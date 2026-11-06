"""تحليل الأجهزة (الهاتف والساعة) وتنظيفها: المساحة، الكبير، الفارغ، المكرر، المتشابه بالاسم، الكاش.
كل الفحوصات للقراءة فقط عبر adb؛ الحذف (rm) لا يتم إلا من خلال نتائج فحص سابق وبتأكيد من المستخدم."""
from __future__ import annotations

import heapq
import json
import os
import posixpath
import re
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

    def add(cid, title, desc, risk, items, perm=True, selectable=True, action=None):
        if not items:
            return
        cat = {"id": cid, "title": title, "desc": desc, "risk": risk, "size": sum(i["size"] for i in items), "permanent_ok": perm, "selectable": selectable, "items": items[:80]}
        if action:
            cat["action"] = action
        cats.append(cat)
        if selectable:
            for i in items:
                job["allowed"].add(i["path"])
                if perm:
                    job["perm_ok"].add(i["path"])
    job["progress"] = "فحص كاش التطبيقات…"
    try: add("app-caches", "كاش التطبيقات", "ملفات مؤقتة تعيد التطبيقات بناءها (آمنة). قد يبطؤ أول تشغيل لكل تطبيق.", "safe", du_items(serial, "/sdcard/Android/data/*/cache"))
    except Exception: pass
    job["progress"] = "فحص المصغّرات وسلة المهملات…"
    try: add("thumbs", "المصغّرات المخزّنة", "صور مصغّرة يعيد المعرض بناءها. آمنة.", "safe", du_items(serial, "/sdcard/DCIM/.thumbnails /sdcard/Pictures/.thumbnails /sdcard/.thumbnails"))
    except Exception: pass
    try: add("trash", "سلة المهملات", "ملفات حُذفت سابقًا من تطبيقات (المعرض وغيره). إفراغها نهائي.", "safe", du_items(serial, "/sdcard/.Trash /sdcard/.trash /sdcard/.Trash-* /sdcard/.recycle_bin '/sdcard/.$recycle_bin$' /sdcard/Android/.Trash"))
    except Exception: pass
    try:
        r = M.shell("find /sdcard/Download/ -maxdepth 1 -type f \\( -iname '*.apk' -o -iname '*.xapk' -o -iname '*.apks' \\) -exec stat -c '%s|%n' {} + 2>/dev/null", serial, 120)
        inst = []
        for line in r.stdout.splitlines():
            s, sep, n = line.partition("|")
            if sep and s.isdigit(): inst.append({"path": n, "name": posixpath.basename(n), "size": int(s)})
        add("installers", "ملفات تثبيت تطبيقات (APK) في التنزيلات", "ملفات تثبيت استعملتها غالبًا ولم تعد تحتاجها. راجعها قبل الحذف.", "review", sorted(inst, key=lambda i: -i["size"]), perm=False)
    except Exception: pass
    # Each independent phone section is isolated: unavailable adb commands must not hide other findings.
    try:
        health = _phone_health(serial)
    except Exception:
        health = None
    try:
        media = []
        for folder in ("/sdcard/Android/media/com.whatsapp/WhatsApp/Media", "/sdcard/Android/media/com.whatsapp.w4b/WhatsApp/Media"):
            media.extend(du_items(serial, q(folder) + "/*"))
            for item in media:
                item["name"] = posixpath.basename(item["path"])
        add("whatsapp-media", "وسائط واتساب", "مجلدات الوسائط؛ راجعها من واتساب قبل إزالة أي ملف.", "review", media,
            perm=False, selectable=False,
            action={"kind": "howto", "label": "إدارة الوسائط في واتساب", "steps": ["واتساب ▸ الإعدادات ▸ التخزين والبيانات ▸ إدارة التخزين", "أوقف تنزيل الفيديو تلقائيًا من التخزين والبيانات"]})
    except Exception: pass
    try:
        apps = (health or {}).get("apps", [])
        data_items = []
        for app in apps:
            if app.get("data", 0) > 1 << 30:
                label = app.get("label") or app["pkg"]
                data_items.append({"path": app["pkg"], "name": label, "size": app["data"], "note": app.get("note", "راجع بيانات التطبيق قبل مسحها.")})
        add("app-data", "بيانات تطبيقات كبيرة", "بيانات محفوظة داخل التطبيقات؛ مسحها قد يزيل ملفات أو إعدادات محلية.", "info", data_items,
            perm=False, selectable=False,
            action={"kind": "howto", "label": "فتح مساحة التطبيق", "steps": ["الإعدادات ▸ التطبيقات ▸ <التطبيق> ▸ التخزين"]})
    except Exception:
        pass
    try:
        logs = du_items(serial, "/sdcard/log/*")
        add("device-logs", "سجلات الجهاز", "سجلات داخلية يعيد النظام إنشاءها بحجم صغير.", "safe", logs, perm=True)
    except Exception:
        pass
    try:
        r = M.shell("find /sdcard/Download/ -maxdepth 2 -type f -exec stat -c '%s|%n' {} + 2>/dev/null", serial, 120)
        files = []
        for line in r.stdout.splitlines():
            size, sep, path = line.partition("|")
            if sep and size.isdigit() and re.search(r" \([1-9][0-9]*\)(?=\.[^.]+$|$)", posixpath.basename(path)):
                files.append((int(size), path))
        originals = {}
        for size, path in files:
            name = posixpath.basename(path)
            original = re.sub(r" \([1-9][0-9]*\)(?=(\.[^.]+)?$)", "", name)
            originals[path] = posixpath.join(posixpath.dirname(path), original)
        candidates = [p for _, p in files] + [p for p in originals.values()]
        sizes = {p: s for s, p in files}
        # Stat originals that weren't duplicates too; hashing is only useful for equal-size pairs.
        missing = sorted({p for p in originals.values() if p not in sizes})
        if missing:
            for start in range(0, len(missing), CHUNK):
                sr = M.shell("stat -c '%s|%n' " + " ".join(q(p) for p in missing[start:start+CHUNK]) + " 2>/dev/null", serial, 120)
                for ln in sr.stdout.splitlines():
                    sz, sep, p = ln.partition("|")
                    if sep and sz.isdigit(): sizes[p] = int(sz)
        matched = []
        for size, path in files:
            original = originals[path]
            if sizes.get(original) == size:
                matched.append((path, original, size))
        hashes = sha_many(serial, [p for pair in matched for p in pair[:2]]) if matched else {}
        copies = [{"path": path, "name": posixpath.basename(path), "size": size, "note": "نسخة مطابقة لـ " + posixpath.basename(original)}
                  for path, original, size in matched if hashes.get(path) and hashes.get(path) == hashes.get(original)]
        add("download-copies", "نسخ مطابقة في التنزيلات", "نسخ مطابقة للمحتوى والأصل موجود في المجلد نفسه.", "review", copies, perm=True)
    except Exception:
        pass
    cats.sort(key=lambda c: -c["size"])
    return {"categories": cats, "total": sum(c["size"] for c in cats if c.get("selectable", True)), "health": health}


