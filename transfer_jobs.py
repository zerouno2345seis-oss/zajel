"""نقل وإنقاذ المساحات: تحليل مكان (iCloud، درايف، حساب rclone، قرص) ونقل/نسخ ملفات منه إلى مكان آخر في الخلفية،
مع تحقق (حجم + بصمة للملفات < 200MB) قبل أي حذف للأصل. الحذف دائمًا إلى سلة، وسجلّ يتيح التراجع.
المكان يُوصَف بجذر كما في cloud_resolve («home»، «icloud»، «GoogleDrive-…»، «vol:…»، «rc:<حساب>») + «icloud_all» (كل حاويات iCloud).
حالة المهمة تُحفظ في PB_DATA/transfers/<id>.json فتستأنف بعد إعادة التشغيل."""
from __future__ import annotations

import hashlib
import heapq
import json
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

M = None            # وحدة الخادم (cloud_resolve، cloud_roots، cleaner…) تُضبط بـ init
DATA = Path(os.environ.get("PB_DATA") or Path(__file__).resolve().parent)
JOBS_DIR = DATA / "transfers"
ANALYSIS_DIR = DATA / "space_analysis"
LOCK = threading.RLock()
JOBS: dict[str, dict] = {}
CTRL: dict[str, dict] = {}       # id -> {"pause": Event(set=يعمل), "cancel": bool, "thread": Thread, "proc": Popen}
ANALYSES: dict[str, dict] = {}
ICLOUD_ALL = Path.home() / "Library" / "Mobile Documents"
HASH_LIMIT = 200 * 1024 * 1024
CHUNK = 1024 * 1024
YEAR = 365 * 86400
MAX_ITEMS = 20000
MIN_FREE_LOCAL = 2 * 1024 ** 3   # لا نملأ القرص المحلي: نترك 2GB على الأقل


def init(module, data_dir=None):
    global M, DATA, JOBS_DIR, ANALYSIS_DIR
    M = module
    if data_dir:
        DATA = Path(data_dir)
        JOBS_DIR = DATA / "transfers"
        ANALYSIS_DIR = DATA / "space_analysis"
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    JOBS.clear()
    for p in JOBS_DIR.glob("*.json"):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if j.get("state") in ("running", "paused", "queued"):
            j["state"] = "interrupted"          # كانت تعمل حين أُغلق التطبيق → تُستأنف بزر
        JOBS[j["id"]] = j


# ---------------------------------------------------------------- الأماكن
def _is_rc(root):
    return root.startswith("rc:")


def resolve(root, rel=""):
    """يعيد مسارًا محليًا آمنًا (Path) لجذر محلي. «icloud_all» = ~/Library/Mobile Documents."""
    if ".." in rel.split("/"):
        raise ValueError("مسار غير صالح.")
    if root == "icloud_all":
        base = ICLOUD_ALL.resolve()
        if not base.is_dir():
            raise ValueError("iCloud غير مفعّل على هذا الكمبيوتر.")
        t = (base / rel.lstrip("/")).resolve()
        if t != base and base not in t.parents:
            raise ValueError("مسار خارج المجلد المسموح.")
        return t
    return M.cloud_resolve(root, rel)[1]


def places():
    out = []
    for r in M.cloud_roots():
        if r["id"] in ("uploads",):
            continue
        out.append(r)
    if ICLOUD_ALL.is_dir():
        out.insert(0, {"id": "icloud_all", "group": "cloud", "label": "iCloud (كل الحاويات، مع مجلدات التطبيقات)"})
    return out


def _R():
    import rclone_src
    return rclone_src


# ---------------------------------------------------------------- iCloud: ملفات «مبعدة» (placeholders)
def _placeholder_real(name):
    m = re.fullmatch(r"\.(.+)\.icloud", name)
    return m.group(1) if m else None


def _placeholder_size(p):
    try:
        with open(p, "rb") as f:
            d = plistlib.load(f)
        return int(d.get("NSURLFileSizeKey") or 0)
    except Exception:
        return 0


def _download_icloud(real: Path, size, ctrl, timeout=1800):
    """يطلب تنزيل ملف مبعد من iCloud وينتظر ظهوره. يعيد True عند الجاهزية."""
    if real.exists():
        return True
    ph = real.parent / f".{real.name}.icloud"
    if not ph.exists():
        return False
    subprocess.run(["/usr/bin/brctl", "download", str(real)], capture_output=True, timeout=60)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if real.exists() and not ph.exists():
            return True
        if ctrl.get("cancel"):
            raise _Cancel()
        time.sleep(1.5)
    return real.exists()


class _Cancel(Exception):
    pass


# ---------------------------------------------------------------- التحليل
def _akey(root):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", root)


