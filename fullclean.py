"""التنظيف الكامل: يفحص كل ما يعطيه المستخدم (الكمبيوتر، أقراص، سحابات) ثم يعرض خطة تحسين بمشاركة الذكاء الاصطناعي،
ولا ينفّذ شيئًا إلا بعد موافقة صريحة. التنفيذ ينقل إلى السلة (قابل للاسترجاع) ولا يحذف نهائيًا إلا ما تسمح به نتائج الفحص.
"""
from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

import cleaner as C

FULL: dict[str, dict] = {}
LOCK = threading.Lock()
MAX_ITEM_PATHS = 3000

LOCAL_STEPS = [("analyze", "تحليل المساحة", {}), ("large", "أكبر الملفات", {"min_size": 200 << 20}),
               ("duplicates", "الملفات المكررة", {"min_size": 5 << 20}), ("empty", "المجلدات الفارغة", {})]
CLOUD_STEPS = [("analyze", "تحليل المساحة", {}), ("large", "أكبر الملفات", {"min_size": 200 << 20}),
               ("duplicates", "الملفات المكررة", {"min_size": 5 << 20}), ("empty", "المجلدات الفارغة", {})]


def public(f: dict) -> dict:
    return {"id": f["id"], "state": f["state"], "progress": f["progress"], "steps": f["steps"], "plan": f.get("plan"),
            "ai": f.get("ai", ""), "report": f.get("report"), "error": f.get("error", ""), "health": f.get("health"),
            "phone_health": f.get("phone_health", {}), "seconds": round(time.time() - f["started"], 1)}


def _cancelled(f):
    if f["cancel"]:
        raise C.Cancelled()


def start(targets: list[dict], resolver, rc_spec, agent: str = "") -> dict:
    """targets: [{'root': 'home'|'vol:X'|'rc:name', 'label': '...'}]؛ resolver(root) → (base, target) للمحلي؛ rc_spec(root) → «حساب:»."""
    if not targets:
        raise ValueError("اختر جهازًا أو قرصًا أو سحابة واحدة على الأقل.")
    f = {"id": uuid.uuid4().hex[:10], "state": "scanning", "progress": "يبدأ…", "steps": [], "cancel": False, "started": time.time(),
         "jobs": {}, "plan": None, "ai": "", "report": None, "error": "", "targets": targets, "agent": agent,
         "health": None, "phone_health": {}}
    with LOCK:
        FULL[f["id"]] = f
        for k in sorted(FULL, key=lambda x: FULL[x]["started"])[:-4]:
            FULL.pop(k, None)
    threading.Thread(target=_run, args=(f, resolver, rc_spec), daemon=True).start()
    return public(f)


def _step(f, label):
    s = {"label": label, "state": "running"}
    f["steps"].append(s)
    return s


def _job(f, kind, target_label):
    job = C.new_job(kind, target_label)
    job["keep"] = True          # لا يُحذف من السجل حتى تُنفَّذ الخطة
    f["jobs"][job["id"]] = job
    return job


def _watch(f, job, s, label):
    """ينقل تقدّم المهمة الفرعية إلى الواجهة، ويُلغيها إن أُلغي التنظيف."""
    def beat():
        while job["state"] == "running":
            f["progress"] = f"{label} · {job['progress']}"
            if f["cancel"]:
                job["cancel"] = True
            time.sleep(0.5)
    t = threading.Thread(target=beat, daemon=True)
    t.start()
    return t


