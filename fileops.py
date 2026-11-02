"""عمليات الملفات على كل المصادر: مجلد جديد، إعادة تسمية، نقل، نسخ، تجميع، حذف.
المصدر يُوصَف هكذا: {"type": "local", "root": "home"} أو {"type": "adb", "serial": "..."}.
المسارات المحلية نسبية للجذر؛ مسارات أندرويد مطلقة تحت /sdcard."""
from __future__ import annotations

import datetime as dt
import json
import os
import posixpath
import shlex
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

import archives

M = None  # وحدة الخادم (تُضبط بـ init) لاستعمال adb وcloud_resolve وغيرها
OPS: dict[str, dict] = {}
LOCK = threading.Lock()
LOG = Path(os.environ.get("PB_DATA") or Path(__file__).resolve().parent) / "operations.log"
# مجلدات أساسية لا تُنقل ولا تُحذف ولا يُعاد تسميتها (نسبة إلى مجلد المستخدم)
LOCAL_PROTECTED = {"", "Library", "Documents", "Desktop", "Downloads", "Pictures", "Movies", "Music", "Applications", ".Trash", "نسخ احتياطي"}


def init(module):
    global M
    M = module
    load_log()


class Cancelled(Exception):
    pass


def title_of(kind, n, name=""):
    t = {"mkdir": "مجلد جديد", "rename": "إعادة تسمية", "copy": "نسخ", "move": "نقل", "delete": "حذف", "group": "تجميع في مجلد", "gather": "تجميع من أماكن مختلفة"}[kind]
    return f"{t}: {name}" if name else f"{t} ({n} عنصر)"


class _Op(dict):
    """عملية تسجّل اسم كل ملف تُنهيه (يزداد «done») ليُعرض عند الضغط عليها."""
    def __setitem__(self, k, v):
        if k == "done" and isinstance(v, int) and v > self.get("done", 0):
            cur = self.get("current") or self.get("_last_cur") or ""
            log = self.setdefault("log", [])
            errs = self.get("errors") or []
            failed = bool(errs) and cur in errs[-1]  # الملف الذي فشل للتو لا يُسجَّل منجزًا
            if cur and not failed and (not log or log[-1] != cur) and len(log) < 3000:
                log.append(cur)
        if k == "current" and v:
            dict.__setitem__(self, "_last_cur", v)
        dict.__setitem__(self, k, v)


def new_op(kind, body, n):
    op = {"id": uuid.uuid4().hex[:10], "kind": kind, "title": title_of(kind, n, body.get("name", "")), "state": "running", "done": 0, "total": n,
          "detail": "", "errors": [], "cancel": False, "started": time.time(), "ended": None, "current": ""}
    op = _Op(op)
    op["log"] = []
    with LOCK:
        OPS[op["id"]] = op
    return op


def _probe_size(p, limit=3000):
    """حجم ما كُتب حتى الآن في الوجهة (ملف أو مجلد صغير)."""
    try:
        p = Path(p)
        if p.is_file():
            return p.stat().st_size
        n = tot = 0
        for root, _d, files in os.walk(p):
            for fn in files:
                n += 1
                if n > limit:
                    return tot
                try:
                    tot += os.path.getsize(os.path.join(root, fn))
                except OSError:
                    pass
        return tot
    except Exception:
        return 0


def public(op):
    out = {k: op[k] for k in ("id", "kind", "title", "state", "done", "total", "detail", "errors", "current")} | {"seconds": round((op["ended"] or time.time()) - op["started"], 1)}
    tot = op.get("bytes_total")
    if tot:
        part = op.get("rc_bytes") or 0
        if not part and op.get("probe") and op["state"] == "running":
            part = _probe_size(op["probe"])
        done = min(tot, op.get("bytes_base", 0) + part)
        now = time.time()
        smp = op.setdefault("_smp", [])
        smp.append((now, done))
        while len(smp) > 2 and now - smp[0][0] > 6:
            smp.pop(0)
        speed = (smp[-1][1] - smp[0][1]) / (smp[-1][0] - smp[0][0]) if len(smp) > 1 and smp[-1][0] > smp[0][0] else 0
        if op["state"] != "running":
            done = tot if op["state"] == "done" and not op["errors"] else done
            el = max(0.1, (op["ended"] or now) - op["started"])
            speed = done / el
        out |= {"bytes_done": done, "bytes_total": tot, "speed": round(speed), "eta": round((tot - done) / speed) if speed > 0 and op["state"] == "running" else None}
    if op.get("paused"):
        out["paused"] = True
        out["eta"] = None
    if op.get("retry") and op["state"] != "running":
        out["retry"] = op["retry"]
    return out


