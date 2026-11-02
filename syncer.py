"""المزامنة التلقائية: مجلد واحد في عدة أماكن (الكمبيوتر، قرص، سحابة متزامنة، حساب سحابي مباشر، الهاتف).
كل مدة يحددها المستخدم تُقارن النسخ، ويُنسخ كل ملف إلى المكان الذي ينقصه أو فيه نسخة أقدم (الأحدث يغلب).
الحذف لا ينتقل إلا إذا فُعّل للمجموعة، وإلى السلة دائمًا، وبشرط اتصال كل الأماكن."""
from __future__ import annotations

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

M = None
GROUPS = None
LOCK = threading.Lock()
STATE = {}  # id -> {"running", "last", "result"}
SKIP = {".DS_Store", "Thumbs.db", "desktop.ini", "Icon\r", "Icon\u240d"}  # Icon\r: أيقونة مجلد في الماك، ويحوّلها rclone إلى «Icon␍» فلا تتطابق أبدًا
# عند تضمين المخفيات (خزائن Obsidian): تُستثنى ملفات تتغير باستمرار أو خاصة بكل جهاز فتسبب تضاربًا لا ينتهي
HIDDEN_IGNORE = {".trash", ".git", ".sync", ".syncthing", ".stfolder", "workspace.json", "workspace-mobile.json", ".zajel_trash", ".Spotlight-V100", ".fseventsd", ".Trashes"}


def init(module, data_dir: Path):
    global M, GROUPS
    M = module
    GROUPS = data_dir / ".sync.json"
    threading.Thread(target=_loop, daemon=True).start()