def _run(f, resolver, rc_spec):
    results: list[dict] = []     # {target, kind, job, result}
    try:
        for tg in f["targets"]:
            root, label = tg["root"], tg.get("label") or tg["root"]
            is_rc = root.startswith("rc:")
            is_phone = root.startswith("dev:")
            if is_phone:
                serial = root[4:]
                _cancelled(f)
                s = _step(f, f"{label} — الكاش والسجلات")
                job = _job(f, "caches", label)
                job["serial"] = serial
                w = _watch(f, job, s, f"{label} — الكاش والسجلات")
                import adbclean
                adbclean.run(job, "caches", serial, "/sdcard", {})
                w.join(timeout=1)
                if job["state"] == "cancelled":
                    raise C.Cancelled()
                s["state"] = "done" if job["state"] == "done" else "error"
                if job["state"] == "error":
                    s["detail"] = job["error"]
                else:
                    phone_result = job["result"] or {}
                    f["phone_health"][label] = phone_result.get("health")
                    results.append({"target": label, "root": root, "kind": "caches", "job": job["id"], "result": phone_result})
                continue
            if root == "home":
                health_step = _step(f, f"{label} — صحة الجهاز")
                try:
                    import health
                    f["health"] = health.scan()
                    health_step["state"] = "done"
                except Exception:  # noqa: BLE001
                    f["health"] = None
                    health_step["state"] = "error"
            try:
                if is_rc:
                    spec, base = rc_spec(root), rc_spec(root)
                    steps = CLOUD_STEPS
                else:
                    base, target = resolver(root)
                    steps = ([("caches", "الكاش والسجلات", {})] if root == "home" else []) + LOCAL_STEPS
            except Exception as exc:  # noqa: BLE001
                f["steps"].append({"label": f"{label}: تعذر فتحه", "state": "error", "detail": str(exc)})
                continue
            for kind, title, opts in steps:
                _cancelled(f)
                s = _step(f, f"{label} — {title}")
                job = _job(f, kind, label)
                job["base"] = str(base)
                w = _watch(f, job, s, f"{label} — {title}")
                if is_rc:
                    C.rc_run(job, kind, spec, opts)
                elif kind == "caches":
                    C.run(job, kind, Path(base), Path(base), opts)
                else:
                    C.run(job, kind, Path(base), Path(target), opts)
                w.join(timeout=1)
                if job["state"] == "cancelled":
                    raise C.Cancelled()
                s["state"] = "done" if job["state"] == "done" else "error"
                if job["state"] == "error":
                    s["detail"] = job["error"]
                else:
                    results.append({"target": label, "root": root, "kind": kind, "job": job["id"], "result": job["result"]})
        f["state"], f["progress"] = "planning", "يبني الخطة…"
        f["plan"] = build_plan(results)
        f["ai"] = ask_ai(f, results, f["plan"])
        f["state"], f["progress"] = "ready", "الخطة جاهزة للمراجعة"
    except C.Cancelled:
        f["state"], f["progress"] = "cancelled", "أُلغي"
    except Exception as exc:  # noqa: BLE001
        f["state"], f["error"] = "error", str(exc)


def _chunks(paths):
    return [paths[i:i + MAX_ITEM_PATHS] for i in range(0, len(paths), MAX_ITEM_PATHS)]