def item_size(src, path):
    try:
        if src.get("type") == "abs":
            return _probe_size(path, 20000)
        if src.get("type") == "local":
            if str(src.get("root", "")).startswith("rc:"):
                import rclone_src as R
                st = R.stat(src["root"], path)
                return (st or {}).get("size") or 0 if st and not st["is_dir"] else 0
            if "::" in path:
                return 0
            return _probe_size(local_path(src, path, allow_root=True)[1], 20000)
        if src.get("type") == "adb":
            kind, size = remote_size(src["serial"], M.storage_path(path, src["serial"]))
            return size or 0
        if src.get("type") == "kindle":
            import kindle_src
            st = kindle_src.stat(path)
            return (st or {}).get("size") or 0 if st and not st["is_dir"] else 0
        if src.get("type") == "ios":
            import ios_src
            st = ios_src.stat(src["udid"], path)
            return (st or {}).get("size") or 0 if st and not st["is_dir"] else 0
    except Exception:
        return 0
    return 0


def details(op_id):
    op = OPS.get(op_id) or OPS.get("h" + op_id)
    if not op:
        raise ValueError("العملية غير موجودة.")
    return public(op) | {"log": list(op.get("log") or []), "errors": list(op.get("errors") or []), "started": op.get("started"), "ended": op.get("ended"),
                         "history": op.get("history", "")}


def persist(op):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": dt.datetime.now().isoformat(timespec="seconds"), "id": op["id"], "title": op["title"], "state": op["state"],
                             "done": op["done"], "total": op["total"], "errors": op["errors"][:50], "detail": op["detail"][:200], "log": list(op.get("log") or [])[:300]}, ensure_ascii=False) + "\n")


def load_log():
    if not LOG.exists():
        return
    try:
        lines = LOG.read_text(encoding="utf-8").splitlines()[-50:]
        for line in lines:
            d = json.loads(line)
            OPS.setdefault("h" + d["id"], {"id": d["id"], "kind": "log", "title": d["title"], "state": d["state"], "done": d["done"], "total": d["total"],
                                           "detail": d.get("detail", ""), "errors": d.get("errors", []), "cancel": False, "started": 0, "ended": 0, "current": "", "history": d["time"], "log": d.get("log", [])})
    except Exception:
        pass


def listing():
    with LOCK:
        ops = sorted(OPS.values(), key=lambda o: o["started"], reverse=True)
    out = []
    for o in ops[:60]:
        p = public(o)
        p["time"] = o.get("history") or dt.datetime.fromtimestamp(o["started"]).isoformat(timespec="seconds")
        out.append(p)
    return out


def check(op):
    while op.get("paused") and not op["cancel"]:
        time.sleep(0.3)
    if op["cancel"]:
        raise Cancelled()


def _copy_file(src, dst, op):
    """نسخ بقطع 4MB يسمح بالإيقاف المؤقت والإلغاء داخل الملف الكبير نفسه."""
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while True:
            check(op)
            b = fi.read(4 << 20)
            if not b:
                break
            fo.write(b)
    shutil.copystat(src, dst)
    return dst


def _signal(op, sig):
    p = op.get("proc")
    if p is not None and p.poll() is None:
        try:
            os.kill(p.pid, sig)
        except OSError:
            pass


def pause(op_id, paused):
    import signal
    op = OPS.get(op_id)
    if op and op["state"] == "running":
        op["paused"] = bool(paused)
        _signal(op, signal.SIGSTOP if paused else signal.SIGCONT)


# ---------------- حلّ المسارات ----------------
def local_path(src, rel, allow_root=False):
    base, target = M.cloud_resolve(src["root"], rel)
    if not allow_root and (target == base):
        raise ValueError("لا يمكن تنفيذ هذه العملية على جذر المصدر.")
    return base, target


def check_local_protected(src, rel):
    if src["root"] == "home" and rel.strip("/") in LOCAL_PROTECTED:
        raise ValueError("مجلد أساسي محمي: " + (rel or "الرئيسي"))