def analysis(root, refresh=False):
    """يعيد حالة التحليل المخزّنة؛ يبدأ تحليلًا في الخلفية إن لم يوجد أو طُلب التحديث."""
    with LOCK:
        a = ANALYSES.get(root)
        if a and a.get("state") == "running":
            return a
        if not refresh:
            if a:
                return a
            f = ANALYSIS_DIR / (_akey(root) + ".json")
            if f.exists():
                try:
                    a = json.loads(f.read_text(encoding="utf-8"))
                    ANALYSES[root] = a
                    return a
                except Exception:
                    pass
        a = {"root": root, "state": "running", "scanned": 0, "started": time.time()}
        ANALYSES[root] = a
    threading.Thread(target=_analyze_thread, args=(root, a), daemon=True).start()
    return a


def _analyze_thread(root, a):
    try:
        res = _analyze_rc(root, a) if _is_rc(root) else _analyze_local(root, a)
        a.update(res)
        a["state"] = "done"
    except Exception as exc:
        a["state"] = "error"
        a["error"] = str(exc)
    a["ended"] = time.time()
    try:
        (ANALYSIS_DIR / (_akey(root) + ".json")).write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _icloud_category(name):
    """(الرمز، الشرح) لمجلد أعلى في حاويات iCloud."""
    low = name.lower()
    if "photos" in low or "photo" in low:
        return "red", "الصور: لا تُمسّ آليًا أبدًا (تُدار من تطبيق الصور)."
    if "whatsapp" in low:
        return "yellow", "نسخة واتساب الاحتياطية: لا تُنقل يدويًا فتفسد. لتوفير مساحتها: واتساب ← الإعدادات ← الدردشات ← نسخ احتياطي، أو احذفها من إعدادات iCloud."
    if name == "com~apple~CloudDocs":
        return "green", "ملفات iCloud Drive: قابلة للنقل بأمان."
    return "green_old", "مجلد تطبيق: يُنقل القديم من ملفاته فقط (أقدم من سنة)؛ ملفات التطبيق الحيّة لا تُمسّ."


def _analyze_local(root, a):
    base = resolve(root)
    icl = root == "icloud_all"
    now = time.time()
    top = {}
    largest, oldest = [], []         # كومتان صغيرتان (حجم/تاريخ، مسار)
    old_total = {"count": 0, "bytes": 0}
    old_by_top = {}
    total = count = evicted = 0
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        rel_dir = os.path.relpath(dirpath, base)
        topname = "" if rel_dir == "." else rel_dir.split(os.sep)[0]
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if not os.path.isfile(p) and not fn.startswith("."):
                continue
            real = _placeholder_real(fn)
            size, name = st.st_size, fn
            if real:
                size, name, evicted = _placeholder_size(p), real, evicted + 1
            elif fn.startswith(".") and fn in (".DS_Store", ".localized"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), base)
            tn = topname or name
            t = top.setdefault(tn, {"name": tn, "bytes": 0, "files": 0, "is_dir": bool(topname)})
            t["bytes"] += size
            t["files"] += 1
            total += size
            count += 1
            a["scanned"] = count
            mt = st.st_mtime
            if size > 0:
                heapq.heappush(largest, (size, rel))
                if len(largest) > 60:
                    heapq.heappop(largest)
            if not (icl and topname and _icloud_category(topname)[0] in ("red", "yellow")):
                heapq.heappush(oldest, (-mt, rel, size))
                if len(oldest) > 60:
                    heapq.heappop(oldest)
                if now - mt > YEAR:
                    old_total["count"] += 1
                    old_total["bytes"] += size
                    o = old_by_top.setdefault(tn, {"name": tn, "bytes": 0, "files": 0})
                    o["bytes"] += size
                    o["files"] += 1
    tops = sorted(top.values(), key=lambda x: -x["bytes"])
    for t in tops:
        if icl:
            t["cat"], t["note"] = _icloud_category(t["name"])
            if t["name"].startswith("com~apple~") and t["name"] != "com~apple~CloudDocs" and t["cat"] == "green_old":
                t["label"] = t["name"].replace("com~apple~", "تطبيق Apple: ")
        else:
            t["cat"], t["note"] = "green", ""
    res = {"total_bytes": total, "files": count, "evicted": evicted, "top": tops[:200],
           "largest": [{"rel": r, "size": s} for s, r in sorted(largest, reverse=True)],
           "oldest": [{"rel": r, "size": s, "mtime": -m} for m, r, s in sorted(oldest, reverse=True)],
           "older_than_year": old_total, "old_by_top": sorted(old_by_top.values(), key=lambda x: -x["bytes"])[:50]}
    if icl:
        res["notes"] = ["نسخ احتياطية للأجهزة (آيفون…) لا تظهر ملفاتٍ على الماك؛ تُحذف من: إعدادات النظام ← Apple ID ← iCloud ← إدارة المساحة ← النسخ الاحتياطية.",
                        "الصور 🔴 لا يلمسها هذا القسم أبدًا."]
        res["quota"] = _icloud_quota()
    else:
        try:
            du = shutil.disk_usage(base)
            res["disk"] = {"total": du.total, "free": du.free}
        except OSError:
            pass
    return res


def _icloud_quota():
    try:
        out = subprocess.run(["/usr/bin/brctl", "quota"], capture_output=True, text=True, timeout=20).stdout
        m = re.search(r"(\d+)\s+bytes of quota remaining", out)
        return {"remaining": int(m.group(1))} if m else {}
    except Exception:
        return {}