def build_plan(results: list[dict]) -> dict:
    items: list[dict] = []
    overview = []
    advice = []

    def add(group, title, desc, risk, size, paths, job, target, on, sample=None, **extra):
        if not paths:
            return
        items.append({"id": f"i{len(items)}", "group": group, "title": title, "desc": desc, "risk": risk, "size": size, "count": len(paths),
                      "paths": paths[:MAX_ITEM_PATHS], "job": job, "target": target, "default_on": on, "sample": (sample or paths)[:12],
                      "truncated": len(paths) > MAX_ITEM_PATHS, **extra})

    for r in results:
        res, kind, job, tg = r["result"] or {}, r["kind"], r["job"], r["target"]
        if kind == "analyze":
            overview.append({"target": tg, "total": res.get("total", 0), "files": res.get("files", 0),
                             "types": (res.get("types") or [])[:5], "top": [{"name": c["name"], "size": c["size"]} for c in (res.get("children") or [])[:5]]})
        elif kind == "caches":
            serial = bool((r.get("job_data") or {}).get("serial"))
            # Job metadata is also available in cleaner.JOBS for actual scan results.
            serial = serial or bool(C.JOBS.get(job, {}).get("serial"))
            for c in res.get("categories", []):
                if not c.get("selectable", True):
                    advice.append({"target": tg, "title": c["title"], "desc": c["desc"], "risk": c["risk"], "size": c["size"],
                                   "action": c.get("action"), "items": [{k: i[k] for k in ("path", "name", "size", "note") if k in i}
                                                                          for i in c.get("items", [])[:12]]})
                    continue
                category_id = c.get("id")
                unique = [{"path": i["path"], **{k: i["unique"].get(k) for k in ("count", "size", "complete")}}
                          for i in c.get("items", []) if i.get("unique")]
                desc = c["desc"]
                # node_modules قد تكون في مجلدات عمل نشطة لوكلاء آخرين: للمراجعة لا تُحدَّد تلقائيًا
                on = c["risk"] in ("safe", "rebuild") and category_id != "node-modules"
                group = "cache"
                extra = {"notes": [f'{i["path"]} — {i["note"]}' for i in c.get("items", []) if i.get("note")]}
                if category_id == "icloud-archives":
                    on = False
                    extra["unique"] = unique
                    complete = bool(unique) and all(u.get("complete") for u in unique)
                    desc += " كل ملفاته موجودة في مكان آخر" if complete and all(u.get("count", 0) == 0 for u in unique) else " فيه ملفات غير موجودة في أي مكان آخر — انقلها أولًا"
                if serial:
                    group, on = "phone", category_id in ("app-caches", "thumbs", "device-logs")
                    desc += " (يُحذف نهائيًا من الهاتف)"
                    extra["device"] = True
                add(group, c["title"], desc, c["risk"], c["size"], [i["path"] for i in c["items"]], job, tg, on,
                    [f'{i["path"]} ({i["size"] >> 20} MB)' for i in c["items"][:12]], **extra)
        elif kind == "empty":
            paths = res.get("dirs") or []
            add("empty", "مجلدات فارغة", "مجلدات بلا أي ملف: حذفها آمن.", "safe", 0, paths, job, tg, True)
        elif kind == "duplicates":
            paths, size = [], 0
            sample = []
            for g in res.get("groups", []):
                extra = [f["path"] for f in g["files"][1:]]
                paths += extra
                size += g["wasted"]
                if len(sample) < 12:
                    sample.append(f'{extra[0]} ← مكرر لـ {g["files"][0]["path"]}')
            add("dup", "ملفات مكررة تمامًا (يُبقى نسخة واحدة)", "نسخ مطابقة بايتًا ببايت؛ يُبقى الأنسب بحسب قواعد الاحتفاظ، وتُنقل البقية إلى السلة.", "review", size, paths, job, tg, True, sample)
        elif kind == "large":
            files = res.get("files") or []
            old = [x for x in files if x.get("old")]
            add("large", "ملفات كبيرة لم تُعدَّل منذ سنة", "للمراجعة اليدوية فقط: لا تُحدَّد تلقائيًا.", "review", sum(x["size"] for x in old), [x["path"] for x in old], job, tg, False,
                [f'{x["path"]} ({x["size"] >> 20} MB)' for x in old[:12]])
    groups = {}
    for it in items:
        g = groups.setdefault(it["group"], {"count": 0, "size": 0})
        g["count"] += it["count"]
        g["size"] += it["size"]
    safe_total = sum(i["size"] for i in items if i["default_on"])
    return {"items": items, "overview": overview, "groups": groups, "advice": advice, "recommended_size": safe_total,
            "total_size": sum(i["size"] for i in items)}