def adb_path(src, path):
    p = M.storage_path(path, src["serial"])
    if p in M.PROTECTED_PATHS:
        raise ValueError("مجلد أساسي محمي: " + p)
    return p


def valid_name(name):
    name = (name or "").strip()
    if not name or name in (".", "..") or "/" in name or "\0" in name or len(name) > 200:
        raise ValueError("اسم غير صالح.")
    return name


def unique_local(directory: Path, name: str) -> Path:
    cand = directory / name
    stem, ext = os.path.splitext(name)
    i = 2
    while cand.exists() or cand.is_symlink():
        cand = directory / f"{stem} {i}{ext}"
        i += 1
    return cand


def unique_adb(serial, directory, name):
    stem, ext = posixpath.splitext(name)
    cand, i = name, 2
    while M.shell("test -e " + shlex.quote(directory + "/" + cand), serial, 10).returncode == 0:
        cand = f"{stem} {i}{ext}"
        i += 1
    return cand


def same_dir_as_source(src, dst):
    return src.get("type") == dst.get("type") and (src.get("root") == dst.get("root") if src["type"] == "local" else src.get("serial") == dst.get("serial"))


# ---------------- الأوامر الأساسية ----------------
def arch_target(src, rel):
    """يعيد (مسار الأرشيف المحلي، المسار الداخلي) إن كان rel داخل أرشيف، وإلا None."""
    if src.get("type") != "local" or "::" not in rel:
        return None
    a_rel, inner = archives.split(rel)
    _b, apath = local_path(src, a_rel)
    if not apath.is_file() or not archives.is_archive_name(apath.name):
        raise ValueError("ليس أرشيفًا مدعومًا.")
    return apath, (inner or "")


def do_mkdir(src, parent, name):
    name = valid_name(name)
    at = arch_target(src, parent)
    if at:
        return archives.mkdir(at[0], at[1], name)
    if src["type"] == "local" and str(src.get("root", "")).startswith("rc:"):
        import rclone_src as R
        R._run(["mkdir", R.spec(src["root"], "/".join(x for x in (parent.strip("/"), name) if x))], 60)
        return name
    if src["type"] == "local":
        _b, d = local_path(src, parent, allow_root=True)
        if not d.is_dir():
            raise ValueError("المجلد الأب غير موجود.")
        target = unique_local(d, name)
        target.mkdir()
        return target.name
    p = M.storage_path(parent, src["serial"])
    nm = unique_adb(src["serial"], p, name)
    r = M.shell("mkdir " + shlex.quote(p + "/" + nm), src["serial"], 30)
    if r.returncode:
        raise ValueError("تعذّر إنشاء المجلد: " + r.stderr.strip()[:120])
    return nm


def do_rename(src, path, new_name):
    new_name = valid_name(new_name)
    at = arch_target(src, path)
    if at:
        archives.rename(at[0], at[1], new_name)
        return
    if src["type"] == "local":
        check_local_protected(src, path)
        _b, s = local_path(src, path)
        d = s.parent / new_name
        if d.exists():
            raise ValueError("يوجد عنصر بهذا الاسم.")
        os.rename(s, d)
        return
    p = adb_path(src, path)
    dest = posixpath.dirname(p) + "/" + new_name
    if M.shell("test -e " + shlex.quote(dest), src["serial"], 10).returncode == 0:
        raise ValueError("يوجد عنصر بهذا الاسم.")
    r = M.shell("mv " + shlex.quote(p) + " " + shlex.quote(dest), src["serial"], 60)
    if r.returncode:
        raise ValueError("تعذّرت إعادة التسمية: " + r.stderr.strip()[:120])


def _same_device(a, b):
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def trash_local(path: Path):
    d = M.cleaner.trash_dir_for(path)
    dest = unique_local(d, path.name)
    shutil.move(str(path), str(dest))


def remote_size(serial, p):
    out = M.shell("stat -c '%F|%s' " + shlex.quote(p), serial, 15).stdout.strip().split("|")
    return (out[0], int(out[1])) if len(out) == 2 and out[1].isdigit() else (None, None)


