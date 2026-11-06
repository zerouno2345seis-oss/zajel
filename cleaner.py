"""أدوات تحليل المجلدات وتنظيفها: المساحة، المكرر، الكاش، الكبير، الفارغ.
كل الفحوصات للقراءة فقط. الحذف لا يتم إلا بطلب منفصل ومن قائمة نتائج فحص سابق."""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import heapq
import os
import shutil
import subprocess
import threading
import time
import json
import re
import uuid
from collections import Counter
from pathlib import Path

HOME = Path.home()
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()
LOG = Path(os.environ.get("PB_DATA") or Path(__file__).resolve().parent) / "cleaning.log"

TYPES = {
    "صور": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff", ".raw", ".dng", ".svg", ".psd"},
    "فيديو": {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".3gp", ".wmv"},
    "صوت": {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".amr"},
    "مستندات": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".pages", ".numbers", ".key", ".csv", ".rtf", ".epub"},
    "أرشيف": {".zip", ".rar", ".7z", ".tar", ".gz", ".dmg", ".iso", ".pkg", ".xip"},
    "برمجة": {".py", ".js", ".ts", ".java", ".kt", ".swift", ".c", ".h", ".cpp", ".html", ".css", ".json", ".xml", ".sh", ".apk", ".aab"},
}
SKIP_DIR_NAMES = {"node_modules", ".git", ".Trash", "Library", ".venv", "venv", "__pycache__", ".gradle", ".npm", ".cache", ".Spotlight-V100", ".fseventsd", ".Trashes", "System Volume Information"}
SKIP_SUFFIX = (".app", ".photoslibrary", ".fcpbundle", ".sparsebundle", ".xcodeproj", ".framework", ".bundle", ".imovielibrary")


# ---------------- قواعد الاحتفاظ (أي نسخة تُبقى) ----------------
RULES_FILE = Path(os.environ.get("PB_DATA") or Path(__file__).resolve().parent) / ".clean_rules.json"
KEEP_CHOICES = {"newest": "الأحدث", "oldest": "الأقدم", "largest": "الأكبر حجمًا", "smallest": "الأصغر حجمًا",
                "highest_res": "الأعلى دقة (للصور)", "shortest_path": "الأقصر مسارًا", "longest_path": "الأطول مسارًا"}
DEFAULT_RULES = {"keep": ["oldest"], "prefer_dirs": [], "avoid_dirs": ["downloads", ".trash", "trash", "tmp", "temp", "cache"], "prefer_clean_names": True}
_COPY_RE = re.compile(r"(\(\d+\)|[\s_-]copy\b|\bcopy of\b|\bcopia\b|نسخة|[\s_-]\d{1,2}$)", re.I)


def load_rules():
    try:
        d = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    return {**DEFAULT_RULES, **{k: v for k, v in d.items() if k in DEFAULT_RULES}}


def save_rules(d):
    keep = [k for k in (d.get("keep") or []) if k in KEEP_CHOICES][:7]
    clean = lambda lst: [str(x).strip()[:200] for x in (lst or []) if str(x).strip()][:20]
    rules = {"keep": keep, "prefer_dirs": clean(d.get("prefer_dirs")), "avoid_dirs": clean(d.get("avoid_dirs")), "prefer_clean_names": bool(d.get("prefer_clean_names"))}
    RULES_FILE.write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")
    return rules


def rank_key(f, rules):
    path = f["path"].lower()
    comps = [p for p in path.replace("\\", "/").split("/") if p]
    avoid = 1 if any(a.lower() in comps or a.lower() in path for a in rules["avoid_dirs"]) else 0
    pref = min([i for i, d in enumerate(rules["prefer_dirs"]) if d.lower() in path] or [999])
    dirty = 1 if rules["prefer_clean_names"] and _COPY_RE.search(os.path.splitext(os.path.basename(path))[0]) else 0
    crit = []
    for k in rules["keep"]:
        crit.append({"newest": -f.get("mtime", 0), "oldest": f.get("mtime", 0), "largest": -(f.get("size") or 0), "smallest": f.get("size") or 0,
                     "highest_res": -((f.get("w") or 0) * (f.get("h") or 0)), "shortest_path": len(path), "longest_path": -len(path)}[k])
    return (avoid, pref, dirty, *crit)


def apply_rules(groups):
    """يرتّب ملفات كل مجموعة بحسب القواعد؛ الأول هو الذي يُبقى. ويكتب سبب الاختيار."""
    rules = load_rules()
    labels = ["المجلد ليس من المرفوضة", "المجلد المفضّل", "الاسم النظيف"] + [KEEP_CHOICES[k] for k in rules["keep"]]
    for g in groups:
        files = g["files"]
        files.sort(key=lambda f: rank_key(f, rules))
        reason = "الأول في الترتيب"
        if len(files) > 1:
            a, b = rank_key(files[0], rules), rank_key(files[1], rules)
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    reason = labels[i] if i < len(labels) else "ترتيب القواعد"
                    break
        g["keep_reason"] = reason
    return groups