def ask_ai(f, results, plan) -> str:
    """يطلب من الوكيل الأساسي قراءة الخلاصة وكتابة رؤيته؛ إن تعذّر يبقى التحليل الآلي وحده."""
    try:
        import agent_runner
        import council_agents
        agent = f.get("agent") or agent_runner.settings().get("default_agent") or "agy"
        lines = []
        for o in plan["overview"]:
            lines.append(f"- {o['target']}: الحجم {o['total'] >> 20} MB في {o['files']} ملف؛ الأنواع: " + "، ".join(f"{t['name']} {t['size'] >> 20}MB" for t in o["types"]) +
                         "؛ أكبر العناصر: " + "، ".join(f"{t['name']} {t['size'] >> 20}MB" for t in o["top"]))
        for it in plan["items"]:
            lines.append(f"* [{it['group']}/{it['risk']}] {it['target']} — {it['title']}: {it['count']} عنصر، {it['size'] >> 20} MB")
        for card in ((f.get("health") or {}).get("cards") or []):
            if card.get("status") != "ok":
                lines.append(f"! صحة: {card.get('title', '')}: {card.get('summary', '')}")
        for target, health_data in f.get("phone_health", {}).items():
            for card in health_data.get("cards", []):
                if card.get("status") != "ok":
                    lines.append(f"! صحة: {target} — {card.get('title', '')}: {card.get('summary', '')}")
        for entry in plan.get("advice", []):
            lines.append(f"~ يحتاج خطوة من المستخدم: {entry['target']} — {entry['title']} {entry['size'] >> 20} MB")
        prompt = ("أنت مستشار تنظيف ملفات داخل برنامج زاجل. هذه نتيجة فحص آلي لأجهزة وأقراص وسحابات المستخدم (لا تخترع أي مسار أو رقم غير موجود هنا):\n"
                  + "\n".join(lines) +
                  "\n\nلا تقترح حذف أي بند من بنود «يحتاج خطوة من المستخدم»؛ هذه معلومات أو خطوات إرشادية وليست عناصر حذف. "
                  "اكتب بالعربية، في أقل من 180 كلمة وبنقاط قصيرة: (١) تقييمك للوضع العام وأين تضيع المساحة. (٢) ترتيب التنفيذ الأنسب ولماذا. "
                  "(٣) ما الذي يجب مراجعته يدويًا قبل الحذف، وأي مخاطر. (٤) اقتراحات تحسين دائمة (عادات أو أتمتة) تمنع عودة الفوضى. لا تنفّذ شيئًا ولا تستعمل أدوات.")
        res = council_agents.run(agent, prompt, depth="fast", timeout=120)
        return (res.get("text") or "").strip() if res.get("ok") else ""
    except Exception:  # noqa: BLE001
        return ""


def apply(fid: str, item_ids: list[str]) -> dict:
    f = FULL.get(fid)
    if not f or f["state"] != "ready":
        raise ValueError("الخطة غير جاهزة أو انتهت صلاحيتها؛ أعد التنظيف الكامل.")
    chosen = [i for i in f["plan"]["items"] if i["id"] in set(item_ids)]
    if not chosen:
        raise ValueError("لم تُحدَّد أي بنود.")
    f["state"], f["progress"], f["cancel"] = "applying", "يبدأ التنفيذ…", False
    threading.Thread(target=_apply, args=(f, chosen), daemon=True).start()
    return public(f)


def _apply(f, chosen):
    report = {"ok": 0, "failed": 0, "freed": 0, "items": []}
    try:
        for n, it in enumerate(chosen, 1):
            if f["cancel"]:
                break
            f["progress"] = f"({n}/{len(chosen)}) {it['target']} — {it['title']}"
            ok = bad = 0
            for part in _chunks(it["paths"]):
                if f["cancel"]:
                    break
                try:
                    if C.JOBS.get(it["job"], {}).get("serial"):
                        import adbclean
                        rep = adbclean.remove(C.JOBS[it["job"]], part)
                    else:
                        rep = C.remove(it["job"], part, False)
                except Exception as exc:  # noqa: BLE001
                    bad += len(part)
                    report["items"].append({"title": it["title"], "error": str(exc)})
                    continue
                ok += sum(1 for r in rep if r["ok"])
                bad += sum(1 for r in rep if not r["ok"])
            report["ok"] += ok
            report["failed"] += bad
            if bad == 0 or ok:
                report["freed"] += it["size"] * (ok / max(1, it["count"]))
            report["items"].append({"title": it["title"], "target": it["target"], "ok": ok, "failed": bad})
        f["report"] = report
        f["state"], f["progress"] = "done", "اكتمل التنفيذ"
    except Exception as exc:  # noqa: BLE001
        f["state"], f["error"] = "error", str(exc)


def cancel(fid: str):
    f = FULL.get(fid)
    if f:
        f["cancel"] = True
    return {"ok": True}