def archive_copy(op, src, path, dst, dst_dir, move, policy):
    """نسخ/نقل يكون المصدر أو الوجهة فيه داخل أرشيف: عبر مجلد مؤقت."""
    sa, da = arch_target(src, path), arch_target(dst, dst_dir)
    tmp = Path(tempfile.mkdtemp())
    try:
        if sa and da and sa[0] == da[0] and move:                       # نقل داخل الأرشيف نفسه
            name = posixpath.basename(sa[1])
            target = (da[1] + "/" if da[1] else "") + name
            if target == sa[1] or target.startswith(sa[1] + "/"):
                raise ValueError("لا يمكن نقل مجلد إلى داخل نفسه.")
            archives.move_within(sa[0], [(sa[1], target)])
            return name
        if sa:
            staged = archives.extract(sa[0], sa[1], tmp / "src")
        elif src["type"] == "local":
            _b, staged = local_path(src, path)
        else:
            staged = tmp / "src" / posixpath.basename(path.rstrip("/"))
            staged.parent.mkdir(parents=True)
            rp = M.storage_path(path, src["serial"])
            r = M.adb("pull", "-a", rp, str(staged), serial=src["serial"], timeout=7200)
            if r.returncode:
                raise ValueError("تعذّر السحب من الجهاز.")
        name = staged.name
        if da:
            final = archives.add(da[0], da[1], [(staged, name)], policy) or name
        else:
            final = copy_one(op, {"type": "abs"}, str(staged), dst, dst_dir, False, policy)
        if move:
            if sa:
                archives.delete(sa[0], [sa[1]])
            elif src["type"] == "local":
                trash_local(staged)
            else:
                M.shell("rm -rf " + shlex.quote(M.storage_path(path, src["serial"])), src["serial"], 300)
        return final
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _rc_root(side):
    r = side.get("root", "") if side.get("type") == "local" else ""
    return r if r.startswith("rc:") else None


def rc_copy_one(op, src, path, dst, dst_dir, move, policy):
    """نسخ/نقل يمس حسابًا سحابيًا (rclone) عبر مجلد مؤقت؛ لا يُحذف الأصل إلا بعد نجاح النسخ."""
    import rclone_src as R
    sr, dr = _rc_root(src), _rc_root(dst)
    name = posixpath.basename(path.rstrip("/"))
    tmp = tempfile.mkdtemp()
    try:
        if sr:
            staged = Path(tmp) / name
            op["probe"] = str(staged)
            st = R.download(sr, path, staged, on_proc=lambda p: op.__setitem__("proc", p))
            op["probe"] = None
            if dr is None:
                final = copy_one(op, {"type": "abs"}, str(staged), dst, dst_dir, False, policy)
            else:
                final = rc_put(R, staged, dr, dst_dir, name, policy, op)
            if move and final is not None:
                R.remove(sr, path, st["is_dir"])
            return final
        # المصدر محلي أو جهاز → حساب سحابي
        if src["type"] == "adb":
            staged = Path(tmp) / name
            r = M.adb("pull", "-a", M.storage_path(path, src["serial"]), str(staged), serial=src["serial"], timeout=7200)
            if r.returncode:
                raise ValueError("تعذّر السحب من الجهاز.")
        else:
            if move:
                check_local_protected(src, path)
            staged = Path(path) if src["type"] == "abs" else local_path(src, path)[1]
        final = rc_put(R, staged, dr, dst_dir, name, policy, op)
        if move and final is not None:
            if src["type"] == "adb":
                M.shell("rm -rf " + shlex.quote(M.storage_path(path, src["serial"])), src["serial"], 300)
            else:
                trash_local(staged)
        return final
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def rc_put(R, staged, dr, dst_dir, name, policy, op=None):
    final = name
    rel = lambda n: "/".join(x for x in (dst_dir.strip("/"), n) if x)
    ex = R.stat(dr, rel(name))
    if ex:
        if policy == "skip":
            return None
        if policy == "replace":
            R.remove(dr, rel(name), ex["is_dir"])
        else:
            stem, ext = os.path.splitext(name)
            i = 2
            while R.stat(dr, rel(final)):
                final = f"{stem} {i}{ext}"
                i += 1
    R.upload(staged, dr, rel(final), progress=(lambda b: op.__setitem__("rc_bytes", b)) if op is not None else None, on_proc=(lambda p: op.__setitem__("proc", p)) if op is not None else None)
    return final


