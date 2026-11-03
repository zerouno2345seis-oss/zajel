"""تحليل الأجهزة (الهاتف والساعة) وتنظيفها: المساحة، الكبير، الفارغ، المكرر، المتشابه بالاسم، الكاش.
كل الفحوصات للقراءة فقط عبر adb؛ الحذف (rm) لا يتم إلا من خلال نتائج فحص سابق وبتأكيد من المستخدم."""
from __future__ import annotations

import heapq
import os
import posixpath
import shlex
import threading
import time

M = None
C = None   # وحدة cleaner (دوال مساعدة: category, normalize_name, Cancelled...)
CHUNK = 40


def init(module, cleaner):
    global M, C
    M, C = module, cleaner


def q(p):
    return shlex.quote(p)


def check(job):
    if job["cancel"]:
        raise C.Cancelled()


def list_files(job, serial, path, min_size=0):
    """كل الملفات تحت path: [(الحجم، وقت التعديل، المسار الكامل)]."""
    cond = f"-size +{max(0, (min_size // 1024) - 1)}k " if min_size >= 2048 else ""
    job["progress"] = "يقرأ ملفات الجهاز…"
    r = M.shell(f"find {q(path.rstrip('/') + '/')} -type f {cond}-exec stat -c '%s|%Y|%n' {{}} + 2>/dev/null", serial, 300)
    out = []
    for line in r.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            out.append((int(parts[0]), int(parts[1]), parts[2]))
        if len(out) % 5000 == 0:
            check(job)
    job["scanned"] = len(out)
    return out


def analyze(job, serial, path):
    files = list_files(job, serial, path)
    base = path.rstrip("/") + "/"
    children: dict[str, dict] = {}
    types: dict[str, list[int]] = {}
    heap: list = []
    total = 0
    for size, mt, full in files:
        total += size
        rel = full[len(base):] if full.startswith(base) else full
        first, sep, _tail = rel.partition("/")
        c = children.setdefault(first, {"name": first, "is_dir": bool(sep), "size": 0, "files": 0})
        c["size"] += size; c["files"] += 1; c["is_dir"] = c["is_dir"] or bool(sep)
        t = types.setdefault(C.category(posixpath.basename(full)), [0, 0]); t[0] += size; t[1] += 1
        if len(heap) < 30:
            heapq.heappush(heap, (size, full, mt))
        elif size > heap[0][0]:
            heapq.heapreplace(heap, (size, full, mt))
    top = sorted(heap, reverse=True)
    for _s, p, _m in top:
        job["allowed"].add(p)
    return {"total": total, "files": len(files), "children": sorted(children.values(), key=lambda c: -c["size"])[:80],
            "types": [{"name": k, "size": v[0], "count": v[1]} for k, v in sorted(types.items(), key=lambda kv: -kv[1][0])],
            "biggest": [{"path": p, "size": s, "mtime": m * 1000} for s, p, m in top], "skipped": 0}


def large(job, serial, path, min_size):
    files = sorted(list_files(job, serial, path, min_size), reverse=True)[:300]
    now = time.time()
    for _s, _m, p in files:
        job["allowed"].add(p)
    return {"files": [{"path": p, "size": s, "mtime": m * 1000, "old": now - m > 365 * 86400} for s, m, p in files], "total": sum(f[0] for f in files)}


def empty(job, serial, path):
    r = M.shell(f"find {q(path.rstrip('/') + '/')} -mindepth 1 -type d -empty 2>/dev/null", serial, 300)
    dirs = [d for d in r.stdout.splitlines() if d and d not in M.PROTECTED_PATHS][:1000]
    for d in dirs:
        job["allowed"].add(d)
    return {"dirs": dirs}


def sha_many(serial, paths):
    out = {}
    for i in range(0, len(paths), CHUNK):
        r = M.shell("sha256sum " + " ".join(q(p) for p in paths[i:i + CHUNK]) + " 2>/dev/null", serial, 600)
        for line in r.stdout.splitlines():
            h, sep, name = line.partition("  ")
            if sep and len(h) == 64:
                out[name] = h
    return out