def _diskstats_value(text, label):
    """dumpsys diskstats يكتب «Label: [..]» أو «Label: رقم» (وأحيانًا ["Label", ...] في نسخ أخرى)."""
    m = re.search(r"^\s*" + re.escape(label) + r"\s*:\s*(\[.*?\]|-?\d+)", text, re.M)
    if not m:
        m = re.search(r'\[\s*["\']' + re.escape(label) + r'["\']\s*,\s*(\[[^\]]*\]|-?\d+)\s*\]', text)
    if not m:
        return None
    value = m.group(1)
    try:
        return json.loads(value)
    except Exception:
        return int(value) if value.lstrip("-").isdigit() else None


APP_LABELS = {"com.whatsapp": "واتساب", "com.whatsapp.w4b": "واتساب للأعمال", "com.sec.android.easyMover": "Smart Switch (نقل البيانات)",
              "com.google.android.apps.labs.language.tailwind": "NotebookLM", "com.readdle.spark": "Spark (البريد)", "com.google.android.youtube": "YouTube",
              "com.microsoft.skydrive": "OneDrive", "com.google.android.apps.photos": "صور Google", "com.google.android.gms": "خدمات Google",
              "com.google.android.apps.maps": "خرائط Google", "com.facebook.katana": "Facebook", "com.instagram.android": "Instagram",
              "com.adobe.reader": "Adobe Acrobat", "com.google.android.apps.docs": "Google Drive", "com.virtualmaze.offlinemapnavigationtracker": "خرائط بلا إنترنت",
              "com.samsung.android.intellivoiceservice": "خدمة الصوت الذكية من سامسونج", "com.google.android.tts": "النطق من Google",
              "com.samsung.android.offline.languagemodel": "نموذج اللغة المحلي من سامسونج", "com.mohamad.smartnotehub": "SmartNoteHub"}


def _gb(n):
    return f"{(n or 0) / 1e9:.1f} غيغابايت"