def kindle_copy_one(op, src, path, dst, dst_dir, move, policy):
    """الكيندل: يُجلب منه إلى مجلد مؤقت ثم يُنسخ عاديًّا؛ وإليه: يُجهَّز الملف محليًّا ثم يُرسل."""
    import kindle_src
    import uuid as _u
    if src.get("type") == "kindle":
        if dst.get("type") == "kindle":
            raise ValueError("انسخ من الكيندل إلى مكان آخر.")
        tmp = tempfile.mkdtemp()
        try:
            staged = Path(tmp) / posixpath.basename(path.rstrip("/"))
            op["probe"] = str(staged)
            kindle_src.pull(path, str(staged))
            return copy_one(op, {"type": "abs"}, str(staged), dst, dst_dir, False, policy)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # الوجهة كيندل: نجهّز نسخة محلية في مجلد مؤقت داخل المجلد الشخصي
    rel_tmp = "Library/Caches/zajel-tmp/" + _u.uuid4().hex[:10]
    tdir = Path.home() / rel_tmp
    tdir.mkdir(parents=True, exist_ok=True)
    try:
        if src.get("type") == "abs":
            staged = Path(path)
        else:
            nm = copy_one(op, src, path, {"type": "local", "root": "home"}, rel_tmp, False, "rename")
            staged = tdir / (nm or posixpath.basename(path.rstrip("/")))
        if staged.is_dir():
            raise ValueError("أرسل إلى الكيندل ملفات الكتب نفسها، لا المجلدات.")
        name = staged.name
        try:
            ex = kindle_src.stat("/".join(x for x in (dst_dir.strip("/"), name) if x))
        except ValueError:
            ex = None
        if ex:
            if policy == "skip":
                return None
            if policy == "replace":
                kindle_src.delete("/".join(x for x in (dst_dir.strip("/"), name) if x))
            else:
                stem, ext = os.path.splitext(name)
                i = 2
                while True:
                    cand = f"{stem} {i}{ext}"
                    try:
                        kindle_src.stat("/".join(x for x in (dst_dir.strip("/"), cand) if x))
                        i += 1
                    except ValueError:
                        name = cand
                        break
        kindle_src.push(str(staged), dst_dir, name)
        return name  # إلى الكيندل: نسخ دائمًا (الأصل يبقى)
    finally:
        shutil.rmtree(tdir, ignore_errors=True)


