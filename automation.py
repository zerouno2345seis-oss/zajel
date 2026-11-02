"""أتمتة زاجل: قواعد تراقب مجلدًا كل مدة، وفي كل مرة تتصرف في «الجديد فقط» (إشعار، نسخ، نقل).
- إنشاء القاعدة يمرّ بحارس المساعد (النقل يحتاج موافقة المستخدم الصريحة عند الإنشاء)، وبعدها تعمل دون سؤال داخل حدودها المعلنة.
- لا حذف أبدًا؛ سقف ١٠٠ عنصر في كل دورة؛ الوجهة لا تكون داخل المجلد المراقَب (منعًا للدوران).
- العناصر التي تُنزَّل الآن (تعديل خلال ٩٠ ثانية أو لاحقة جزئية) تُؤجَّل للدورة التالية.
- تعمل ما دام زاجل مفتوحًا."""
import fnmatch
import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

DATA = None
LOCK = threading.RLock()
MAX_RULES, MAX_NOTICES, MAX_SEEN, PER_RUN = 12, 100, 4000, 100
MIN_EVERY, MAX_EVERY = 2, 1440
PARTIAL = (".crdownload", ".part", ".download", ".tmp", ".partial", ".opdownload")
SETTLE_MS = 90_000
_err_last = {}


def init(data_dir):
    global DATA
    DATA = Path(data_dir)


def _load(name, default):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(name, obj):
    p = DATA / name
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def rules_list():
    with LOCK:
        return _load("automations.json", [])


def notices_list():
    with LOCK:
        return _load("assistant_notices.json", [])