def _analyze_rc(root, a):
    R = _R()
    name = root[3:]
    res = {"total_bytes": 0, "files": 0}
    try:
        ab = json.loads(R._run(["about", "--json", name + ":"], 60) or "{}")
        res["quota"] = {"total": ab.get("total"), "used": ab.get("used"), "free": ab.get("free"), "trashed": ab.get("trashed")}
    except Exception:
        pass
    rows = json.loads(R._run(["lsjson", "-R", "--files-only", "--fast-list", "--drive-export-formats", R.EXPORT, name + ":"], 3600) or "[]")
    from datetime import datetime
    now = time.time()
    top = {}
    largest, oldest = [], []
    old_total = {"count": 0, "bytes": 0}
    old_by_top = {}
    for it in rows:
        size = max(it.get("Size") or 0, 0)
        path = it.get("Path") or it.get("Name")
        try:
            mt = datetime.fromisoformat(it["ModTime"].replace("Z", "+00:00")).timestamp()
        except Exception:
            mt = now
        tn = path.split("/")[0]
        t = top.setdefault(tn, {"name": tn, "bytes": 0, "files": 0, "is_dir": "/" in path, "cat": "green", "note": ""})
        t["bytes"] += size
        t["files"] += 1
        res["total_bytes"] += size
        res["files"] += 1
        a["scanned"] = res["files"]
        if size > 0:
            heapq.heappush(largest, (size, path))
            if len(largest) > 60:
                heapq.heappop(largest)
        heapq.heappush(oldest, (-mt, path, size))
        if len(oldest) > 60:
            heapq.heappop(oldest)
        if now - mt > YEAR:
            old_total["count"] += 1
            old_total["bytes"] += size
            o = old_by_top.setdefault(tn, {"name": tn, "bytes": 0, "files": 0})
            o["bytes"] += size
            o["files"] += 1
    res["top"] = sorted(top.values(), key=lambda x: -x["bytes"])[:200]
    res["largest"] = [{"rel": r, "size": s} for s, r in sorted(largest, reverse=True)]
    res["oldest"] = [{"rel": r, "size": s, "mtime": -m} for m, r, s in sorted(oldest, reverse=True)]
    res["older_than_year"] = old_total
    res["old_by_top"] = sorted(old_by_top.values(), key=lambda x: -x["bytes"])[:50]
    return res


def suggestions(root):
    """اقتراحات جاهزة مشتقة من التحليل المخزّن: عناوين + عناصر + حجم."""
    a = ANALYSES.get(root) or analysis(root)
    if a.get("state") != "done":
        return []
    sug = []
    o = a.get("older_than_year") or {}
    if o.get("bytes"):
        sug.append({"id": "older_year", "title": "انقل الملفات الأقدم من سنة", "bytes": o["bytes"], "files": o["count"],
                    "rule": {"older_than_days": 365}})
    for t in (a.get("top") or [])[:5]:
        if t.get("cat") in ("green",) and t["bytes"] > 100 * 1024 * 1024 and t.get("is_dir"):
            sug.append({"id": "top:" + t["name"], "title": f"انقل مجلد «{t['name']}» كاملًا", "bytes": t["bytes"], "files": t["files"],
                        "rule": {"items": [t["name"]]}})
    return sug


def _collect_old(root, days, limit=MAX_ITEMS):
    """مسارات الملفات الأقدم من days يوم (تستثني الصور وواتساب في iCloud)."""
    cutoff = time.time() - days * 86400
    out = []
    if _is_rc(root):
        R = _R()
        from datetime import datetime
        for it in json.loads(R._run(["lsjson", "-R", "--files-only", "--fast-list", "--drive-export-formats", R.EXPORT, root[3:] + ":"], 3600) or "[]"):
            try:
                mt = datetime.fromisoformat(it["ModTime"].replace("Z", "+00:00")).timestamp()
            except Exception:
                continue
            if mt < cutoff:
                out.append(it.get("Path") or it["Name"])
                if len(out) >= limit:
                    break
        return out
    base = resolve(root)
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        rel_dir = os.path.relpath(dirpath, base)
        if root == "icloud_all" and rel_dir != ".":
            if _icloud_category(rel_dir.split(os.sep)[0])[0] in ("red", "yellow"):
                dirnames[:] = []
                continue
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            name = _placeholder_real(fn) or fn
            if fn in (".DS_Store", ".localized"):
                continue
            if st.st_mtime < cutoff:
                out.append(os.path.relpath(os.path.join(dirpath, name), base))
                if len(out) >= limit:
                    return out
    return out