def copy_one(op, src, path, dst, dst_dir, move, policy):
    """ينسخ أو ينقل عنصرًا واحدًا. يعيد الاسم الجديد في الوجهة."""
    if src.get("type") == "kindle" or dst.get("type") == "kindle":
        return kindle_copy_one(op, src, path, dst, dst_dir, move, policy)
    if src.get("type") == "ios":  # الآيفون/الآيباد: قراءة فقط — يُجلب إلى مجلد مؤقت ثم يُنسخ كملف عادي
        import ios_src
        if dst.get("type") == "ios":
            raise ValueError("لا يمكن الكتابة إلى الآيفون/الآيباد.")
        tmp = tempfile.mkdtemp()
        try:
            staged = Path(tmp) / posixpath.basename(path.rstrip("/"))
            op["probe"] = str(staged)
            ios_src.pull(src["udid"], path, str(staged))
            return copy_one(op, {"type": "abs"}, str(staged), dst, dst_dir, False, policy)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if dst.get("type") == "ios":
        raise ValueError("لا يمكن الكتابة إلى الآيفون/الآيباد.")
    if _rc_root(src) or _rc_root(dst):
        return rc_copy_one(op, src, path, dst, dst_dir, move, policy)
    if src["type"] != "abs" and (arch_target(src, path) or arch_target(dst, dst_dir)):
        return archive_copy(op, src, path, dst, dst_dir, move, policy)
    name = posixpath.basename(path.rstrip("/"))
    sl, dl = src["type"] in ("local", "abs"), dst["type"] == "local"
    # --- الوجهة ---
    if dl:
        _b, ddir = local_path(dst, dst_dir, allow_root=True)
        if not ddir.is_dir():
            raise ValueError("مجلد الوجهة غير موجود.")
    else:
        rdir = M.storage_path(dst_dir, dst["serial"])
    # --- المصدر ---
    if sl:
        if src["type"] == "abs":
            spath = Path(path)
        else:
            if move:
                check_local_protected(src, path)
            _b, spath = local_path(src, path)
        if dl and (spath == ddir or spath in ddir.parents):
            raise ValueError("لا يمكن نسخ مجلد إلى داخل نفسه.")
    else:
        rpath = M.storage_path(path, src["serial"])
        if move and rpath in M.PROTECTED_PATHS:
            raise ValueError("مجلد أساسي محمي: " + rpath)
    # --- اسم الوجهة وسياسة التعارض ---
    if dl:
        exists = (ddir / name).exists()
    else:
        exists = M.shell("test -e " + shlex.quote(rdir + "/" + name), dst["serial"], 10).returncode == 0
    final = name
    if exists:
        if policy == "skip":
            return None
        if policy == "replace":
            if dl:
                trash_local(ddir / name)
            else:
                M.shell("rm -rf " + shlex.quote(rdir + "/" + name), dst["serial"], 120)
        else:
            final = unique_local(ddir, name).name if dl else unique_adb(dst["serial"], rdir, name)
    # --- التنفيذ ---
    if sl and dl:
        target = ddir / final
        op["probe"] = str(target)
        try:
            import ebook
            if ebook.is_kindle_root(dst.get("root")) and not spath.is_dir() and ebook.needs_convert(spath.name):
                conv = ebook.convert(spath, tempfile.mkdtemp(), lambda: check(op))  # صيغة لا يقرؤها الكيندل: تُحوَّل إلى azw3 تلقائيًا
                try:
                    target = ddir / unique_local(ddir, conv.name).name if (ddir / conv.name).exists() and policy != "replace" else ddir / conv.name
                    op["probe"] = str(target)
                    _copy_file(conv, target, op)
                finally:
                    shutil.rmtree(conv.parent, ignore_errors=True)
                if move:
                    trash_local(spath)
                return target.name
            if move and _same_device(spath, ddir):
                shutil.move(str(spath), str(target))
            elif spath.is_dir():
                shutil.copytree(spath, target, symlinks=True, copy_function=lambda s, d: _copy_file(s, d, op))
            else:
                _copy_file(spath, target, op)
        except Cancelled:
            shutil.rmtree(target, ignore_errors=True) if target.is_dir() else target.unlink(missing_ok=True)
            raise
        if move and spath.exists():  # مثل shutil.move بين قرصين: يُزال الأصل بعد اكتمال النسخ
            shutil.rmtree(spath) if spath.is_dir() and not spath.is_symlink() else spath.unlink()
        return final
    if sl and not dl:
        r = M.adb("push", str(spath), rdir + "/" + final, serial=dst["serial"], timeout=7200)
        if r.returncode:
            raise ValueError("تعذّر الرفع إلى الجهاز: " + (r.stderr or r.stdout).strip()[-150:])
        if move:
            trash_local(spath)
        return final
    if not sl and dl:
        target = ddir / final
        op["probe"] = str(target)
        r = M.adb("pull", "-a", rpath, str(target), serial=src["serial"], timeout=7200)
        if r.returncode:
            raise ValueError("تعذّر السحب من الجهاز: " + (r.stderr or r.stdout).strip()[-150:])
        if move:
            kind, size = remote_size(src["serial"], rpath)
            ok = target.exists() and (kind == "directory" or (target.is_file() and target.stat().st_size == size))
            if not ok:
                raise ValueError("لم أتحقق من سلامة النسخة، فلم أحذف الأصل.")
            M.shell("rm -rf " + shlex.quote(rpath), src["serial"], 300)
        return final
    # أندرويد إلى أندرويد
    if src["serial"] == dst["serial"] and move:
        r = M.shell("mv " + shlex.quote(rpath) + " " + shlex.quote(rdir + "/" + final), src["serial"], 300)
        if r.returncode:
            raise ValueError("تعذّر النقل: " + r.stderr.strip()[:120])
        return final
    if src["serial"] == dst["serial"]:
        r = M.shell("cp -r " + shlex.quote(rpath) + " " + shlex.quote(rdir + "/" + final), src["serial"], 600)
        if r.returncode:
            raise ValueError("تعذّر النسخ: " + r.stderr.strip()[:120])
        return final
    tmp = tempfile.mkdtemp()
    try:
        t = os.path.join(tmp, final)
        if M.adb("pull", "-a", rpath, t, serial=src["serial"], timeout=7200).returncode or M.adb("push", t, rdir + "/" + final, serial=dst["serial"], timeout=7200).returncode:
            raise ValueError("تعذّر النقل بين الجهازين.")
        if move:
            M.shell("rm -rf " + shlex.quote(rpath), src["serial"], 300)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return final