def notice_add(rule_name, text, level="info"):
    with LOCK:
        d = notices_list()
        d.insert(0, {"id": uuid.uuid4().hex[:8], "t": time.time(), "rule": rule_name, "text": text[:400], "level": level, "read": False})
        _save("assistant_notices.json", d[:MAX_NOTICES])
    try:   # إشعار نظام الماك (اختياري؛ يفشل بصمت إن لم يُسمح)
        msg = text.replace('"', "'")[:120]
        subprocess.Popen(["/usr/bin/osascript", "-e", f'display notification "{msg}" with title "زاجل — {rule_name.replace(chr(34), "")[:40]}"'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def notices_read(ids=None):
    with LOCK:
        d = notices_list()
        for n in d:
            if ids is None or n["id"] in ids:
                n["read"] = True
        _save("assistant_notices.json", d)


# ---------- التحقق ----------
def _inside(parent, child):
    p, c = str(parent or "").strip("/"), str(child or "").strip("/")
    return c == p or (p != "" and c.startswith(p + "/")) or p == ""


def validate(a):
    """يفحص المواصفة قبل أي حفظ أو طلب موافقة؛ يرمي ValueError عربيًا. يعيد مواصفة منظَّفة."""
    import agent_tools as T
    name = " ".join(str(a.get("name") or "").split())[:60]
    if not name:
        raise ValueError("سمِّ القاعدة.")
    try:
        every = int(a.get("every_minutes") or 0)
    except (TypeError, ValueError):
        every = 0
    if not MIN_EVERY <= every <= MAX_EVERY:
        raise ValueError(f"المدة بين {MIN_EVERY} دقيقتين و{MAX_EVERY} دقيقة (يوم كامل).")
    wp, wpath = str(a.get("watch_place") or ""), str(a.get("watch_path") or "")
    if not wp:
        raise ValueError("حدّد المكان المراقَب.")
    T.check_place_path(wp, wpath)
    kind = a.get("kind") or "any"
    if kind not in ("any", "files", "folders"):
        raise ValueError("النوع: any أو files أو folders.")
    pattern = str(a.get("pattern") or "")[:60]
    acts = []
    for x in (a.get("actions") or [{"type": "notify"}])[:3]:
        typ = str(x.get("type") or "")
        if typ not in ("notify", "copy", "move"):
            raise ValueError("الإجراء: notify أو copy أو move فقط (لا حذف في الأتمتة).")
        if typ == "notify":
            acts.append({"type": "notify"})
            continue
        tp, tpath = str(x.get("to_place") or ""), str(x.get("to_path") or "")
        if not tp or not tpath:
            raise ValueError("حدّد وجهة النسخ/النقل (المكان والمجلد).")
        T.check_place_path(tp, tpath)
        if tp == wp and _inside(wpath, tpath):
            raise ValueError("الوجهة داخل المجلد المراقَب؛ ستدور القاعدة على نفسها. اختر وجهة خارجه.")
        acts.append({"type": typ, "to_place": tp, "to_path": tpath})
    if not any(x["type"] != "notify" for x in acts) and not acts:
        acts = [{"type": "notify"}]
    return {"name": name, "every": every, "watch": {"place": wp, "path": wpath.strip("/") if not wpath.startswith("/") else wpath, "kind": kind, "pattern": pattern},
            "actions": acts, "include_existing": bool(a.get("include_existing"))}


def has_move(a):
    return any(isinstance(x, dict) and x.get("type") == "move" for x in (a.get("actions") or []))


# ---------- القواعد ----------
def add_rule(a, H):
    spec = validate(a)
    with LOCK:
        rules = rules_list()
        if len(rules) >= MAX_RULES:
            raise ValueError(f"بلغت الحد الأقصى ({MAX_RULES} قاعدة)؛ احذف قاعدة قديمة.")
        r = {"id": uuid.uuid4().hex[:8], "name": spec["name"], "enabled": True, "every": spec["every"], "watch": spec["watch"], "actions": spec["actions"],
             "seen": [], "baseline": bool(spec["include_existing"]), "created": time.time(), "last_run": 0, "next_run": time.time() + 5,
             "runs": 0, "items": 0, "last_note": "في انتظار أول فحص"}
        rules.append(r)
        _save("automations.json", rules)
    return public(r)


def public(r):
    return {k: r[k] for k in ("id", "name", "enabled", "every", "watch", "actions", "created", "last_run", "next_run", "runs", "items", "last_note")}


def delete_rule(rid):
    with LOCK:
        _save("automations.json", [r for r in rules_list() if r["id"] != rid])


def set_enabled(rid, enabled):
    with LOCK:
        rules = rules_list()
        for r in rules:
            if r["id"] == rid:
                r["enabled"] = bool(enabled)
                r["next_run"] = time.time() + 3
        _save("automations.json", rules)


def _save_rule(r):
    with LOCK:
        rules = rules_list()
        for i, x in enumerate(rules):
            if x["id"] == r["id"]:
                rules[i] = r
        _save("automations.json", rules)


# ---------- التنفيذ ----------
def _list(H, w):
    import agent_tools as T
    res = T.TOOLS["list_folder"]["run"]({"place": w["place"], "path": w["path"]}, H)
    return res.get("entries") or []


def _match(e, w):
    if w["kind"] == "files" and e.get("is_dir"):
        return False
    if w["kind"] == "folders" and not e.get("is_dir"):
        return False
    return not w["pattern"] or fnmatch.fnmatch(e.get("name", "").lower(), w["pattern"].lower())


def run_rule(r, H, force=False):
    import agent_tools as T
    now = time.time()
    w = r["watch"]
    entries = _list(H, w)
    if not r["baseline"]:
        r["seen"] = [e["name"] for e in entries][-MAX_SEEN:]
        r["baseline"] = True
        r["last_note"] = f"بدأت المراقبة؛ {len(entries)} عنصرًا موجودًا لا يُعدّ جديدًا"
    else:
        seen = set(r["seen"])
        fresh = [e for e in entries if e.get("name") and e["name"] not in seen and _match(e, w)]
        ready = [e for e in fresh if not e["name"].lower().endswith(PARTIAL) and (now * 1000 - (e.get("mod") or 0)) > SETTLE_MS]
        batch = ready[:PER_RUN]
        if batch:
            names = [e["name"] for e in batch]
            paths = [e["path"] for e in batch]
            did = []
            for act in r["actions"]:
                if act["type"] == "notify":
                    continue
                args = {"from_place": w["place"], "paths": paths, "to_place": act["to_place"], "to_dir": act["to_path"]}
                T.TOOLS["copy_items" if act["type"] == "copy" else "move_items"]["run"](args, H)
                did.append(("نُسخ" if act["type"] == "copy" else "نُقل") + f" إلى {act['to_path']}")
            r["seen"] = (r["seen"] + names)[-MAX_SEEN:]
            r["items"] += len(names)
            sample = "، ".join(names[:4]) + (f" و{len(names) - 4} آخر" if len(names) > 4 else "")
            text = f"{len(names)} جديد في «{w['path'] or w['place']}»: {sample}" + ("؛ " + "، ".join(dict.fromkeys(did)) if did else "")
            notice_add(r["name"], text)
            r["last_note"] = text[:160]
        else:
            r["last_note"] = "لا جديد" + (f" ({len(fresh)} قيد الإكمال)" if fresh else "")
    r["last_run"] = now
    r["next_run"] = now + r["every"] * 60
    r["runs"] += 1
    _save_rule(r)
    return r["last_note"]


def run_now(rid, H):
    for r in rules_list():
        if r["id"] == rid:
            return run_rule(r, H, force=True)
    raise ValueError("القاعدة غير موجودة.")


def scheduler(helper_factory):
    """كل ٢٠ ثانية ينفّذ القواعد المستحقة. أخطاء قاعدة لا توقف غيرها، وتُبلَّغ مرة كل ساعة."""
    while True:
        time.sleep(20)
        try:
            for r in rules_list():
                if r["enabled"] and time.time() >= r.get("next_run", 0):
                    try:
                        run_rule(r, helper_factory())
                    except Exception as exc:
                        r["next_run"] = time.time() + min(r["every"], 10) * 60
                        r["last_note"] = "تعذّر الفحص: " + str(exc)[:120]
                        _save_rule(r)
                        if time.time() - _err_last.get(r["id"], 0) > 3600:
                            _err_last[r["id"]] = time.time()
                            notice_add(r["name"], r["last_note"], "error")
        except Exception:
            pass