# ---------------------------------------------------------------- تصفح
def browse(root, rel=""):
    if _is_rc(root):
        d = _R().browse(root, rel)
        return {"root": root, "path": d["path"], "entries": [{"name": e["name"], "path": e["path"], "is_dir": e["is_dir"], "size": e["size"], "mod": e["mod"]} for e in d["entries"]]}
    base = resolve(root, rel)
    root_base = resolve(root)
    entries = []
    for e in sorted(os.scandir(base), key=lambda x: (not x.is_dir(follow_symlinks=False), x.name.casefold())):
        if e.is_symlink() or e.name in (".DS_Store", ".localized"):
            continue
        name, size, evicted = e.name, None, False
        real = _placeholder_real(e.name)
        try:
            st = e.stat(follow_symlinks=False)
        except OSError:
            continue
        isdir = e.is_dir(follow_symlinks=False)
        if real:
            name, size, evicted = real, _placeholder_size(e.path), True
        elif not isdir:
            size = st.st_size
        elif e.name.startswith("."):
            continue
        if name.startswith(".") and not real:
            continue
        entries.append({"name": name, "path": os.path.relpath(os.path.join(base, name), root_base), "is_dir": isdir, "size": size,
                        "mod": int(st.st_mtime * 1000), "evicted": evicted})
    return {"root": root, "path": "" if base == root_base else os.path.relpath(base, root_base), "entries": entries}


# ---------------------------------------------------------------- المهام
def _job_path(jid):
    return JOBS_DIR / f"{jid}.json"