def do_delete(op, src, paths, allow_unverified):
    if src.get("type") == "kindle":  # الكيندل: حذف نهائي (لا سلة فيه)، بتأكيد الواجهة
        import kindle_src
        for p in paths:
            check(op)
            op["current"] = p
            try:
                kindle_src.delete(p)
            except Exception as exc:
                op["errors"].append(f"{p}: {exc}")
            op["done"] += 1
        return
    if src["type"] == "adb":
        rep = M.delete_paths(src["serial"], paths, allow_unverified)
        for r in rep:
            op["done"] += 1
            if not r["ok"]:
                op["errors"].append(f"{r['path']}: {r['detail']}")
        return
    by_arch = {}
    plain = []
    for p in paths:
        at = arch_target(src, p) if "::" in p else None
        (by_arch.setdefault(at[0], []).append(at[1]) if at else plain.append(p))
    for apath, inners in by_arch.items():
        check(op)
        op["current"] = apath.name
        try:
            archives.delete(apath, inners)
        except Exception as exc:
            op["errors"].append(f"{apath.name}: {exc}")
        op["done"] += len(inners)
    for p in plain:
        check(op)
        op["current"] = p
        try:
            if _rc_root(src):
                import rclone_src as R
                st = R.stat(src["root"], p)
                if st is None:
                    raise ValueError("لم يعد موجودًا.")
                R.remove(src["root"], p, st["is_dir"])  # إلى سلة الخدمة
                op["done"] += 1
                continue
            check_local_protected(src, p)
            _b, target = local_path(src, p)
            if not target.exists() and not target.is_symlink():
                raise ValueError("لم يعد موجودًا.")
            trash_local(target)
        except Exception as exc:
            op["errors"].append(f"{p}: {exc}")
        op["done"] += 1


def run(op, body):
    try:
        kind, src, paths = body["kind"], body.get("src"), body.get("paths", [])
        if kind == "mkdir":
            op["detail"] = "أُنشئ: " + do_mkdir(src, body["parent"], body["name"])
            op["done"] = 1
        elif kind == "rename":
            do_rename(src, paths[0], body["name"])
            op["done"] = 1
        elif kind == "delete":
            do_delete(op, src, paths, bool(body.get("allow_unverified")))
        elif kind in ("copy", "move"):
            cap = 20 if _rc_root(src) else 200 if src.get("type") == "adb" else 2000
            sizes = {p: item_size(src, p) for p in paths} if len(paths) <= cap else {}
            op["bytes_total"] = sum(sizes.values()) or None
            op["bytes_base"] = 0
            failed = []
            for p in paths:
                check(op)
                op["current"] = p
                op["probe"] = None
                op["rc_bytes"] = 0
                try:
                    copy_one(op, src, p, body["dst"], body["dst_dir"], kind == "move", body.get("policy", "keep"))
                except Cancelled:
                    raise
                except Exception as exc:
                    op["errors"].append(f"{p}: {exc}")
                    failed.append(p)
                op["bytes_base"] += sizes.get(p, 0)
                op["probe"] = None
                op["rc_bytes"] = 0
                op["done"] += 1
            if failed:
                op["retry"] = {k: v for k, v in body.items() if k in ("kind", "src", "dst", "dst_dir", "policy")} | {"paths": failed}
        elif kind == "gather":
            dst = body["dst"]
            folder = do_mkdir(dst, body["parent"], body["name"])
            dst_dir = (body["parent"] + "/" + folder).replace("//", "/") if dst["type"] == "adb" else (
                body["parent"] + ("/" if body["parent"] and not body["parent"].endswith("::") else "") + folder)
            move = body.get("mode") == "move"
            for it in body["items"]:
                check(op)
                op["current"] = it["path"]
                try:
                    copy_one(op, it["src"], it["path"], dst, dst_dir, move, "keep")
                except Cancelled:
                    raise
                except Exception as exc:
                    op["errors"].append(f"{it['path']}: {exc}")
                op["done"] += 1
            op["detail"] = "المجلد: " + folder + (" (نقل)" if move else " (نسخ)")
        elif kind == "group":
            def parent_of(p):
                p = p.rstrip("/")
                if "::" in p:
                    arc, inner = p.split("::", 1)
                    d = posixpath.dirname(inner.strip("/"))
                    return arc + "::" + d
                return posixpath.dirname(p)
            parent = parent_of(paths[0])
            if any(parent_of(x) != parent for x in paths):
                raise ValueError("لتجميعها يجب أن تكون كلها في المجلد نفسه.")
            if src["type"] == "adb" and parent == "":
                parent = "/sdcard"
            folder = do_mkdir(src, parent, body["name"])
            if "::" in parent:
                dst_dir = parent + ("/" if not parent.endswith("::") else "") + folder
            elif src["type"] == "adb":
                dst_dir = (parent + "/" + folder).replace("//", "/")
            else:
                dst_dir = parent + "/" + folder if parent else folder
            for p in paths:
                check(op)
                op["current"] = p
                try:
                    copy_one(op, src, p, src, dst_dir, True, "keep")
                except Cancelled:
                    raise
                except Exception as exc:
                    op["errors"].append(f"{p}: {exc}")
                op["done"] += 1
            op["detail"] = "المجلد: " + folder
        op["state"] = "done" if not op["errors"] else ("error" if op["done"] == 0 or len(op["errors"]) >= op["total"] else "done")
        if op["errors"] and op["state"] == "done":
            op["detail"] = (op["detail"] + " · " if op["detail"] else "") + f"{len(op['errors'])} فشل"
    except Cancelled:
        op["state"] = "cancelled"
    except Exception as exc:
        op["state"] = "error"
        op["errors"].append(str(exc))
    finally:
        op["current"] = ""
        op["ended"] = time.time()
        persist(op)


