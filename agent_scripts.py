"""سكربتات المساعد: يكتبها المساعد في مجلد خاص ويبقى لها فهرس يتذكره، ولا تعمل إلا بعد موافقة المستخدم على نصّها الظاهر له.
- الكتابة لا تشغّل شيئًا. التشغيل أحمر: المعاينة تعرض الكود نفسه وتنبّه إلى الأوامر الخطرة.
- الموافقة مربوطة ببصمة النص: لو تغيّر الملف بين الموافقة والتشغيل يُرفض.
- يعمل بصلاحيات المستخدم نفسه، بمهلة، وبيئة مقلَّصة بلا مفتاح الوكيل، وناتجه يُحفظ في سجل ويصل إشعارًا حين ينتهي."""
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

DATA = None
M = None   # وحدة زاجل الرئيسية (لتسجيل التشغيل في قائمة العمليات)
PROG_RE = re.compile(r"^ZAJEL_PROGRESS\s+(\d+)\s*/\s*(\d+)\s*(.*)$")
RES_RE = re.compile(r"^ZAJEL_RESULT\s+(.*)$")
PHONE_SERIAL = lambda: ""   # يضبطها الخادم: عنوان الهاتف المتصل الآن (كابل أو ip:port)
LOCK = threading.RLock()
RUNS = {}
MAX_CODE = 64_000
NAME_RE = re.compile(r"^[A-Za-z0-9_\-؀-ۿ]{1,60}\.(py|sh)$")
RISKY = [(r"\brm\s+-[a-zA-Z]*[rf]", "حذف بـ rm"), (r"shutil\.rmtree", "حذف مجلدات (rmtree)"), (r"os\.(remove|unlink|rmdir)|\bunlink\(", "حذف ملفات"),
         (r"\bsudo\b", "صلاحيات المدير (sudo)"), (r"curl[^\n|]*\|\s*(ba|z)?sh|wget[^\n|]*\|\s*(ba|z)?sh", "تنزيل وتشغيل مباشر"), (r"\bdiskutil\b|\bmkfs\b|\bdd\s+if=", "عمليات أقراص"),
         (r"requests\.|urllib\.request|\bcurl\b|\bwget\b|socket\.", "اتصال بالإنترنت"), (r"subprocess|os\.system|os\.popen", "تشغيل أوامر نظام"),
         (r"\.ssh|Keychain|security\s+find|\.aws|\.env\b|password", "قد يمسّ أسرارًا")]


def init(data_dir):
    global DATA
    DATA = Path(data_dir)
    (DATA / "scripts" / "logs").mkdir(parents=True, exist_ok=True)


def _dir():
    return DATA / "scripts"