class Cancelled(Exception):
    pass


def category(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    for k, v in TYPES.items():
        if ext in v:
            return k
    return "أخرى"


def new_job(kind: str, target: str) -> dict:
    job = {"id": uuid.uuid4().hex[:10], "kind": kind, "target": target, "state": "running", "progress": "يبدأ…", "scanned": 0,
           "result": None, "error": "", "cancel": False, "allowed": set(), "perm_ok": set(), "started": time.time()}
    with LOCK:
        JOBS[job["id"]] = job
        now = time.time()
        for k in [k for k, j in JOBS.items() if j.get("keep") and now - j["started"] > 6 * 3600]:
            JOBS.pop(k, None)
        loose = [k for k in sorted(JOBS, key=lambda x: JOBS[x]["started"]) if not JOBS[k].get("keep")]
        for k in loose[:-12]:
            JOBS.pop(k, None)
    if kind in KIND_AR:
        import history
        history.watch("clean", job, lambda j: KIND_AR[j["kind"]] + " — " + str(j["target"])[-60:], lambda j: {"kind": j["kind"], "target": j["target"]},
                      lambda j: {"kind": j["kind"], "target": j["target"], "result": j["result"], "allowed": sorted(j["allowed"]), "perm_ok": sorted(j["perm_ok"]),
                                 "base": j.get("base"), "serial": j.get("serial")} if j.get("result") is not None else None)
    return job


def restore(payload: dict) -> dict:
    """يعيد نتيجة تنظيف محفوظة كمهمة منتهية حتى تعمل معاينتها وحذفها كما لو كانت جديدة."""
    job = {"id": uuid.uuid4().hex[:10], "kind": payload["kind"], "target": payload["target"], "state": "done", "progress": "اكتمل (نتيجة محفوظة)", "scanned": 0,
           "result": payload["result"], "error": "", "cancel": False, "allowed": set(payload.get("allowed") or []), "perm_ok": set(payload.get("perm_ok") or []),
           "started": time.time(), "keep": True}
    for k in ("base", "serial"):
        if payload.get(k):
            job[k] = payload[k]
    with LOCK:
        JOBS[job["id"]] = job
    return job


def public(job: dict) -> dict:
    return {"id": job["id"], "kind": job["kind"], "state": job["state"], "progress": job["progress"], "scanned": job["scanned"],
            "result": job["result"], "error": job["error"], "seconds": round(time.time() - job["started"], 1)}


def check(job):
    if job["cancel"]:
        raise Cancelled()


CLOUD_DIR_NAMES = {"CloudStorage", "Mobile Documents", "Volumes"}   # سحابات/شبكات: قراءتها تُنزّل الملفات أو تتجمّد
SF_DATALESS = 0x40000000   # ملف في iCloud لم يُنزَّل بعد: قراءته تبدأ تنزيله فتتجمّد العملية


def walk(job, top: Path, skip_special=True, include_hidden=True):
    """يمرّ على الملفات (بلا روابط رمزية، وبلا مغادرة قرص المجلد المختار، وبلا مجلدات السحابة). يعيد (مسار، stat)."""
    try:
        root_dev = os.stat(top).st_dev
    except OSError:
        root_dev = None
    stack = [top]
    last = 0.0
    while stack:
        check(job)
        d = stack.pop()
        now = time.time()
        if now - last > 0.4:
            last = now
            job["beat"] = now
            job["progress"] = f"فُحص {job['scanned']:,} ملف · {d.name or str(d)[:40]}"
        try:
            it = os.scandir(d)
        except OSError:
            job.setdefault("skipped", 0)
            job["skipped"] += 1
            continue
        with it:
            for e in it:
                try:
                    if e.is_symlink():
                        continue
                    name = e.name
                    if e.is_dir(follow_symlinks=False):
                        if name in CLOUD_DIR_NAMES:
                            continue
                        if skip_special and (name in SKIP_DIR_NAMES or name.endswith(SKIP_SUFFIX)):
                            continue
                        if not include_hidden and name.startswith("."):
                            continue
                        if root_dev is not None and e.stat(follow_symlinks=False).st_dev != root_dev:
                            continue
                        stack.append(Path(e.path))
                    elif e.is_file(follow_symlinks=False):
                        if not include_hidden and name.startswith("."):
                            continue
                        st = e.stat(follow_symlinks=False)
                        if getattr(st, "st_flags", 0) & SF_DATALESS:
                            continue
                        job["scanned"] += 1
                        yield Path(e.path), st
                except OSError:
                    continue


# ---------------- تحليل المساحة ----------------
def analyze(job, target: Path):
    total = files = 0
    types: dict[str, list[int]] = {}
    biggest: list = []
    children = []
    try:
        entries = list(os.scandir(target))
    except OSError as exc:
        raise ValueError(f"تعذّر فتح المجلد: {exc}")
    loose = 0
    for e in entries:
        check(job)
        try:
            if e.is_symlink():
                continue
            if e.is_dir(follow_symlinks=False):
                sz = n = 0
                for p, st in walk(job, Path(e.path), skip_special=False):
                    sz += st.st_size
                    n += 1
                    t = types.setdefault(category(p.name), [0, 0]); t[0] += st.st_size; t[1] += 1
                    if len(biggest) < 30:
                        heapq.heappush(biggest, (st.st_size, str(p), st.st_mtime))
                    elif st.st_size > biggest[0][0]:
                        heapq.heapreplace(biggest, (st.st_size, str(p), st.st_mtime))
                children.append({"name": e.name, "is_dir": True, "size": sz, "files": n})
                total += sz; files += n
            elif e.is_file(follow_symlinks=False):
                st = e.stat(follow_symlinks=False)
                children.append({"name": e.name, "is_dir": False, "size": st.st_size, "files": 1})
                total += st.st_size; files += 1; loose += 1
                t = types.setdefault(category(e.name), [0, 0]); t[0] += st.st_size; t[1] += 1
                heapq.heappush(biggest, (st.st_size, e.path, st.st_mtime))
                job["scanned"] += 1
        except OSError:
            continue
    children.sort(key=lambda c: -c["size"])
    top = sorted(biggest, reverse=True)[:30]
    for _s, pth, _m in top:
        job["allowed"].add(pth)
    return {"total": total, "files": files, "children": children[:80],
            "types": [{"name": k, "size": v[0], "count": v[1]} for k, v in sorted(types.items(), key=lambda kv: -kv[1][0])],
            "biggest": [{"path": pth, "size": s, "mtime": int(m * 1000)} for s, pth, m in top], "skipped": job.get("skipped", 0)}


# ---------------- المكررات ----------------
def hash_part(path: str, size: int = 65536) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        h.update(fh.read(size))
    return h.hexdigest()


def hash_full(job, path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            check(job)
            h.update(chunk)
    return h.hexdigest()


def duplicates(job, target: Path, min_size: int):
    by_size: dict[int, list[tuple[str, float]]] = {}
    seen = set()
    for p, st in walk(job, target, skip_special=True, include_hidden=False):
        if st.st_size < min_size:
            continue
        key = (st.st_dev, st.st_ino)
        if key in seen:
            continue
        seen.add(key)
        by_size.setdefault(st.st_size, []).append((str(p), st.st_mtime))
    cands = {s: v for s, v in by_size.items() if len(v) > 1}
    del by_size, seen
    flat = [(size, pth, mt) for size, items in cands.items() for pth, mt in items]
    total_files = len(flat)
    job["progress"] = f"مقارنة سريعة لـ {total_files:,} ملف محتمل التكرار…"
    workers = min(8, (os.cpu_count() or 4))

    def safe_part(rec):
        if job["cancel"]:
            return None
        try:
            return hash_part(rec[1])
        except OSError:
            return None

    part: dict[tuple, list] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for n, (rec, h) in enumerate(zip(flat, pool.map(safe_part, flat)), 1):
            check(job)
            if h:
                part.setdefault((rec[0], h), []).append((rec[1], rec[2]))
            if n % 200 == 0:
                job["progress"] = f"مقارنة سريعة… {n:,}/{total_files:,}"
    todo = [(size, pth, mt) for (size, _h), sub in part.items() if len(sub) > 1 for pth, mt in sub]
    del part, flat, cands

    def safe_full(rec):
        try:
            return hash_full(job, rec[1])
        except Cancelled:
            raise
        except OSError:
            return None

    full: dict[tuple, list] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for n, (rec, h) in enumerate(zip(todo, pool.map(safe_full, todo)), 1):
            check(job)
            if h:
                full.setdefault((rec[0], h), []).append((rec[1], rec[2]))
            job["progress"] = f"مقارنة المحتوى… {n:,}/{len(todo):,}"
    groups = []
    for (size, digest), same in full.items():
        if len(same) > 1:
            same.sort(key=lambda x: (x[1], len(x[0])))
            groups.append({"hash": digest[:12], "size": size, "wasted": size * (len(same) - 1),
                           "files": [{"path": p, "mtime": int(m * 1000)} for p, m in same]})
    groups.sort(key=lambda g: -g["wasted"])
    groups = apply_rules(groups[:400])
    for g in groups:
        for f in g["files"]:
            job["allowed"].add(f["path"])
    return {"groups": groups, "wasted": sum(g["wasted"] for g in groups), "files": sum(len(g["files"]) for g in groups), "scanned": job["scanned"]}



# ---------------- المتشابه ----------------
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
_name_re = None


def dhash(path: str):
    """بصمة بصرية 64 بت: تتشابه للصور المتقاربة وإن اختلف حجمها أو ضغطها."""
    from PIL import Image
    with Image.open(path) as im:
        w, h = im.size
        if w * h > 120_000_000:       # صورة ضخمة جدًا: فكّها يستهلك الذاكرة حتى ينهار البرنامج
            raise ValueError("too large")
        try:
            im.draft("L", (64, 64))
        except Exception:
            pass
        g = im.convert("L").resize((9, 8), Image.LANCZOS)
        px = list(g.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
    return bits, w, h


def popcount(x: int) -> int:
    return bin(x).count("1")


def normalize_name(name: str) -> str:
    import re
    stem, ext = os.path.splitext(name)
    stem = stem.lower()
    stem = re.sub(r"[\s_-]*\(\d+\)$", "", stem)
    stem = re.sub(r"[\s_-]*(copy|copia|نسخة|- copy|copy of|final|new|جديد)(\s*\d*)$", "", stem)
    stem = re.sub(r"^(copy of|copia de|نسخة من)\s+", "", stem)
    stem = re.sub(r"[\s_-]+\d{1,2}$", "", stem) if re.search(r"[a-zA-Z\u0600-\u06FF]", stem) else stem
    return re.sub(r"\s+", " ", stem).strip() + ext.lower()


def similar(job, target: Path, max_dist: int, with_names: bool, min_size: int):
    imgs = []
    names: dict[tuple, list] = {}
    n_img = 0
    for p, st in walk(job, target, skip_special=True, include_hidden=False):
        ext = p.suffix.lower()
        if ext in IMG_EXT and st.st_size >= max(2048, min_size // 100):
            imgs.append((str(p), st.st_size, st.st_mtime))
        if with_names and st.st_size >= min_size and len(names) < 400_000:
            names.setdefault((normalize_name(p.name), p.suffix.lower()), []).append((str(p), st.st_size, st.st_mtime))
    imgs = imgs[:30000]
    hashed = []

    def safe_dhash(rec):
        if job["cancel"]:
            return None
        try:
            return dhash(rec[0])
        except Exception:
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, (os.cpu_count() or 4))) as pool:
        for i, (rec, res) in enumerate(zip(imgs, pool.map(safe_dhash, imgs))):
            check(job)
            if res:
                hashed.append((res[0], rec[0], rec[1], rec[2], res[1], res[2]))
            if i % 50 == 0:
                job["progress"] = f"تحليل الصور… {i:,}/{len(imgs):,}"
    # فهرسة متعددة: كل بصمة تُقسَّم إلى أجزاء؛ المتشابهان يتشاركان جزءًا واحدًا على الأقل
    k = max_dist + 1
    width = 64 // k
    buckets: dict[tuple, list[int]] = {}
    for idx, rec in enumerate(hashed):
        for c in range(k):
            buckets.setdefault((c, (rec[0] >> (c * width)) & ((1 << width) - 1)), []).append(idx)
    parent = list(range(len(hashed)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    checked = set()
    for members in buckets.values():
        if len(members) < 2 or len(members) > 400:
            continue
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                i, j = members[a], members[b]
                if (i, j) in checked:
                    continue
                checked.add((i, j))
                if popcount(hashed[i][0] ^ hashed[j][0]) <= max_dist:
                    parent[find(i)] = find(j)
        check(job)
    comp: dict[int, list[int]] = {}
    for idx in range(len(hashed)):
        comp.setdefault(find(idx), []).append(idx)
    groups = []
    for members in comp.values():
        if len(members) < 2:
            continue
        files = sorted((hashed[m] for m in members), key=lambda r: -(r[4] * r[5]))
        groups.append({"type": "image", "size": sum(f[2] for f in files[1:]), "wasted": sum(f[2] for f in files[1:]),
                       "files": [{"path": f[1], "size": f[2], "mtime": int(f[3] * 1000), "w": f[4], "h": f[5]} for f in files]})
    if with_names:
        for (nm, _ext), items in names.items():
            if len(items) < 2:
                continue
            items.sort(key=lambda r: r[2], reverse=True)
            groups.append({"type": "name", "key": nm, "size": sum(i[1] for i in items[1:]), "wasted": sum(i[1] for i in items[1:]),
                           "files": [{"path": i[0], "size": i[1], "mtime": int(i[2] * 1000)} for i in items]})
    groups.sort(key=lambda g: -g["wasted"])
    groups = apply_rules(groups[:300])
    for g in groups:
        for f in g["files"]:
            job["allowed"].add(f["path"])
    return {"groups": groups, "images": len(hashed), "wasted": sum(g["wasted"] for g in groups)}


# ---------------- مجلدات متشابهة ----------------
def similar_folders(job, target: Path, threshold: float, min_files: int = 3):
    """أزواج مجلدات تتشابه محتوياتها (الحجم + الاسم) بنسبة ≥ threshold، ولا يحتوي أحدهما الآخر."""
    sigs: dict[str, dict] = {}
    n = 0
    top = str(target)
    for p, st in walk(job, target, skip_special=True, include_hidden=False):
        n += 1
        if n > 400_000:
            break
        key = (st.st_size, p.name.lower())
        d, depth = p.parent, 0
        while str(d) != top and str(d).startswith(top) and depth < 9:
            s = sigs.setdefault(str(d), {})
            s[key] = st.st_size
            d, depth = d.parent, depth + 1
    dirs = [d for d, s in sigs.items() if len(s) >= min_files]
    index: dict = {}
    for di, d in enumerate(dirs):
        for k in sigs[d]:
            index.setdefault(k, []).append(di)
    pairs: Counter = Counter()
    shared_bytes: Counter = Counter()
    for k, ds in index.items():
        if 2 <= len(ds) <= 60:
            for i in range(len(ds)):
                for j in range(i + 1, len(ds)):
                    pairs[(ds[i], ds[j])] += 1
                    shared_bytes[(ds[i], ds[j])] += k[0]
        check(job)
    out = []
    for (a, b), shared in pairs.items():
        da, db = dirs[a], dirs[b]
        if da.startswith(db + os.sep) or db.startswith(da + os.sep):
            continue
        sa, sb = sigs[da], sigs[db]
        ratio = shared / min(len(sa), len(sb))
        if shared >= min_files and ratio >= threshold:
            out.append({"a": da, "b": db, "shared": shared, "only_a": len(sa) - shared, "only_b": len(sb) - shared, "ratio": round(ratio, 3),
                        "size_a": sum(sa.values()), "size_b": sum(sb.values()), "shared_bytes": shared_bytes[(a, b)]})
    out.sort(key=lambda x: -x["shared_bytes"])
    out = out[:200]
    for x in out:
        job["allowed"].add(x["a"]); job["allowed"].add(x["b"])
    return {"pairs": out, "scanned": n}


# ---------------- الكاش وملفات النظام ----------------
def du_kb(path: str) -> int:
    try:
        r = subprocess.run(["/usr/bin/du", "-sk", path], capture_output=True, text=True, timeout=45)
        return int(r.stdout.split()[0]) * 1024 if r.stdout.split() else 0
    except Exception:
        return 0


def sized(job, paths: list[str]) -> list[dict]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        sizes = list(pool.map(du_kb, paths))
    out = [{"path": p, "name": os.path.basename(p), "size": s} for p, s in zip(paths, sizes)]
    out.sort(key=lambda x: -x["size"])
    return out


def children(path: Path) -> list[str]:
    try:
        return [str(path / n) for n in os.listdir(path) if n != ".DS_Store"]
    except OSError:
        return []


def find_named(job, top: Path, name: str, limit_seconds=45, max_depth=7):
    """يبحث عن مجلدات باسم معيّن (مثل node_modules) دون الدخول إليها."""
    out, start = [], time.time()
    stack = [(top, 0)]
    while stack and time.time() - start < limit_seconds:
        check(job)
        d, depth = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if not e.is_dir(follow_symlinks=False):
                        continue
                    if e.name == name:
                        out.append(e.path)
                    elif depth < max_depth and e.name not in ("Library", ".Trash", ".git", ".npm", ".cache", ".gradle") and not e.name.endswith(SKIP_SUFFIX):
                        stack.append((Path(e.path), depth + 1))
                except OSError:
                    continue
    return out


def caches(job):
    cats = []

    def add(cid, title, desc, risk, paths, permanent_ok=True):
        paths = [p for p in paths if os.path.exists(p)]
        if not paths:
            return
        items = sized(job, paths)
        total = sum(i["size"] for i in items)
        if total <= 0:
            return
        cats.append({"id": cid, "title": title, "desc": desc, "risk": risk, "size": total, "permanent_ok": permanent_ok, "items": items[:60]})
        for i in items:
            job["allowed"].add(i["path"])
            if permanent_ok:
                job["perm_ok"].add(i["path"])

    job["progress"] = "فحص كاش التطبيقات…"
    add("app-caches", "كاش التطبيقات", "ملفات مؤقتة تعيد التطبيقات بناءها عند الحاجة. آمنة غالبًا، وقد تبطئ أول تشغيل لكل تطبيق.", "safe", children(HOME / "Library/Caches"))
    job["progress"] = "فحص السجلات…"
    add("logs", "السجلات (Logs)", "ملفات سجل الأخطاء. آمنة للحذف.", "safe", children(HOME / "Library/Logs"))
    add("trash", "سلة المهملات", "ملفات حذفتها سابقًا. إفراغها نهائي.", "safe", children(HOME / ".Trash"))
    job["progress"] = "فحص أدوات المطورين…"
    dev = [str(HOME / x) for x in (".npm/_cacache", ".cache", ".gradle/caches", "Library/Developer/Xcode/DerivedData", "Library/Developer/Xcode/iOS DeviceSupport",
                                      "Library/Developer/CoreSimulator/Caches", "Library/Caches/Homebrew", ".m2/repository/.cache")]
    add("dev-caches", "كاش أدوات المطورين", "npm وGradle وXcode وHomebrew وغيرها. تُعاد بنائها تلقائيًا عند البناء أو التثبيت التالي (قد تحتاج تنزيلًا).", "rebuild", dev)
    dl = HOME / "Downloads"
    inst = []
    if dl.is_dir():
        for n in os.listdir(dl):
            if n.lower().endswith((".dmg", ".pkg", ".iso", ".xip")):
                inst.append(str(dl / n))
    add("installers", "ملفات التثبيت في التنزيلات", "ملفات dmg وpkg التي استعملتها غالبًا ولم تعد تحتاجها.", "review", inst, permanent_ok=False)
    job["progress"] = "البحث عن node_modules…"
    nm = find_named(job, HOME, "node_modules")
    add("node-modules", "مجلدات node_modules", "مكتبات مشاريع JavaScript. تُعاد بأمر npm install. احذف ما في مشاريع قديمة.", "rebuild", nm, permanent_ok=False)
    cats.sort(key=lambda c: -c["size"])
    return {"categories": cats, "total": sum(c["size"] for c in cats)}


# ---------------- الكبير والفارغ ----------------
def large(job, target: Path, min_size: int):
    heap: list = []
    for p, st in walk(job, target, skip_special=False):
        if st.st_size >= min_size:
            if len(heap) < 300:
                heapq.heappush(heap, (st.st_size, str(p), st.st_mtime))
            elif st.st_size > heap[0][0]:
                heapq.heapreplace(heap, (st.st_size, str(p), st.st_mtime))
    items = sorted(heap, reverse=True)
    for _s, pth, _m in items:
        job["allowed"].add(pth)
    now = time.time()
    return {"files": [{"path": p, "size": s, "mtime": int(m * 1000), "old": now - m > 365 * 86400} for s, p, m in items], "total": sum(s for s, _p, _m in items)}


def empty_dirs(job, target: Path):
    out = []

    def is_empty(d: Path) -> bool:
        check(job)
        try:
            names = os.listdir(d)
        except OSError:
            return False
        real = [n for n in names if n != ".DS_Store"]
        if not real:
            return True
        ok = True
        for n in real:
            p = d / n
            if p.is_symlink() or not p.is_dir() or n.endswith(SKIP_SUFFIX):
                ok = False
                continue
            if not is_empty(p):
                ok = False
        job["scanned"] += 1
        return ok

    def scan(d: Path):
        check(job)
        try:
            names = os.listdir(d)
        except OSError:
            return
        for n in names:
            p = d / n
            if p.is_symlink() or not p.is_dir() or n.startswith(".") or n.endswith(SKIP_SUFFIX) or n in SKIP_DIR_NAMES:
                continue
            if is_empty(p):
                out.append(str(p))
            else:
                scan(p)
    scan(target)
    for p in out:
        job["allowed"].add(p)
    return {"dirs": out[:1000]}


# ---------------- التشغيل ----------------
def run(job, kind, base: Path, target: Path, options: dict):
    try:
        if kind == "analyze":
            job["result"] = analyze(job, target)
        elif kind == "duplicates":
            job["result"] = duplicates(job, target, int(options.get("min_size", 1 << 20)))
        elif kind == "folders":
            job["result"] = similar_folders(job, target, float(options.get("threshold", 0.8)))
        elif kind == "similar":
            job["result"] = similar(job, target, int(options.get("max_dist", 5)), bool(options.get("names", True)), int(options.get("min_size", 100 << 10)))
        elif kind == "caches":
            job["result"] = caches(job)
        elif kind == "large":
            job["result"] = large(job, target, int(options.get("min_size", 100 << 20)))
        elif kind == "empty":
            job["result"] = empty_dirs(job, target)
        else:
            raise ValueError("نوع فحص غير معروف")
        job["state"] = "done"; job["progress"] = "اكتمل"
    except Cancelled:
        job["state"] = "cancelled"; job["progress"] = "أُلغي"
    except Exception as exc:
        job["state"] = "error"; job["error"] = str(exc)


KIND_AR = {"analyze": "تحليل المساحة", "duplicates": "البحث عن الملفات المكررة", "folders": "البحث عن المجلدات المتشابهة",
           "similar": "البحث عن الصور المتشابهة", "caches": "فحص الذاكرات المؤقتة", "large": "البحث عن الملفات الكبيرة", "empty": "البحث عن المجلدات الفارغة"}


def run_notified(fn, job, *args):
    """يشغّل الفحص ثم يرسل نتيجته إلى Telegram إن كان مفعّلًا (الإلغاء لا يُشعِر)."""
    try:
        fn(job, *args)
    finally:
        if job.get("state") in ("done", "error"):
            try:
                import telegram_link
                telegram_link.notify_job(KIND_AR.get(job["kind"], "الفحص"), job["state"], time.time() - job["started"], job.get("error", ""),
                                         "افتح زاجل لرؤية النتيجة." if job["state"] == "done" else "")
            except Exception:
                pass


def start(kind: str, base: Path, target: Path, options: dict) -> dict:
    job = new_job(kind, str(target))
    job["base"] = str(base)
    threading.Thread(target=run_notified, args=(run, job, kind, base, target, options), daemon=True).start()
    return job


# ---------------- الحذف ----------------
def trash_dir_for(path: Path) -> Path:
    st = path.stat()
    if st.st_dev == HOME.stat().st_dev:
        d = HOME / ".Trash"
    else:
        vol = path
        while not os.path.ismount(vol):
            vol = vol.parent
        d = vol / ".Trashes" / str(os.getuid())
    d.mkdir(parents=True, exist_ok=True)
    return d


def log(kind, items, ok):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(f'{dt.datetime.now().isoformat(timespec="seconds")}\t{kind}\t{ok}\t{len(items)}\t{items[:5]}\n')


def kind_is_dir(job, raw):
    return job.get("kind") == "empty"


def remove(job_id: str, paths: list[str], permanent: bool) -> list[dict]:
    job = JOBS.get(job_id)
    if not job:
        raise ValueError("نتيجة الفحص انتهت صلاحيتها؛ أعد الفحص.")
    report = []
    for raw in paths:
        p = Path(raw)
        try:
            if raw not in job["allowed"]:
                raise ValueError("ليس ضمن نتائج الفحص.")
            if job.get("base", "").find(":") > 0 and not job["base"].startswith("/"):  # حساب rclone: إلى سلة الخدمة
                import rclone_src as R
                R._run(["rmdir" if raw.endswith("/") or kind_is_dir(job, raw) else "deletefile", raw], 600)
                report.append({"path": raw, "ok": True})
                continue
            if permanent and raw not in job["perm_ok"]:
                raise ValueError("هذا العنصر لا يُحذف نهائيًا؛ يُنقل إلى السلة فقط.")
            if not p.exists() and not p.is_symlink():
                raise ValueError("لم يعد موجودًا.")
            if p.resolve() in (HOME, HOME / "Library", HOME / "Documents", HOME / "Desktop", HOME / "Downloads") or str(p.resolve()) == "/":
                raise ValueError("مجلد أساسي محمي.")
            if permanent:
                shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
            else:
                dest_dir = trash_dir_for(p)
                dest = dest_dir / p.name
                i = 1
                while dest.exists():
                    dest = dest_dir / f"{p.stem} {i}{p.suffix}"
                    i += 1
                shutil.move(str(p), str(dest))
            report.append({"path": raw, "ok": True})
        except Exception as exc:
            report.append({"path": raw, "ok": False, "detail": str(exc)})
    log("permanent" if permanent else "trash", [r["path"] for r in report if r["ok"]], all(r["ok"] for r in report))
    try:
        import telegram_link
        ok_n = sum(1 for r in report if r["ok"])
        telegram_link.notify_job("التنظيف", "done", 3, detail=f"نُقل أو حُذف {ok_n} من {len(report)}" + (" (بعضها تعذّر)." if ok_n < len(report) else "."))
    except Exception:
        pass
    return report


# ---------------- حسابات السحابة المباشرة (rclone) ----------------
# المسارات هنا بصيغة rclone «الحساب:المجلد/الملف»، والقائمة مع بصمة md5 من الخدمة نفسها، فلا يُنزَّل شيء.
def _rc_join(spec, rel):
    return spec + rel if spec.endswith(":") else spec.rstrip("/") + "/" + rel


def rc_list(job, spec):
    import json as _json
    import rclone_src as R
    job["progress"] = "جلب قائمة الملفات من السحابة…"
    items = _json.loads(R._run(["lsjson", "-R", "--hash", "--hash-type", "md5", "--no-mimetype", spec], 3600))
    files, dirs = [], []
    for it in items:
        check(job)
        try:
            mt = dt.datetime.fromisoformat(it["ModTime"][:19] + "+00:00").timestamp()
        except Exception:
            mt = 0
        if it.get("IsDir"):
            dirs.append(it["Path"])
        else:
            files.append((it["Path"], max(0, int(it.get("Size") or 0)), mt, (it.get("Hashes") or {}).get("md5", "")))
    job["scanned"] = len(files)
    return files, dirs


def rc_run(job, kind, spec, options):
    try:
        files, dirs = rc_list(job, spec)
        job["progress"] = "تحليل…"
        if kind == "analyze":
            total = sum(f[1] for f in files); types, kids = {}, {}
            for rel, size, mt, _h in files:
                t = types.setdefault(category(rel), [0, 0]); t[0] += size; t[1] += 1
                top = rel.split("/")[0]; k = kids.setdefault(top, {"name": top, "is_dir": "/" in rel, "size": 0, "files": 0}); k["size"] += size; k["files"] += 1
            top30 = sorted(files, key=lambda f: -f[1])[:30]
            for f in top30:
                job["allowed"].add(_rc_join(spec, f[0]))
            job["result"] = {"total": total, "files": len(files), "children": sorted(kids.values(), key=lambda c: -c["size"])[:80],
                             "types": [{"name": k, "size": v[0], "count": v[1]} for k, v in sorted(types.items(), key=lambda kv: -kv[1][0])],
                             "biggest": [{"path": _rc_join(spec, r), "size": sz, "mtime": int(m * 1000)} for r, sz, m, _h in top30], "skipped": 0}
        elif kind == "large":
            mn = int(options.get("min_size", 100 << 20)); items = sorted([f for f in files if f[1] >= mn], key=lambda f: -f[1])[:300]; now = time.time()
            for f in items:
                job["allowed"].add(_rc_join(spec, f[0]))
            job["result"] = {"files": [{"path": _rc_join(spec, r), "size": sz, "mtime": int(m * 1000), "old": now - m > 365 * 86400} for r, sz, m, _h in items], "total": sum(f[1] for f in items)}
        elif kind == "duplicates":
            mn = int(options.get("min_size", 1 << 20)); by = {}
            for rel, size, mt, h in files:
                if size >= mn and h:
                    by.setdefault((size, h), []).append((rel, mt))
            groups = []
            for (size, h), same in by.items():
                if len(same) > 1:
                    same.sort(key=lambda x: (x[1], len(x[0])))
                    groups.append({"hash": h[:12], "size": size, "wasted": size * (len(same) - 1), "files": [{"path": _rc_join(spec, p), "mtime": int(m * 1000), "size": size} for p, m in same]})
            groups.sort(key=lambda g: -g["wasted"]); groups = apply_rules(groups[:400])
            for g in groups:
                for f in g["files"]:
                    job["allowed"].add(f["path"])
            job["result"] = {"groups": groups, "wasted": sum(g["wasted"] for g in groups), "files": sum(len(g["files"]) for g in groups), "scanned": len(files)}
        elif kind == "empty":
            used = set()
            for rel, *_ in files:
                parts = rel.split("/")[:-1]
                for i in range(1, len(parts) + 1):
                    used.add("/".join(parts[:i]))
            empty = sorted([d for d in dirs if d not in used], key=lambda d: -d.count("/"))
            for d in empty:
                job["allowed"].add(_rc_join(spec, d))
            job["result"] = {"dirs": [_rc_join(spec, d) for d in empty][:500], "count": len(empty)}
        else:
            raise ValueError("هذا الفحص لا يعمل على الحسابات السحابية المباشرة؛ المتاح: التحليل، الكبيرة، المكررة، الفارغة.")
        job["state"] = "done"; job["progress"] = "اكتمل"
    except Cancelled:
        job["state"] = "cancelled"; job["progress"] = "أُلغي"
    except Exception as exc:
        job["state"] = "error"; job["error"] = str(exc)


def rc_start(kind, spec, options):
    job = new_job(kind, spec)
    job["base"] = spec
    threading.Thread(target=run_notified, args=(rc_run, job, kind, spec, options), daemon=True).start()
    return job