def duplicates(job, serial, path, min_size):
    files = list_files(job, serial, path, min_size)
    by_size: dict[int, list] = {}
    for size, mt, full in files:
        if size >= min_size:
            by_size.setdefault(size, []).append((full, mt))
    cands = {s: v for s, v in by_size.items() if len(v) > 1}
    total = sum(len(v) for v in cands.values()); done = 0
    groups = []
    for size, items in sorted(cands.items(), key=lambda kv: -kv[0] * (len(kv[1]) - 1)):
        check(job)
        hashes = sha_many(serial, [p for p, _ in items]); done += len(items)
        job["progress"] = f"مقارنة المحتوى على الجهاز… {done}/{total}"
        by_hash: dict[str, list] = {}
        for p, mt in items:
            if p in hashes:
                by_hash.setdefault(hashes[p], []).append((p, mt))
        for h, same in by_hash.items():
            if len(same) > 1:
                same.sort(key=lambda x: (x[1], len(x[0])))
                groups.append({"hash": h[:12], "size": size, "wasted": size * (len(same) - 1), "files": [{"path": p, "mtime": m * 1000} for p, m in same]})
    groups.sort(key=lambda g: -g["wasted"])
    groups = C.apply_rules(groups[:400])
    for g in groups:
        for f in g["files"]:
            job["allowed"].add(f["path"])
    return {"groups": groups, "wasted": sum(g["wasted"] for g in groups), "files": sum(len(g["files"]) for g in groups), "scanned": len(files)}


def similar(job, serial, path, min_size):
    files = list_files(job, serial, path, max(min_size, 0))
    names: dict[tuple, list] = {}
    for size, mt, full in files:
        names.setdefault((C.normalize_name(posixpath.basename(full)), posixpath.splitext(full)[1].lower()), []).append((full, size, mt))
    groups = []
    for (nm, _e), items in names.items():
        if len(items) > 1:
            items.sort(key=lambda r: -r[1])
            groups.append({"type": "name", "key": nm, "size": sum(i[1] for i in items[1:]), "wasted": sum(i[1] for i in items[1:]),
                           "files": [{"path": i[0], "size": i[1], "mtime": i[2] * 1000} for i in items]})
    groups.sort(key=lambda g: -g["wasted"])
    groups = C.apply_rules(groups[:300])
    for g in groups:
        for f in g["files"]:
            job["allowed"].add(f["path"])
    return {"groups": groups, "images": 0, "wasted": sum(g["wasted"] for g in groups),
            "note": "على أجهزة أندرويد يُقارَن التشابه بالأسماء فقط. المقارنة البصرية للصور متاحة لملفات الكمبيوتر والأقراص."}


def du_items(serial, shell_glob):
    r = M.shell(f"du -sk {shell_glob} 2>/dev/null", serial, 300)
    out = []
    for line in r.stdout.splitlines():
        kb, sep, p = line.partition("\t")
        if sep and kb.isdigit() and int(kb) > 0:
            out.append({"path": p, "name": posixpath.basename(posixpath.dirname(p)) + "/" + posixpath.basename(p) if p.endswith("/cache") else posixpath.basename(p), "size": int(kb) * 1024})
    return sorted(out, key=lambda i: -i["size"])