def start(body):
    kind = body.get("kind")
    if kind not in ("mkdir", "rename", "copy", "move", "delete", "group", "gather"):
        raise ValueError("نوع عملية غير معروف.")
    src = body.get("src") or {}
    if src.get("type") == "kindle" and kind not in ("copy", "delete"):
        raise ValueError("من الكيندل: النسخ والحذف فقط.")
    if src.get("type") == "ios" and kind not in ("copy",):
        raise ValueError("الآيفون/الآيباد للقراءة فقط: يمكن النسخ منه فقط.")
    if src.get("type") == "adb":
        src["serial"] = M.connected_device(src.get("serial"))
    if kind in ("copy", "move"):
        dst = body.get("dst") or {}
        if dst.get("type") == "adb":
            dst["serial"] = M.connected_device(dst.get("serial"))
        body["dst"] = dst
    if kind == "gather":
        dst = body.get("dst") or {}
        if dst.get("type") == "adb":
            dst["serial"] = M.connected_device(dst.get("serial"))
        items = body.get("items")
        if not isinstance(items, list) or not items or len(items) > 5000:
            raise ValueError("قائمة العناصر غير صالحة.")
        for it in items:
            s = it.get("src") or {}
            if s.get("type") == "adb":
                s["serial"] = M.connected_device(s.get("serial"))
            it["src"] = s
        valid_name(body.get("name"))
        body["dst"] = dst
        op = new_op(kind, body, len(items))
        threading.Thread(target=run, args=(op, body), daemon=True).start()
        return public(op)
    paths = body.get("paths", [])
    if kind in ("copy", "move", "delete", "group", "rename") and (not isinstance(paths, list) or not paths or len(paths) > 5000):
        raise ValueError("قائمة العناصر غير صالحة.")
    if kind == "delete" and body.get("confirm") is not True:
        raise ValueError("يلزم تأكيد صريح من المستخدم.")
    if kind == "group":
        valid_name(body.get("name"))
    body["src"] = src
    n = 1 if kind in ("mkdir", "rename") else len(paths)
    op = new_op(kind, body, n)
    threading.Thread(target=run, args=(op, body), daemon=True).start()
    return public(op)


def cancel(op_id):
    import signal
    op = OPS.get(op_id)
    if op:
        op["cancel"] = True
        op["paused"] = False
        _signal(op, signal.SIGCONT)
        _signal(op, signal.SIGTERM)