def _phone_health(serial):
    facts = {}
    try:
        r = M.shell("df -k /data", serial, 30)
        rows = r.stdout.splitlines()
        for row in rows[1:]:
            cols = row.split()
            if len(cols) >= 5 and cols[1].isdigit() and cols[2].isdigit():
                facts.update(total=int(cols[1]) * 1024, used=int(cols[2]) * 1024, free=int(cols[3]) * 1024)
                break
    except Exception: pass
    try:
        facts["model"] = M.shell("getprop ro.product.model", serial, 20).stdout.strip()
    except Exception: pass
    apps = []
    totals = {}
    try:
        raw = M.shell("dumpsys diskstats", serial, 60).stdout
        names = _diskstats_value(raw, "Package Names") or []
        app_sizes = _diskstats_value(raw, "App Sizes") or []
        data_sizes = _diskstats_value(raw, "App Data Sizes") or []
        cache_sizes = _diskstats_value(raw, "Cache Sizes") or []
        notes = {
            "com.whatsapp": "الوسائط غالبًا في /sdcard/Android/media/؛ راجع إدارة التخزين.",
            "com.whatsapp.w4b": "الوسائط غالبًا في /sdcard/Android/media/؛ راجع إدارة التخزين.",
            "com.sec.android.easyMover": "بقايا نقل مكتمل عبر Smart Switch؛ امسح بياناته من إعدادات التطبيق إن لم تعد تحتاجها.",
            "com.google.android.apps.labs.language.tailwind": "قد تشمل صوت NotebookLM المنزّل للاستماع دون اتصال.",
            "com.google.android.youtube": "قد تشمل تنزيلات YouTube للمشاهدة دون اتصال.",
            "com.google.android.apps.photos": "قد تشمل كاشًا ومصغّرات؛ استخدم «إخلاء مساحة» بعد التأكد من النسخ الاحتياطي.",
            "com.microsoft.skydrive": "قد تشمل ملفات OneDrive المتاحة دون اتصال.",
            "com.readdle.spark": "قد تشمل نسخًا محلية من البريد.",
            "com.google.android.apps.maps": "قد تشمل خرائط محفوظة دون اتصال.",
        }
        for i, pkg in enumerate(names):
            vals = [app_sizes, data_sizes, cache_sizes]
            if i >= min(map(len, vals), default=0): continue
            try: app, data, cache = (int(v[i]) for v in vals)
            except (TypeError, ValueError): continue
            apps.append({"pkg": str(pkg), "label": APP_LABELS.get(str(pkg), str(pkg).split(".")[-1]), "app": app, "data": data, "cache": cache, **({"note": notes[pkg]} if pkg in notes else {})})
        apps.sort(key=lambda a: -(a["app"] + a["data"]))
        for label in ("Photos Size", "Videos Size", "Audio Size", "Other Size", "System Size", "App Size", "App Data Size"):
            val = _diskstats_value(raw, label)
            key = label.lower().replace(" size", "")
            if isinstance(val, int): totals[key] = val
            elif isinstance(val, list) and val and isinstance(val[0], int): totals[key] = val[0]
    except Exception: pass
    cards = []
    total, used, free = facts.get("total"), facts.get("used"), facts.get("free")
    if total:
        pct = free * 100 / total
        cards.append({"id": "storage", "title": "مساحة الهاتف", "status": "warn" if pct < 20 else "ok", "summary": f"المتاح {pct:.0f}% من مساحة البيانات", "details": [f"الإجمالي {_gb(total)}", f"المستخدم {_gb(used)}", f"المتاح {_gb(free)}"], "advice": ["حافظ على 20% مساحة متاحة على الأقل."] if pct < 20 else [], "commands": []})
    breakdown = [("الصور", "photos"), ("الفيديوهات", "videos"), ("الصوت", "audio"), ("برامج التطبيقات", "app"), ("بيانات التطبيقات (ومنها وسائط واتساب)", "app data"), ("النظام", "system"), ("أخرى", "other")]
    details = [f"{label}: {_gb(totals.get(key, 0) if key else sum(a['app'] + a['data'] for a in apps))}" for label, key in breakdown]
    cards.append({"id": "breakdown", "title": "تفصيل المساحة", "status": "ok", "summary": "توزيع المساحة حسب نوع المحتوى", "details": details, "advice": [], "commands": []})
    top = apps[0] if apps else None
    summary = f"أكبر تطبيق هو {top['label']} ({top['pkg']})" if top else "لم تتوفر تفاصيل أحجام التطبيقات"
    cards.append({"id": "apps", "title": "التطبيقات", "status": "ok", "summary": summary, "details": [], "advice": [], "commands": []})
    return {"cards": cards, "facts": facts, "apps": apps[:25]}


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