def groups():
    try:
        return json.loads(GROUPS.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(v):
    tmp = GROUPS.with_suffix(".tmp")
    tmp.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(GROUPS)


def save(items):
    out = []
    old = {g["id"]: g for g in groups()}
    for g in items if isinstance(items, list) else []:
        locs = []
        for l in g.get("locations") or []:
            kind, root, path = str(l.get("kind") or ""), str(l.get("root") or ""), str(l.get("path") or "").strip("/")
            who = str(l.get("label") or root or "الهاتف")[:80]
            if ".." in path.split("/"):
                raise ValueError(f"{who}: مسار غير صالح.")
            if kind == "ios":
                if not root or not path:
                    raise ValueError(f"{who}: اختر مجلدًا داخل الآيفون/الآيباد لا جذره.")
            elif kind == "adb":
                if not ("/" + path).startswith("/sdcard/"):
                    raise ValueError(f"{who}: اختر مجلدًا داخل الهاتف لا جذر التخزين.")
            elif kind == "local":
                if not root:
                    raise ValueError(f"{who}: مكان غير صالح.")
            else:
                raise ValueError(f"{who}: نوع مكان غير مدعوم.")
            locs.append({"kind": kind, "root": root, "path": path, "label": str(l.get("label") or "")[:120]})
        if len(locs) < 2:
            raise ValueError("المزامنة تحتاج مكانين على الأقل.")
        for a in range(len(locs)):
            for b in range(a + 1, len(locs)):
                x, y = locs[a], locs[b]
                if x["kind"] == y["kind"] and x["root"] == y["root"]:
                    px, py = x["path"].strip("/"), y["path"].strip("/")
                    if px == py or px.startswith(py + "/") or py.startswith(px + "/") or not px or not py:
                        raise ValueError(f"مكانان متداخلان أو مكرران: {x['label'] or px} و{y['label'] or py}.")
        gid = g.get("id") or uuid.uuid4().hex[:8]
        out.append({"id": gid, "name": str(g.get("name") or "مزامنة")[:60], "locations": locs,
                    "every": max(1, min(10080, int(g.get("every") or 30))), "enabled": bool(g.get("enabled", True)),
                    "deletes": bool(g.get("deletes", False)),
                    "mode": "one" if g.get("mode") == "one" else "two",
                    "hidden": _hidden_flag(g, locs),
                    "last": old.get(gid, {}).get("last", 0)})
    with LOCK:
        _save(out)
    return out


def _hidden_flag(g, locs):
    """تضمين الملفات المخفية: بطلب المستخدم، أو تلقائيًا إن كان المجلد خزنة Obsidian (فيه .obsidian)."""
    if g.get("hidden") is not None:
        return bool(g["hidden"])
    for l in locs:
        if l["kind"] == "local" and not l["root"].startswith("rc:"):
            try:
                if (Path(M.cloud_resolve(l["root"], l["path"])[1]) / ".obsidian").is_dir():
                    return True
            except Exception:
                pass
    return False


def _load_prev():
    try:
        return json.loads((GROUPS.parent / ".sync_prev.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_prev(v):
    (GROUPS.parent / ".sync_prev.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")


def _load_memo():
    try:
        return json.loads((GROUPS.parent / ".sync_ios_memo.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _history(gid, name, st, secs):
    """سجل كل تشغيل (يغذّي الرسم البياني): الوقت، المنسوخ، الأخطاء، المحفّز، المدة."""
    try:
        f = GROUPS.parent / ".sync_history.json"
        try:
            h = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            h = []
        h.append({"gid": gid, "name": name, "t": int(time.time()), "copied": st.get("copied", 0), "errors": st.get("nerr", 0 if st.get("ok") else 1),
                  "ok": bool(st.get("ok")), "secs": round(secs, 1), "trigger": st.get("trigger", "يدوي"), "result": st.get("result", "")})
        f.write_text(json.dumps(h[-800:], ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


CATS = [("مستندات", {"pdf", "doc", "docx", "odt", "rtf", "pages", "xls", "xlsx", "csv", "ods", "numbers", "ppt", "pptx", "odp", "key"}),
        ("نصوص وملاحظات", {"txt", "md", "markdown", "log", "json", "xml", "yaml", "yml", "canvas", "org"}),
        ("صور", {"jpg", "jpeg", "png", "gif", "webp", "heic", "heif", "bmp", "tif", "tiff", "dng", "svg", "raw"}),
        ("فيديو", {"mp4", "mov", "mkv", "avi", "webm", "3gp", "m4v"}),
        ("صوت", {"mp3", "m4a", "aac", "wav", "flac", "ogg", "opus", "amr", "aax"}),
        ("كتب", {"epub", "azw", "azw3", "mobi", "prc", "djvu", "fb2", "kfx"}),
        ("أرشيف", {"zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz", "iso", "dmg"}),
        ("تطبيقات وبرمجة", {"apk", "aab", "ipa", "py", "js", "ts", "swift", "kt", "java", "html", "css", "sh"})]


def category_of(rel):
    ext = rel.rsplit(".", 1)[-1].lower() if "." in rel.rsplit("/", 1)[-1] else ""
    for name, exts in CATS:
        if ext in exts:
            return name
    return "أخرى"


_ANA = {}  # gid -> {"t", "cats": {name: [count, bytes]}, "files", "bytes", "busy"}


def _analyze(g):
    a = _ANA.setdefault(g["id"], {"t": 0, "cats": {}, "files": 0, "bytes": 0, "busy": False})
    if a["busy"]:
        return
    a["busy"] = True

    def work():
        try:
            fl = None
            for l in g["locations"]:  # أول مكان متاح وغير سحابي مباشر يكفي لوصف المجلد
                try:
                    x = Loc(l, bool(g.get("hidden")))
                    if x.rc and fl is not None:
                        continue
                    fl = x.files()
                    break
                except Exception:
                    continue
            cats = {}
            for rel, (size, _mt) in (fl or {}).items():
                c = cats.setdefault(category_of(rel), [0, 0])
                c[0] += 1; c[1] += size
            a.update(t=time.time(), cats=cats, files=sum(c[0] for c in cats.values()), bytes=sum(c[1] for c in cats.values()))
        except Exception:
            pass
        finally:
            a["busy"] = False
    threading.Thread(target=work, daemon=True).start()


def overview(refresh=False):
    """لقطة لقسم «المزامنات»: لكل مزامنة فئتها (بحسب محتواها) وحالتها وموعد آخر مرة وتوزيع الأنواع، مع سجل التشغيلات."""
    out = []
    now = time.time()
    for g in groups():
        st = STATE.get(g["id"], {})
        a = _ANA.get(g["id"])
        if refresh or not a or now - a["t"] > 600:
            _analyze(g)
            a = _ANA.get(g["id"])
        cats = sorted(((k, v[0], v[1]) for k, v in (a or {}).get("cats", {}).items()), key=lambda x: -x[1])
        if not g["enabled"]:
            state = "paused"
        elif st.get("running"):
            state = "running"
        elif st.get("waiting"):
            state = "waiting"
        elif not g.get("last"):
            state = "never"
        elif (g.get("ok") if st.get("ok") is None else st.get("ok")) is False:
            state = "error"
        else:
            state = "ok"
        locs = []
        for l in g["locations"]:
            try:
                Loc(l)
                on = True
            except Exception:
                on = False
            kind = "cloud" if l["root"].startswith(("rc:", "GoogleDrive", "OneDrive", "iCloud", "icloud")) else "disk" if l["root"].startswith("vol:") else "phone" if l["kind"] in ("adb", "ios") else "computer"
            locs.append({"label": l.get("label") or l["root"] or "الهاتف", "kind": kind, "online": on})
        out.append({"id": g["id"], "name": g["name"], "enabled": g["enabled"], "mode": g.get("mode", "two"), "every": g["every"], "last": g.get("last") or 0,
                    "result": g.get("result", ""), "op": st.get("op") if st.get("running") else "", "state": state, "waiting": st.get("waiting") or [], "trigger": st.get("trigger", ""),
                    "category": cats[0][0] if cats else ("جارٍ التحليل…" if a and a["busy"] else "فارغ"), "cats": cats,
                    "files": (a or {}).get("files", 0), "bytes": (a or {}).get("bytes", 0), "analyzing": bool(a and a["busy"]), "locs": locs})
    try:
        hist = json.loads((GROUPS.parent / ".sync_history.json").read_text(encoding="utf-8"))[-300:]
    except Exception:
        hist = []
    return {"groups": out, "history": hist}


def status():
    return {"groups": groups(), "state": STATE}


# ---------- طبقة الأماكن ----------
class Loc:
    def __init__(self, l, hidden=False):
        self.l = l
        self.hidden = hidden
        self.kind, self.root, self.path = l["kind"], l["root"], l["path"]
        self.rc = self.kind == "local" and self.root.startswith("rc:")
        if self.kind == "local" and not self.rc:
            self.base = Path(M.cloud_resolve(self.root, self.path)[1])
        if self.kind == "adb":
            self.serial = M.connected_device()
            self.base = "/" + self.path
        if self.kind == "ios":
            import ios_src
            self.I, self.udid, self.base = ios_src, self.root, "/" + self.path
            if not any(d["udid"] == self.udid and not d.get("asleep") for d in ios_src.devices()):
                raise ValueError("الجهاز غير متصل أو مقفل.")
            self.writable = self.base.startswith(ios_src.APPS + "/")
            self.memo = {}  # rel -> [حجم الجهاز، وقته، الوقت المنطقي] (آبل لا تسمح بضبط وقت الملف)

    def files(self):
        """{rel: (size, mtime_sec)}"""
        out = {}
        if self.rc:
            import rclone_src as R
            try:
                items = json.loads(R._run(["lsjson", "-R", "--files-only", "--no-mimetype", R.spec(self.root, self.path)], 900))
            except Exception as exc:
                if "directory not found" in str(exc).lower():
                    return {}
                raise
            from datetime import datetime
            for it in items:
                try:
                    mt = datetime.fromisoformat(it["ModTime"][:19] + "+00:00").timestamp()  # الوقت بتوقيت UTC، لا المحلي
                except Exception:
                    mt = 0
                out[it["Path"]] = (int(it.get("Size") or 0), int(mt))
        elif self.kind == "ios":
            for size, mt, p in self.I.files(self.udid, self.base):
                rel = posixpath.relpath(p, self.base)
                m = self.memo.get(rel)
                out[rel] = (size, m[2] if m and m[0] == size and abs(m[1] - mt) <= 2 else mt)
        elif self.kind == "adb":
            r = M.shell(f"mkdir -p {shlex.quote(self.base)}; find {shlex.quote(self.base)} -type f -exec stat -c '%s|%Y|%n' {{}} + 2>/dev/null", self.serial, 600)
            for line in r.stdout.splitlines():
                p = line.split("|", 2)
                if len(p) == 3 and p[0].isdigit():
                    out[posixpath.relpath(p[2], self.base)] = (int(p[0]), int(p[1]))
        else:
            self.base.mkdir(parents=True, exist_ok=True)
            for dp, ds, fs in os.walk(self.base):
                ds[:] = [d for d in ds if (d not in HIDDEN_IGNORE if self.hidden else not d.startswith("."))]
                for f in fs:
                    fp = os.path.join(dp, f)
                    try:
                        st = os.stat(fp)
                    except OSError:
                        continue
                    out[os.path.relpath(fp, self.base)] = (st.st_size, int(st.st_mtime))
        if self.hidden:
            return {k: v for k, v in out.items() if not any(x in SKIP or x in HIDDEN_IGNORE or x.endswith(".pbsync") for x in k.split("/"))}
        return {k: v for k, v in out.items() if not any(x.startswith(".") or x in SKIP for x in k.split("/"))}

    def get(self, rel, dest):
        """ينسخ الملف إلى مسار محلي مؤقت."""
        if self.rc:
            import rclone_src as R
            R.download(self.root, "/".join(x for x in (self.path, rel) if x), dest)
        elif self.kind == "ios":
            self.I.pull(self.udid, posixpath.join(self.base, rel), str(dest))
        elif self.kind == "adb":
            r = M.adb("pull", "-a", posixpath.join(self.base, rel), str(dest), serial=self.serial, timeout=7200)
            if r.returncode:
                raise ValueError((r.stderr or r.stdout).strip()[-120:])
        else:
            shutil.copy2(self.base / rel, dest)

    def put(self, local, rel, mtime):
        if self.rc:
            import rclone_src as R
            R.upload(local, self.root, "/".join(x for x in (self.path, rel) if x))
        elif self.kind == "adb":
            rp = posixpath.join(self.base, rel)
            M.shell("mkdir -p " + shlex.quote(posixpath.dirname(rp)), self.serial, 30)
            r = M.adb("push", str(local), rp, serial=self.serial, timeout=7200)
            if r.returncode:
                raise ValueError((r.stderr or r.stdout).strip()[-120:])
            M.shell(f"touch -m -d @{int(mtime)} {shlex.quote(rp)}", self.serial, 30)
        elif self.kind == "ios":
            if not self.writable:
                raise ValueError("مجلدات الصور في الآيفون للقراءة فقط.")
            rp = posixpath.join(self.base, rel)
            st = self.I.push(self.udid, local, rp)
            self.memo[rel] = [st["size"], self.I.mtime(self.udid, rp), int(mtime)]
        else:
            t = self.base / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            tmp = t.with_name(t.name + ".pbsync")
            shutil.copy2(local, tmp)
            os.utime(tmp, (mtime, mtime))
            tmp.replace(t)

    def trash(self, rel):
        """حذف آمن: سلة الكمبيوتر/الخدمة؛ وفي الهاتف والآيفون مجلد «.zajel_trash» بدل المحو."""
        if self.rc:
            import rclone_src as R
            R.remove(self.root, "/".join(x for x in (self.path, rel) if x), False)
        elif self.kind == "adb":
            rp = posixpath.join(self.base, rel)
            tp = posixpath.join("/sdcard/.zajel_trash", time.strftime("%Y-%m-%d"), self.path.replace("sdcard/", "", 1), rel)
            M.shell(f"mkdir -p {shlex.quote(posixpath.dirname(tp))} && mv -f {shlex.quote(rp)} {shlex.quote(tp)}", self.serial, 60)
        elif self.kind == "ios":
            if not self.writable:
                raise ValueError("مجلدات الصور في الآيفون للقراءة فقط.")
            self.I.trash(self.udid, posixpath.join(self.base, rel))
            self.memo.pop(rel, None)
        else:
            M.fileops.trash_local(self.base / rel)

    def local_path(self, rel):
        return None if self.rc or self.kind in ("adb", "ios") else self.base / rel


def run(gid):
    g = next((x for x in groups() if x["id"] == gid), None)
    if not g or STATE.get(gid, {}).get("running"):
        return
    st = STATE.setdefault(gid, {})
    st.update(running=True, last=time.time(), result="", ok=None)
    t_start = time.time()
    op = M.fileops.new_op("copy", {"name": "مزامنة: " + g["name"]}, 0)
    op["title"] = "مزامنة: " + g["name"]
    st["op"] = op["id"]
    locs = []
    copied, errors, tmpdir = 0, [], Path(tempfile.mkdtemp(prefix="pbsync-"))
    try:
        locs, skipped = [], []
        for l in g["locations"]:
            try:
                locs.append(Loc(l, bool(g.get("hidden"))))
            except Exception as exc:
                skipped.append(f"{l.get('label') or l['root'] or 'الهاتف'}: {exc}")
        if len(locs) < 2:
            raise ValueError("لا يتوفر مكانان متصلان الآن. " + " · ".join(skipped))
        memo_all = _load_memo()
        for k, x in enumerate(locs):
            if x.kind == "ios":
                x.memo = memo_all.get(f"{gid}|{x.udid}|{x.path}", {})
        lists = [x.files() for x in locs]
        best = {}
        one = g.get("mode") == "one"  # اتجاه واحد: الأول مصدر فقط، لا يُكتب فيه ولا يُحذف منه
        for i, fl in enumerate(lists):
            if one and i > 0:
                break
            for rel, (size, mt) in fl.items():
                b = best.get(rel)
                if not b or mt > b[2] + 2:
                    best[rel] = (i, size, mt)
        prev_all = _load_prev()
        prev = prev_all.get(gid, {}) if g.get("deletes") and not skipped and not one else {}
        deleted = 0
        for rel, pmt in prev.items():
            gone = [k for k, fl in enumerate(lists) if rel not in fl]
            if not gone or rel not in best:
                continue
            if any(fl[rel][1] > pmt + 2 for fl in lists if rel in fl):
                continue  # عُدّل بعد آخر مزامنة: التعديل يغلب الحذف
            for k, fl in enumerate(lists):
                if rel in fl and not (locs[k].kind == "ios" and not locs[k].writable):
                    try:
                        locs[k].trash(rel)
                        fl.pop(rel)
                        deleted += 1
                        op["log"].append("🗑 " + rel)
                    except Exception as exc:
                        errors.append(f"{rel}: حذف: {exc}")
                        op["errors"].append(f"{rel}: حذف: {exc}")
            if not any(rel in fl for fl in lists):
                best.pop(rel)
        plan = []
        for rel, (i, size, mt) in best.items():
            for j, fl in enumerate(lists):
                if j == i or (locs[j].kind == "ios" and not locs[j].writable):
                    continue
                cur = fl.get(rel)
                if not cur or cur[1] + 2 < mt:
                    plan.append((rel, i, j, size, mt))
        plan_all = list(plan)
        op["total"] = len(plan)
        op["bytes_total"] = sum(p[3] for p in plan) or None
        op["bytes_base"] = 0
        staged, failed = {}, set()
        # دفعات rclone: استدعاء واحد لكل (مصدر، وجهة) بدل تشغيل rclone لكل ملف (ثانيتان للملف ← آلاف الملفات في نصف ساعة)
        groups_rc = {}
        for item in plan:
            rel, i, j = item[0], item[1], item[2]
            if (locs[j].rc and locs[i].local_path(rel) is not None) or (locs[i].rc and locs[j].local_path(rel) is not None):
                groups_rc.setdefault((i, j), []).append(item)
        if groups_rc:
            import rclone_src as R
            for (i, j), items in groups_rc.items():
                if op["cancel"]:
                    break
                lst = tmpdir / f"files-{i}-{j}.txt"
                lst.write_text("\n".join(x[0] for x in items) + "\n", encoding="utf-8")
                src = R.spec(locs[i].root, locs[i].path) if locs[i].rc else str(locs[i].base)
                dst = R.spec(locs[j].root, locs[j].path) if locs[j].rc else str(locs[j].base)
                op["current"] = f"دفعة: {len(items)} ملف ← {locs[j].l.get('label') or locs[j].root}"
                try:
                    R._run(["copy", src, dst, "--files-from-raw", str(lst), "--no-traverse", "--transfers", "8", "--checkers", "16"], 7200)
                    for x in items:
                        plan.remove(x)
                        copied += 1
                        op["done"] += 1
                        op["bytes_base"] += x[3]
                except Exception as exc:
                    op["errors"].append(f"دفعة إلى {locs[j].l.get('label') or locs[j].root}: {exc} — أكمل ملفًا ملفًا")
        for rel, i, j, size, mt in plan:
            if op["cancel"]:
                break
            op["current"] = rel
            try:
                src = locs[i].local_path(rel)
                if src is None:
                    if rel not in staged:
                        t = tmpdir / uuid.uuid4().hex
                        locs[i].get(rel, t)
                        staged[rel] = t
                    src = staged[rel]
                locs[j].put(src, rel, mt)
                copied += 1
            except Exception as exc:
                errors.append(f"{rel}: {exc}")
                op["errors"].append(f"{rel}: {exc}")
                failed.add(rel)
            op["bytes_base"] += size
            op["done"] += 1
        if not skipped and not op["cancel"]:  # ما وصل إلى كل الأماكن هو مرجع «الحذف» في المرة القادمة
            prev_all[gid] = {rel: v[2] for rel, v in best.items() if rel not in failed}
            _save_prev(prev_all)
        tops = []
        for rel, i, j, size, mt in plan_all:
            top = rel.split("/")[0] if "/" in rel else ""
            if top and top not in tops and rel not in failed:
                tops.append(top)
        st["result"] = f"{len(best)} ملف · نُسخ {copied}" + (" · في: " + "، ".join(tops[:4]) + (f" و{len(tops) - 4} أخرى" if len(tops) > 4 else "") if tops else "") + (f" · حُذف {deleted}" if deleted else "") + (f" · {len(errors)} فشل" if errors else "") + (f" · غير متصل: {len(skipped)}" if skipped else "")
        op["detail"] = st["result"]
        op["state"] = "done" if not errors or copied else "error"
        st["ok"] = not errors
        st["copied"], st["nerr"], st["planned"] = copied, len(errors), len(plan)
    except Exception as exc:
        st["result"] = str(exc)
        st["retry"] = time.time() + 120  # لا إعادة فورية عند الفشل
        st["ok"] = False
        op["state"] = "error"
        op["errors"].append(str(exc))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        try:
            memo_all = _load_memo()
            for x in locs:
                if getattr(x, "kind", "") == "ios":
                    memo_all[f"{gid}|{x.udid}|{x.path}"] = x.memo
            (GROUPS.parent / ".sync_ios_memo.json").write_text(json.dumps(memo_all, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        _history(gid, g["name"], st, time.time() - t_start)
        op["current"] = ""
        op["ended"] = time.time()
        M.fileops.persist(op)
        st["running"] = False
        with LOCK:
            all_g = groups()
            for x in all_g:
                if x["id"] == gid:
                    x["last"] = time.time()
                    x["result"] = st["result"]
                    x["ok"] = st.get("ok")
            _save(all_g)


_FP = {}  # gid -> {"fp", "dirty"}


def _missing(g):
    """أسماء الأماكن غير المتاحة الآن (قرص غير موصول، جهاز غائب/مقفل)."""
    out = []
    for l in g["locations"]:
        try:
            Loc(l)
        except Exception:
            out.append(l.get("label") or l["root"] or "الهاتف")
    return out


def _fingerprint(g):
    """بصمة رخيصة لأماكن الكمبيوتر والأقراص: (عدد، أحدث تعديل، مجموع الأحجام) بسقف عدد وزمن."""
    fp, t0, n = [], time.time(), 0
    for l in g["locations"]:
        if l["kind"] != "local" or l["root"].startswith("rc:"):
            continue
        try:
            base = Path(M.cloud_resolve(l["root"], l["path"])[1])
        except Exception:
            continue
        cnt = mx = tot = 0
        stack = [str(base)]
        while stack and n < 40000 and time.time() - t0 < 4:
            cur = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for e in it:
                        if (e.name in HIDDEN_IGNORE or e.name in SKIP) if g.get("hidden") else (e.name.startswith(".") or e.name in SKIP):
                            continue
                        n += 1
                        try:
                            if e.is_dir(follow_symlinks=False):
                                stack.append(e.path)
                            else:
                                stt = e.stat(follow_symlinks=False)
                                cnt += 1; tot += stt.st_size; mx = max(mx, stt.st_mtime)
                        except OSError:
                            pass
            except OSError:
                pass
        fp.append((cnt, int(mx), tot))
    return fp


def _run_bg(gid):
    run(gid)
    g = next((x for x in groups() if x["id"] == gid), None)
    if g:
        _FP[gid] = {"fp": _fingerprint(g), "dirty": False}  # ما كتبناه نحن لا يُحسب تغييرًا


def _loop():
    while True:
        time.sleep(10)
        try:
            now = time.time()
            for g in groups():
                gid = g["id"]
                st = STATE.setdefault(gid, {})
                if not g["enabled"] or st.get("running") or now < st.get("retry", 0):
                    continue
                missing = _missing(g)
                was = st.get("was_missing", False)
                st["waiting"] = missing
                st["was_missing"] = bool(missing)
                if missing:
                    continue
                trig = None
                if was:
                    trig = "وُصل المكان"
                elif now - (g.get("last") or 0) >= g["every"] * 60:
                    trig = "المدة"
                else:
                    f = _FP.setdefault(gid, {"fp": None, "dirty": False})
                    cur = _fingerprint(g)
                    if f["fp"] is None:
                        f["fp"] = cur
                    elif cur != f["fp"]:
                        f["fp"], f["dirty"] = cur, True  # تغيّر الآن: ننتظر هدوءه عشر ثوانٍ
                    elif f["dirty"]:
                        trig = "تغيّر الملفات"
                if trig:
                    st["trigger"] = trig
                    threading.Thread(target=_run_bg, args=(gid,), daemon=True).start()
        except Exception:
            pass