def _idx():
    try:
        return json.loads((_dir() / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_idx(d):
    p = _dir() / "index.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def sha(name):
    return hashlib.sha256((_dir() / name).read_bytes()).hexdigest()[:16]


def flags(code):
    return [label for rx, label in RISKY if re.search(rx, code)]


def _tags(tags):
    out = []
    for t in (tags if isinstance(tags, list) else str(tags or '').replace('،', ',').split(','))[:6]:
        t = ' '.join(str(t).split())[:20]
        if t and t not in out:
            out.append(t)
    return out


def clean_params(params):
    """معطيات السكربت المعلنة (تُرسَم نموذجًا في الواجهة وتُمرَّر بالترتيب): name, label, type(text|number|folder|choice), default, required, placeholder, options."""
    out = []
    for x in (params if isinstance(params, list) else [])[:6]:
        if not isinstance(x, dict):
            continue
        typ = x.get("type") if x.get("type") in ("text", "number", "folder", "choice") else "text"
        nm = re.sub(r"[^A-Za-z0-9_]", "", str(x.get("name") or ""))[:30] or f"arg{len(out) + 1}"
        out.append({"name": nm, "label": " ".join(str(x.get("label") or nm).split())[:40], "type": typ, "default": str(x.get("default") or "")[:200],
                    "required": bool(x.get("required")), "placeholder": str(x.get("placeholder") or "")[:80],
                    "options": [str(o)[:60] for o in (x.get("options") or [])[:8]] if typ == "choice" else []})
    return out


def build_args(name, values):
    """يحوّل قيم النموذج إلى معطيات موضعية بترتيب الإعلان، بعد التحقق من المطلوب والنوع."""
    params = _idx().get(name, {}).get("params", [])
    values = values if isinstance(values, dict) else {}
    args = []
    for p_ in params:
        v = str(values.get(p_["name"], "") if values.get(p_["name"]) is not None else "").strip() or p_["default"]
        if not v and p_["required"]:
            raise ValueError(f"الحقل «{p_['label']}» مطلوب.")
        if v and p_["type"] == "number" and not re.fullmatch(r"\d+", v):
            raise ValueError(f"الحقل «{p_['label']}» يجب أن يكون رقمًا.")
        if v and p_["type"] == "choice" and p_["options"] and v not in p_["options"]:
            raise ValueError(f"اختر قيمة صحيحة في «{p_['label']}».")
        args.append(v)
    while args and args[-1] == "":
        args.pop()
    return args


def write(name, code, desc, title='', tags=None, params=None):
    name = str(name or "").strip()
    if not NAME_RE.match(name):
        raise ValueError("اسم السكربت: حروف وأرقام وشرطات فقط وينتهي بـ .py أو .sh")
    code = str(code or "")
    if not code.strip() or len(code) > MAX_CODE:
        raise ValueError(f"النص فارغ أو أكبر من {MAX_CODE} حرف.")
    desc = " ".join(str(desc or "").split())[:240]
    if not desc:
        raise ValueError("اكتب وصفًا قصيرًا لما يفعله السكربت (يتذكره المساعد به لاحقًا).")
    if name.endswith(".py"):
        compile(code, name, "exec")   # أخطاء الصياغة تظهر الآن لا عند التشغيل
    with LOCK:
        idx = _idx()
        if name not in idx and len(idx) >= 60:
            raise ValueError("بلغ المجلد 60 سكربتًا؛ احذف قديمًا أولًا.")
        (_dir() / name).write_text(code, encoding="utf-8")
        old = idx.get(name, {})
        idx[name] = {"title": " ".join(str(title or old_title(idx, name)).split())[:60], "tags": _tags(tags) if tags is not None else idx.get(name, {}).get("tags", []),
                     "params": clean_params(params) if params is not None else idx.get(name, {}).get("params", []), "desc": desc, "created": old.get("created") or time.time(), "updated": time.time(), "runs": old.get("runs", 0), "last_run": old.get("last_run", 0),
                     "last_state": old.get("last_state", ""), "sha": sha(name)}
        _save_idx(idx)
    return {"name": name, "path": str(_dir() / name), "bytes": len(code.encode()), "flags": flags(code), "note": "كُتب ولم يُشغَّل. التشغيل يحتاج موافقة المستخدم."}


def old_title(idx, name):
    return idx.get(name, {}).get('title', '')


def listing():
    idx = _idx()
    return [{"name": k, "title": v.get("title") or k, "tags": v.get("tags", []), "desc": v["desc"], "runs": v.get("runs", 0), "last_run": v.get("last_run", 0), "last_state": v.get("last_state", ""),
             "updated": v.get("updated", 0), "created": v.get("created", 0), "params": v.get("params", [])} for k, v in sorted(idx.items(), key=lambda kv: -(kv[1].get("last_run") or kv[1].get("updated") or 0))]


def get(name):
    code = read(name)
    m = listing_one(name)
    return m | {"code": code, "flags": flags(code), "sha": sha(name), "bytes": len(code.encode())}


def listing_one(name):
    return next(x for x in listing() if x["name"] == name)


def meta_update(name, title, desc, tags, params=None):
    with LOCK:
        idx = _idx()
        if name not in idx:
            raise ValueError("السكربت غير موجود.")
        if title is not None:
            idx[name]["title"] = " ".join(str(title).split())[:60]
        if desc is not None:
            idx[name]["desc"] = " ".join(str(desc).split())[:240] or idx[name]["desc"]
        if tags is not None:
            idx[name]["tags"] = _tags(tags)
        if params is not None:
            idx[name]["params"] = clean_params(params)
        _save_idx(idx)


def read(name):
    if name not in _idx():
        raise ValueError("السكربت غير موجود.")
    return (_dir() / name).read_text(encoding="utf-8")


def delete(name):
    with LOCK:
        idx = _idx()
        if name not in idx:
            raise ValueError("السكربت غير موجود.")
        try:
            (_dir() / name).unlink()
        except OSError:
            pass
        idx.pop(name)
        _save_idx(idx)


def preview(name, args, timeout):
    code = read(name)
    return {"description": _idx()[name]["desc"], "code": code[:3500] + ("\n… (مقتطع؛ النص الكامل " + str(len(code)) + " حرفًا)" if len(code) > 3500 else ""),
            "flags": flags(code), "args": args, "timeout_min": round(timeout / 60), "sha": sha(name)}


def start(name, args, timeout, expect_sha, on_done=None):
    if name not in _idx():
        raise ValueError("السكربت غير موجود.")
    if expect_sha and sha(name) != expect_sha:
        raise ValueError("تغيّر نص السكربت بعد طلب الموافقة؛ اطلب من المساعد تشغيله من جديد لتراجعه.")
    if sum(1 for r in RUNS.values() if r["state"] == "running") >= 2:
        raise ValueError("يعمل سكربتان الآن؛ انتظر.")
    rid = uuid.uuid4().hex[:8]
    path = _dir() / name
    interp = [sys.executable if sys.executable and not getattr(sys, "frozen", False) else "python3", "-u", str(path)] if name.endswith(".py") else ["/bin/bash", str(path)]
    log = _dir() / "logs" / f"{rid}-{name}.log"
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"), "HOME": str(Path.home()), "LANG": "en_US.UTF-8", "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
           "USER": os.environ.get("USER", ""), "ZAJEL_SCRIPT": name}
    try:
        env["ZAJEL_ADB_SERIAL"] = PHONE_SERIAL() or ""
    except Exception:
        pass
    run = {"id": rid, "name": name, "state": "running", "started": time.time(), "log": str(log), "code": None}
    RUNS[rid] = run
    with LOCK:
        idx = _idx()
        idx[name]["runs"] = idx[name].get("runs", 0) + 1
        idx[name]["last_run"] = time.time()
        idx[name]["last_state"] = "running"
        _save_idx(idx)

    op = None
    try:
        if M is not None:
            op = M.fileops.new_op("copy", {"name": name}, 0)
            op["title"] = "سكربت: " + name
            op["current"] = "يبدأ…"
            run["op"] = op["id"]
    except Exception:
        op = None

    def parse(chunk, seen):
        for line in chunk.splitlines():
            line = line.strip()
            m = PROG_RE.match(line)
            if m:
                seen["prog"] = True
                if op is not None:
                    op["total"] = int(m.group(2))
                    op["done"] = min(int(m.group(1)), int(m.group(2)) or int(m.group(1)))
                    if m.group(3):
                        op["current"] = m.group(3)[:200]
                continue
            m = RES_RE.match(line)
            if m:
                seen["result"] = m.group(1)[:300]
            elif line and op is not None and not seen.get("prog"):
                op["current"] = line[:200]
            if line:
                seen["last"] = line[:300]

    def go():
        seen = {}
        try:
            with open(log, "w", encoding="utf-8") as fh:
                p = subprocess.Popen(interp + [str(a) for a in args][:20], cwd=str(Path.home()), env=env, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
                run["proc"] = p
                if op is not None:
                    op["proc"] = p
                pos, t0 = 0, time.time()
                while p.poll() is None:
                    time.sleep(0.6)
                    try:
                        with open(log, "r", encoding="utf-8", errors="replace") as rf:
                            rf.seek(pos)
                            chunk = rf.read()
                            pos = rf.tell()
                        parse(chunk, seen)
                    except OSError:
                        pass
                    if op is not None and op.get("cancel"):
                        run["cancelled"] = True
                        os.killpg(p.pid, 9)
                    elif time.time() - t0 > timeout:
                        p.kill()
                        run["timed_out"] = True
                p.wait()
            try:
                with open(log, "r", encoding="utf-8", errors="replace") as rf:
                    rf.seek(pos)
                    parse(rf.read(), seen)
            except OSError:
                pass
            run["code"] = p.returncode
            run["state"] = "done" if p.returncode == 0 else "error"
        except Exception as exc:
            run["state"] = "error"
            run["note"] = str(exc)
        finally:
            run["ended"] = time.time()
            run.pop("proc", None)
            if op is not None:
                op.pop("proc", None)
                op["current"] = ""
                if run["state"] == "done":
                    op["state"] = "done"
                    op["detail"] = seen.get("result") or seen.get("last") or "انتهى"
                    if op["total"] and op["done"] < op["total"]:
                        op["detail"] += f" ({op['done']} من {op['total']})"
                else:
                    op["state"] = "cancelled" if run.get("cancelled") else "error"
                    op["errors"].append("أُلغي" if run.get("cancelled") else ("انتهت المهلة" if run.get("timed_out") else f"رمز الخروج {run.get('code')}: {seen.get('last', '')}"[:300]))
                op["ended"] = time.time()
                try:
                    M.fileops.persist(op)
                except Exception:
                    pass
            with LOCK:
                idx2 = _idx()
                if name in idx2:
                    idx2[name]["last_state"] = run["state"]
                    _save_idx(idx2)
            if on_done:
                try:
                    on_done(run)
                except Exception:
                    pass
    threading.Thread(target=go, daemon=True).start()
    return {"run": rid, "name": name, "note": "بدأ التشغيل في الخلفية؛ تصلك رسالة حين ينتهي، وscript_status يعرض الناتج."}


def status(rid):
    r = RUNS.get(rid)
    if not r:
        raise ValueError("التشغيل غير موجود.")
    try:
        out = Path(r["log"]).read_text(encoding="utf-8", errors="replace")
    except OSError:
        out = ""
    return {"run": rid, "name": r["name"], "state": r["state"], "exit_code": r["code"], "timed_out": bool(r.get("timed_out")), "seconds": round((r.get("ended") or time.time()) - r["started"]),
            "output_tail": out[-2500:], "note": r.get("note", "")}


def stop(rid):
    r = RUNS.get(rid)
    p = r and r.get("proc")
    if p:
        p.kill()
        return True
    return False