def caches(job, serial):
    cats = []

    def add(cid, title, desc, risk, items, perm=True):
        if not items:
            return
        cats.append({"id": cid, "title": title, "desc": desc, "risk": risk, "size": sum(i["size"] for i in items), "permanent_ok": perm, "items": items[:80]})
        for i in items:
            job["allowed"].add(i["path"])
            if perm:
                job["perm_ok"].add(i["path"])
    job["progress"] = "فحص كاش التطبيقات…"
    add("app-caches", "كاش التطبيقات", "ملفات مؤقتة تعيد التطبيقات بناءها (آمنة). قد يبطؤ أول تشغيل لكل تطبيق.", "safe", du_items(serial, "/sdcard/Android/data/*/cache"))
    job["progress"] = "فحص المصغّرات وسلة المهملات…"
    add("thumbs", "المصغّرات المخزّنة", "صور مصغّرة يعيد المعرض بناءها. آمنة.", "safe", du_items(serial, "/sdcard/DCIM/.thumbnails /sdcard/Pictures/.thumbnails /sdcard/.thumbnails"))
    add("trash", "سلة المهملات", "ملفات حُذفت سابقًا من تطبيقات (المعرض وغيره). إفراغها نهائي.", "safe", du_items(serial, "/sdcard/.Trash /sdcard/.trash /sdcard/.Trash-* /sdcard/.recycle_bin '/sdcard/.$recycle_bin$' /sdcard/Android/.Trash"))
    r = M.shell("find /sdcard/Download/ -maxdepth 1 -type f \\( -iname '*.apk' -o -iname '*.xapk' -o -iname '*.apks' \\) -exec stat -c '%s|%n' {} + 2>/dev/null", serial, 120)
    inst = []
    for line in r.stdout.splitlines():
        s, sep, n = line.partition("|")
        if sep and s.isdigit():
            inst.append({"path": n, "name": posixpath.basename(n), "size": int(s)})
    add("installers", "ملفات تثبيت تطبيقات (APK) في التنزيلات", "ملفات تثبيت استعملتها غالبًا ولم تعد تحتاجها. راجعها قبل الحذف.", "review", sorted(inst, key=lambda i: -i["size"]), perm=False)
    cats.sort(key=lambda c: -c["size"])
    return {"categories": cats, "total": sum(c["size"] for c in cats)}


def run(job, kind, serial, path, options):
    try:
        if kind == "analyze":
            job["result"] = analyze(job, serial, path)
        elif kind == "duplicates":
            job["result"] = duplicates(job, serial, path, int(options.get("min_size", 1 << 20)))
        elif kind == "similar":
            job["result"] = similar(job, serial, path, int(options.get("min_size", 100 << 10)))
        elif kind == "caches":
            job["result"] = caches(job, serial)
        elif kind == "large":
            job["result"] = large(job, serial, path, int(options.get("min_size", 100 << 20)))
        elif kind == "empty":
            job["result"] = empty(job, serial, path)
        elif kind == "folders":
            raise ValueError("مقارنة المجلدات المتشابهة متاحة لمجلدات الكمبيوتر والأقراص فقط.")
        else:
            raise ValueError("نوع فحص غير معروف")
        job["state"] = "done"; job["progress"] = "اكتمل"
    except C.Cancelled:
        job["state"] = "cancelled"; job["progress"] = "أُلغي"
    except Exception as exc:
        job["state"] = "error"; job["error"] = str(exc)


def start(serial, kind, path, options):
    job = C.new_job(kind, path)
    job["serial"] = serial
    threading.Thread(target=C.run_notified, args=(run, job, kind, serial, path, options), daemon=True).start()
    return job


def remove(job, paths):
    """حذف نهائي (rm -rf) لعناصر ظهرت في نتائج الفحص فقط، مع حماية المجلدات الأساسية."""
    serial, report = job["serial"], []
    for raw in paths:
        try:
            if raw not in job["allowed"]:
                raise ValueError("ليس ضمن نتائج الفحص.")
            p = M.storage_path(raw, serial)
            if p in M.PROTECTED_PATHS or p == "/sdcard":
                raise ValueError("مجلد أساسي محمي.")
            r = M.shell("rm -rf " + q(p), serial, 600)
            if r.returncode:
                raise ValueError(r.stderr.strip()[:150] or "تعذّر الحذف.")
            report.append({"path": raw, "ok": True})
        except Exception as exc:
            report.append({"path": raw, "ok": False, "detail": str(exc)})
    M.log_action("clean-device-remove", [r["path"] for r in report if r["ok"]], all(r["ok"] for r in report), serial)
    return report