def _save(j):
    with LOCK:
        tmp = _job_path(j["id"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _job_path(j["id"]))


def public(j, files=False):
    d = {k: v for k, v in j.items() if k not in ("files", "ledger", "_last_save")}
    f = j.get("files", [])
    d["counts"] = {s: sum(1 for x in f if x["status"] == s) for s in ("pending", "copied", "verified", "deleted", "failed", "skipped")}
    d["file_total"] = len(f)
    if files:
        d["files"] = f[:3000]
        d["ledger"] = j.get("ledger", [])[-3000:]
    return d


def jobs_list():
    return sorted((public(j) for j in JOBS.values()), key=lambda x: -x.get("created", 0))


def _yellow_red_check(src_root, items, allow_yellow):
    if src_root != "icloud_all":
        return
    for it in items:
        top = it.split("/")[0]
        cat = _icloud_category(top)[0]
        if cat == "red":
            raise ValueError("الصور في iCloud محمية: لا يُنقل منها شيء من هنا.")
        if cat == "yellow" and not allow_yellow:
            raise ValueError(f"«{top}» يحتاج قرارك: انقله فقط بعد تأكيد صريح (نسخة تطبيق لا تعمل بعد نقلها).")


def _expand(src_root, items):
    """يحوّل العناصر (ملفات/مجلدات) إلى قائمة ملفات [{rel, size, mtime}]."""
    out = []
    if _is_rc(src_root):
        R = _R()
        for it in items:
            st = R.stat(src_root, it)
            if st is None:
                continue
            if not st["is_dir"]:
                out.append({"rel": it, "size": max(st.get("size") or 0, 0)})
            else:
                for r in json.loads(R._run(["lsjson", "-R", "--files-only", "--fast-list", "--drive-export-formats", R.EXPORT, R.spec(src_root, it)], 3600) or "[]"):
                    out.append({"rel": it.rstrip("/") + "/" + (r.get("Path") or r["Name"]), "size": max(r.get("Size") or 0, 0)})
            if len(out) > MAX_ITEMS:
                raise ValueError("عدد الملفات كبير جدًا؛ اختر أقل أو قسّمها.")
        return out
    base = resolve(src_root)
    for it in items:
        p = resolve(src_root, it)
        if p == base:
            raise ValueError("لا يمكن نقل الجذر كله؛ اختر مجلدات داخله.")
        if p.is_file():
            out.append({"rel": it, "size": p.stat().st_size})
            continue
        if not p.is_dir():                       # قد يكون ملفًا مبعدًا
            ph = p.parent / f".{p.name}.icloud"
            if ph.exists():
                out.append({"rel": it, "size": _placeholder_size(ph)})
            continue
        for dirpath, dirnames, filenames in os.walk(p, followlinks=False):
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
            for fn in filenames:
                if fn in (".DS_Store", ".localized"):
                    continue
                fp = os.path.join(dirpath, fn)
                real = _placeholder_real(fn)
                try:
                    size = _placeholder_size(fp) if real else os.lstat(fp).st_size
                except OSError:
                    continue
                out.append({"rel": os.path.relpath(os.path.join(dirpath, real or fn), base), "size": size})
                if len(out) > MAX_ITEMS:
                    raise ValueError("عدد الملفات كبير جدًا؛ اختر أقل أو قسّمها.")
    return out


def create(body):
    src_root = str(body.get("src_root") or "")
    dst_root = str(body.get("dst_root") or "")
    dst_dir = str(body.get("dst_dir") or "").strip("/")
    mode = body.get("mode", "copy")
    if mode not in ("copy", "move"):
        raise ValueError("نمط غير معروف.")
    if not src_root or not dst_root:
        raise ValueError("اختر المصدر والوجهة.")
    if ".." in dst_dir.split("/"):
        raise ValueError("مسار الوجهة غير صالح.")
    items = [str(x).strip("/") for x in (body.get("items") or []) if str(x).strip("/")]
    rule = body.get("rule") or {}
    if rule.get("older_than_days"):
        items = _collect_old(src_root, int(rule["older_than_days"]))
    if not items:
        raise ValueError("لم تختر شيئًا.")
    _yellow_red_check(src_root, items, bool(body.get("allow_yellow")))
    if not _is_rc(dst_root):
        resolve(dst_root, dst_dir)               # تحقق أن الوجهة صالحة
    if src_root == dst_root and (dst_dir == "" or any(dst_dir == i or dst_dir.startswith(i + "/") for i in items)):
        raise ValueError("الوجهة داخل المصدر نفسه.")
    files = _expand(src_root, items)
    if not files:
        raise ValueError("لا ملفات في الاختيار.")
    j = {"id": uuid.uuid4().hex[:10], "created": time.time(), "state": "queued", "mode": mode,
         "keep_tree": bool(rule.get("older_than_days")),
         "src_root": src_root, "dst_root": dst_root, "dst_dir": dst_dir, "items": items[:500], "n_items": len(items),
         "title": ("نقل " if mode == "move" else "نسخ ") + (items[0] if len(items) == 1 else f"{len(items)} عنصر"),
         "bytes_total": sum(f["size"] for f in files), "bytes_done": 0, "speed": 0, "eta": None, "current": "",
         "files": [dict(f, status="pending", error="", dst_rel="") for f in files], "ledger": [], "report": None, "freed": 0}
    with LOCK:
        JOBS[j["id"]] = j
    _save(j)
    _launch(j)
    return public(j)


def _launch(j):
    ctrl = {"pause": threading.Event(), "cancel": False, "proc": None}
    ctrl["pause"].set()
    CTRL[j["id"]] = ctrl
    j["state"] = "running"
    j.pop("error", None)
    _save(j)
    t = threading.Thread(target=_run, args=(j, ctrl), daemon=True)
    ctrl["thread"] = t
    t.start()


def _alive(jid):
    c = CTRL.get(jid)
    return bool(c and c.get("thread") and c["thread"].is_alive())


def resume(jid):
    j = _get(jid)
    if _alive(jid):
        raise ValueError("المهمة تعمل بالفعل.")
    if j["state"] == "done":
        raise ValueError("المهمة منتهية.")
    _launch(j)
    return public(j)


def retry_failed(jid):
    j = _get(jid)
    if _alive(jid):
        raise ValueError("المهمة تعمل؛ انتظر انتهاءها أو أوقفها.")
    n = 0
    for f in j["files"]:
        if f["status"] == "failed":
            f["status"], f["error"] = "pending", ""
            n += 1
    if not n:
        raise ValueError("لا ملفات فاشلة.")
    j["report"] = None
    _launch(j)
    return public(j)


def pause(jid, paused=True):
    j = _get(jid)
    c = CTRL.get(jid)
    if not c or not _alive(jid):
        raise ValueError("المهمة ليست قيد العمل.")
    if paused:
        c["pause"].clear()
        j["state"] = "paused"
    else:
        c["pause"].set()
        j["state"] = "running"
    _save(j)
    return public(j)


def cancel(jid):
    j = _get(jid)
    c = CTRL.get(jid)
    if c and _alive(jid):
        c["cancel"] = True
        c["pause"].set()
        p = c.get("proc")
        try:
            if p:
                p.terminate()
        except Exception:
            pass
    else:
        j["state"] = "cancelled"
        _save(j)
    return public(j)


def _get(jid):
    j = JOBS.get(jid)
    if not j:
        raise ValueError("مهمة غير معروفة.")
    return j


def job(jid):
    return public(_get(jid), files=True)


# ---------------------------------------------------------------- التنفيذ
def _sha(path, ctrl=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _wait(ctrl):
    ctrl["pause"].wait()
    if ctrl["cancel"]:
        raise _Cancel()


def _unique_dst_rel(j, f, taken):
    """اسم الوجهة النسبي لملف: يحافظ على بنية المجلد، ويضيف رقمًا عند التعارض مع ملف مختلف."""
    rel = f["rel"]
    if j.get("keep_tree"):
        return "/".join(x for x in (j["dst_dir"], rel) if x)
    items = j["items"]
    # العنصر المختار هو جذر البنية: ننقل «مجلد/…» محتفظين باسم المجلد
    base_name = rel
    for it in items:
        if rel == it or rel.startswith(it + "/"):
            parent = it.rsplit("/", 1)[0] if "/" in it else ""
            base_name = rel[len(parent) + 1:] if parent else rel
            break
    return "/".join(x for x in (j["dst_dir"], base_name) if x)


def _dst_exists(j, dst_rel):
    """(موجود؟، حجم، بصمة md5/None)"""
    if _is_rc(j["dst_root"]):
        R = _R()
        try:
            d = json.loads(R._run(["lsjson", "--stat", "--hash", "--drive-export-formats", R.EXPORT, R.spec(j["dst_root"], dst_rel)], 60))
        except ValueError:
            return False, None, None
        if d.get("IsDir"):
            return True, -1, None
        return True, d.get("Size"), (d.get("Hashes") or {})
    p = resolve(j["dst_root"], str(Path(dst_rel).parent) if "/" in dst_rel else "") / Path(dst_rel).name
    if not p.exists():
        return False, None, None
    return True, p.stat().st_size if p.is_file() else -1, None


def _local_hash_for(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _run(j, ctrl):
    tmpdir = Path(tempfile.mkdtemp(prefix="zajel-xfer-", dir=str(DATA)))
    t0 = time.time()
    base_done = sum(f["size"] for f in j["files"] if f["status"] in ("verified", "deleted", "skipped"))
    j["bytes_done"] = base_done
    last_save = 0.0
    try:
        for f in j["files"]:
            if f["status"] in ("deleted", "skipped"):
                continue
            if f["status"] == "failed":
                continue
            try:
                _wait(ctrl)
                j["current"] = f["rel"]
                _process(j, f, ctrl, tmpdir)
            except _Cancel:
                raise
            except Exception as exc:
                f["status"], f["error"] = "failed", str(exc)[:300]
            done = sum(x["size"] for x in j["files"] if x["status"] in ("verified", "deleted", "skipped"))
            j["bytes_done"] = done
            el = max(time.time() - t0, 0.5)
            j["speed"] = int((done - base_done) / el)
            rem = j["bytes_total"] - done
            j["eta"] = int(rem / j["speed"]) if j["speed"] > 0 else None
            if time.time() - last_save > 1.5:
                _save(j)
                last_save = time.time()
        j["state"] = "done"
        _cleanup_dirs(j)
        _finish_report(j)
    except _Cancel:
        j["state"] = "cancelled"
        _finish_report(j)
    except Exception as exc:
        j["state"] = "error"
        j["error"] = str(exc)
    finally:
        j["current"] = ""
        j["speed"] = 0
        j["eta"] = None
        shutil.rmtree(tmpdir, ignore_errors=True)
        _save(j)


def _progress(j, f, ctrl, base):
    """مؤدّي تقدم لملف جارٍ نقله: يضيف إلى bytes_done جزءًا من الملف."""
    def cb(b):
        j["bytes_done"] = base + min(int(b), f["size"])
        if not ctrl["pause"].is_set():
            ctrl["pause"].wait()
    return cb


def _process(j, f, ctrl, tmpdir):
    src_root, dst_root = j["src_root"], j["dst_root"]
    move = j["mode"] == "move"
    base_done = j["bytes_done"]
    if not f["dst_rel"]:
        f["dst_rel"] = _unique_dst_rel(j, f, None)
    # 1) مصدر محلي جاهز؟ (iCloud المبعد → تنزيل)
    src_local = None
    staged = None
    if _is_rc(src_root):
        if f["status"] == "pending":
            staged = tmpdir / uuid.uuid4().hex
            if shutil.disk_usage(tmpdir).free < f["size"] + MIN_FREE_LOCAL:
                raise ValueError("لا مساحة محلية كافية لتنزيل هذا الملف مؤقتًا.")
            _R().download(src_root, f["rel"], staged, on_proc=lambda p: ctrl.__setitem__("proc", p))
            src_local = staged
    else:
        sp = resolve(src_root, "") / f["rel"]
        if not sp.exists() and f["status"] == "pending":
            if not (sp.parent / f".{sp.name}.icloud").exists():
                raise ValueError("الملف لم يعد موجودًا في المصدر.")
            if shutil.disk_usage(sp.parent).free < f["size"] + MIN_FREE_LOCAL:
                raise ValueError("لا مساحة محلية كافية لتنزيل ملف iCloud هذا.")
            if not _download_icloud(sp, f["size"], ctrl):
                raise ValueError("تعذّر تنزيل الملف من iCloud.")
        src_local = sp
    try:
        # 2) نسخ إلى الوجهة (إن لم يكن منسوخًا سابقًا)
        if f["status"] == "pending":
            ex, size, hashes = _dst_exists(j, f["dst_rel"])
            if ex and size == f["size"] and _same_content(j, f, src_local, hashes):
                pass                                    # موجود بالمحتوى نفسه (استئناف) فلا نعيد النسخ
            else:
                if ex:
                    f["dst_rel"] = _free_name(j, f["dst_rel"])
                _copy(j, f, src_local, ctrl, tmpdir, base_done)
            f["status"] = "copied"
            _save(j)
        # 3) تحقق
        if f["status"] == "copied":
            _verify(j, f, src_local, ctrl, tmpdir)
            f["status"] = "verified"
            j["ledger"].append({"t": time.time(), "op": "copy", "src": f["rel"], "dst": f["dst_rel"], "size": f["size"]})
        # 4) حذف الأصل (نقل فقط) بعد التحقق
        if move and f["status"] == "verified":
            _remove_src(j, f, src_local if not staged else None, ctrl)
            f["status"] = "deleted"
            j["freed"] += f["size"]
    finally:
        if staged and staged.exists():
            try:
                staged.unlink()
            except OSError:
                pass


def _same_content(j, f, src_local, hashes):
    """هل ملف الوجهة الموجود مطابق للمصدر؟ (حجم متساوٍ سلفًا؛ هنا البصمة إن توفرت)."""
    if f["size"] > HASH_LIMIT:
        return True
    if src_local is None or not Path(src_local).exists():
        return False
    if _is_rc(j["dst_root"]):
        h = hashes or {}
        for algo in ("md5", "sha1", "sha256"):
            if h.get(algo):
                return _local_hash_for(src_local, algo) == h[algo]
        return True
    dst = resolve(j["dst_root"], "") / f["dst_rel"]
    try:
        return _sha(src_local) == _sha(dst)
    except OSError:
        return False


def _free_name(j, dst_rel):
    stem, ext = os.path.splitext(dst_rel)
    i = 2
    while True:
        cand = f"{stem} {i}{ext}"
        if not _dst_exists(j, cand)[0]:
            return cand
        i += 1


def _copy(j, f, src_local, ctrl, tmpdir, base_done):
    if _is_rc(j["dst_root"]):
        if src_local is None or not Path(src_local).exists():
            raise ValueError("المصدر المحلي غير متاح للرفع.")
        _R().upload(src_local, j["dst_root"], f["dst_rel"], progress=_progress(j, f, ctrl, base_done), on_proc=lambda p: ctrl.__setitem__("proc", p))
        return
    dst = resolve(j["dst_root"], "") / f["dst_rel"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(dst.parent).free < f["size"] + 256 * 1024 * 1024:
        raise ValueError("لا مساحة كافية في الوجهة.")
    part = dst.with_name(dst.name + ".zajel-part")
    h = hashlib.sha256()
    n = 0
    try:
        with open(src_local, "rb") as fi, open(part, "wb") as fo:
            while True:
                _wait(ctrl)
                b = fi.read(CHUNK)
                if not b:
                    break
                fo.write(b)
                h.update(b)
                n += len(b)
                j["bytes_done"] = base_done + min(n, f["size"])
            fo.flush()
            os.fsync(fo.fileno())
        try:
            os.utime(part, (os.stat(src_local).st_atime, os.stat(src_local).st_mtime))
        except OSError:
            pass
        f["src_sha"] = h.hexdigest() if n <= HASH_LIMIT else ""
        os.replace(part, dst)
    except BaseException:
        try:
            part.unlink()
        except OSError:
            pass
        raise


def _verify(j, f, src_local, ctrl, tmpdir):
    """الحجم دائمًا، والبصمة للملفات < 200MB. أي اختلاف ← فشل (ولا يُحذف الأصل)."""
    small = f["size"] <= HASH_LIMIT
    if _is_rc(j["dst_root"]):
        ex, size, hashes = _dst_exists(j, f["dst_rel"])
        if not ex or size != f["size"]:
            raise ValueError(f"فشل التحقق: حجم الوجهة {size} ≠ {f['size']}.")
        if small and src_local is not None and Path(src_local).exists():
            for algo in ("md5", "sha1", "sha256"):
                if (hashes or {}).get(algo):
                    if _local_hash_for(src_local, algo) != hashes[algo]:
                        raise ValueError("فشل التحقق: بصمة الوجهة تخالف الأصل.")
                    break
        return
    dst = resolve(j["dst_root"], "") / f["dst_rel"]
    if not dst.is_file() or dst.stat().st_size != f["size"]:
        raise ValueError("فشل التحقق: حجم الوجهة يخالف الأصل.")
    if small:
        ref = f.get("src_sha") or (_sha(src_local) if src_local is not None and Path(src_local).exists() else "")
        if ref and _sha(dst) != ref:
            raise ValueError("فشل التحقق: بصمة الوجهة تخالف الأصل.")


def _trash_path(path: Path) -> Path:
    """مسار سلة المستخدم (أو سلة القرص). iCloud: الملف المنقول إلى سلة الماك يغادر iCloud فتتحرر مساحته."""
    try:
        d = M.cleaner.trash_dir_for(path)
    except Exception:
        d = Path.home() / ".Trash"
        d.mkdir(exist_ok=True)
    dest = d / path.name
    i = 2
    while dest.exists():
        dest = d / f"{path.stem} {i}{path.suffix}"
        i += 1
    return dest


def _remove_src(j, f, src_local, ctrl):
    if _is_rc(j["src_root"]):
        _R().remove(j["src_root"], f["rel"], False)
        j["ledger"].append({"t": time.time(), "op": "delete_remote", "src": f["rel"], "note": "في سلة الخدمة السحابية", "size": f["size"]})
        return
    p = Path(src_local) if src_local else resolve(j["src_root"], "") / f["rel"]
    if not p.exists():
        return
    dest = _trash_path(p)
    shutil.move(str(p), str(dest))
    j["ledger"].append({"t": time.time(), "op": "trash", "src": f["rel"], "trash": str(dest), "size": f["size"]})


def _cleanup_dirs(j):
    """بعد نقل ناجح: يزيل المجلدات الفارغة المتبقية من العناصر المنقولة (rmdir فقط، لا حذف محتوى)."""
    if j["mode"] != "move" or _is_rc(j["src_root"]):
        return
    if any(f["status"] != "deleted" for f in j["files"]):
        return
    base = resolve(j["src_root"], "")
    for it in j["items"]:
        p = base / it
        if p.is_dir():
            for dirpath, _d, _f in os.walk(p, topdown=False):
                try:
                    os.rmdir(dirpath)
                except OSError:
                    pass


def _finish_report(j):
    f = j["files"]
    placed = {}
    for x in f:
        if x["status"] in ("verified", "deleted"):
            top = x["dst_rel"]
            placed[x["rel"]] = top
    j["ended"] = time.time()
    j["report"] = {
        "freed": j.get("freed", 0), "copied": sum(1 for x in f if x["status"] in ("verified", "deleted")),
        "failed": [{"rel": x["rel"], "error": x["error"]} for x in f if x["status"] == "failed"][:200],
        "destination": f"{j['dst_root']}:/{j['dst_dir']}".rstrip("/"),
        "bytes": sum(x["size"] for x in f if x["status"] in ("verified", "deleted")),
        "where": [{"from": i, "to": "/".join(x for x in (j["dst_dir"], i.rsplit("/", 1)[-1]) if x)} for i in j["items"][:200]],
        "note": "الملفات المحذوفة من المصدر في سلة الماك (أو سلة الخدمة السحابية) ويمكن استرجاعها." if j["mode"] == "move" else "",
    }


# ---------------------------------------------------------------- التراجع
def undo(jid):
    """يعيد من السلة ما حذفه النقل إلى مكانه الأصلي (نسخ الوجهة تبقى). لا يعمل لما حُذف من سحابة."""
    j = _get(jid)
    if _alive(jid):
        raise ValueError("أوقف المهمة أولًا.")
    base = resolve(j["src_root"], "") if not _is_rc(j["src_root"]) else None
    restored = skipped = 0
    for e in j.get("ledger", []):
        if e.get("op") != "trash" or e.get("undone"):
            continue
        t = Path(e["trash"])
        if base is None or not t.exists():
            skipped += 1
            continue
        orig = base / e["src"]
        if orig.exists():
            skipped += 1
            continue
        orig.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(t), str(orig))
        e["undone"] = True
        restored += 1
        for f in j["files"]:
            if f["rel"] == e["src"] and f["status"] == "deleted":
                f["status"] = "verified"
                j["freed"] = max(0, j["freed"] - f["size"])
    _save(j)
    return {"restored": restored, "skipped": skipped, "job": public(j)}


# ---------------------------------------------------------------- تنبيه المساحة
def space_alert(threshold_gb=2.0):
    """تحذير حين تقلّ مساحة iCloud المتبقية. التوصيل بتيليجرام يتولاه غيري."""
    q = _icloud_quota()
    rem = q.get("remaining")
    if rem is None:
        return {"alert": False, "known": False, "message": ""}
    gb = rem / 1024 ** 3
    if gb < threshold_gb:
        return {"alert": True, "known": True, "remaining": rem,
                "message": f"⚠️ مساحة iCloud شبه ممتلئة: المتبقي {gb:.2f} جيجابايت. افتح «نقل وإنقاذ المساحات» لنقل ما يمكن نقله."}
    return {"alert": False, "known": True, "remaining": rem, "message": ""}


# ---------------------------------------------------------------- واجهة HTTP
def http_get(path, query):
    q = lambda k, d="": (query.get(k) or [d])[0]
    if path == "/api/rescue/places":
        return {"places": places()}
    if path == "/api/rescue/analysis":
        a = analysis(q("root"), q("refresh") == "1")
        out = dict(a)
        out["suggestions"] = suggestions(q("root")) if a.get("state") == "done" else []
        return out
    if path == "/api/rescue/browse":
        return browse(q("root"), q("path"))
    if path == "/api/rescue/jobs":
        return {"jobs": jobs_list()}
    if path == "/api/rescue/job":
        return job(q("id"))
    if path == "/api/rescue/alert":
        return space_alert()
    raise ValueError("مسار غير معروف.")


def http_post(path, body):
    if path == "/api/rescue/start":
        return create(body)
    jid = str(body.get("id", ""))
    if path == "/api/rescue/pause":
        return pause(jid, bool(body.get("paused", True)))
    if path == "/api/rescue/cancel":
        return cancel(jid)
    if path == "/api/rescue/resume":
        return resume(jid)
    if path == "/api/rescue/retry":
        return retry_failed(jid)
    if path == "/api/rescue/undo":
        return undo(jid)
    if path == "/api/rescue/forget":
        j = _get(jid)
        if _alive(jid):
            raise ValueError("أوقف المهمة أولًا.")
        JOBS.pop(jid, None)
        try:
            _job_path(jid).unlink()
        except OSError:
            pass
        return {"ok": True}
    raise ValueError("مسار غير معروف.")
