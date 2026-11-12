"""مصادر الجولة والاتصال بالمكتبات والدفاتر."""
import json
import os
import queue
import re
import subprocess
import threading
import time
from pathlib import Path

DATA = None
LIBRARIES = [
    {"id": "shamela", "name": "المكتبة الشاملة"},
    {"id": "aljam3:3", "name": "الجامع — المكتبة الشاملة الوقفية"},
    {"id": "aljam3:2", "name": "الجامع — المكتبة الوقفية"},
    {"id": "aljam3:1", "name": "الجامع — مكتبة المسجد النبوي"},
]


def _env():
    env = os.environ.copy()
    extra = [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".opencode/bin")]
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", os.defpath)])
    return env


def _run(argv, timeout, inp=None):
    p = subprocess.run(argv, input=inp, capture_output=True, text=True, timeout=timeout, env=_env())
    return p.returncode, p.stdout, p.stderr


RUN = _run


def init(data_dir):
    global DATA
    DATA = Path(data_dir)
    DATA.mkdir(parents=True, exist_ok=True)


def _data():
    if DATA is not None:
        return Path(DATA)
    try:
        import terminal
        return Path(terminal.DATA) if terminal.DATA is not None else Path.home()
    except Exception:
        return Path.home()


def _read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def catalog(refresh=False):
    result = {"libraries": [dict(x) for x in LIBRARIES], "notebooks": [], "notebooks_error": ""}
    cache = _read(_data() / "sources_cache.json", {})
    if not refresh and isinstance(cache, dict) and isinstance(cache.get("time"), (int, float)) and 0 <= time.time() - cache["time"] < 600 and isinstance(cache.get("notebooks"), list):
        result["notebooks"] = cache["notebooks"]
        return result
    try:
        code, out, err = RUN(["notebooklm", "list", "--json"], 30)
        if code:
            raise ValueError(err or out or "فشل عرض الدفاتر")
        data = json.loads(out)
        notebooks = data.get("notebooks", []) if isinstance(data, dict) else data
        if not isinstance(notebooks, list):
            raise ValueError("صيغة قائمة الدفاتر غير صالحة")
        for nb in notebooks:
            if isinstance(nb, dict) and nb.get("id"):
                ident = str(nb["id"])
                result["notebooks"].append({"id": ident, "title": str(nb.get("title") or "(بلا عنوان) " + ident[:8]), "owner": bool(nb.get("owner", nb.get("is_owner", False)))})
        _write(_data() / "sources_cache.json", {"time": time.time(), "notebooks": result["notebooks"]})
    except Exception as exc:
        result["notebooks_error"] = "تعذّر جلب الدفاتر: " + str(exc)
    return result


def get_selection():
    default = {"libraries": [], "notebooks": [], "nb_mode": "answer"}
    data = _read(_data() / "sources.json", default)
    if not isinstance(data, dict):
        return default
    libs = data.get("libraries")
    valid = {item["id"] for item in LIBRARIES}
    libs = [x for x in libs if isinstance(x, str) and x in valid] if isinstance(libs, list) else []
    notebooks, seen = [], set()
    raw = data.get("notebooks")
    for nb in raw if isinstance(raw, list) else []:
        if not isinstance(nb, dict) or not isinstance(nb.get("id"), str) or not nb["id"].strip() or nb["id"] in seen:
            continue
        seen.add(nb["id"])
        notebooks.append({"id": nb["id"], "title": nb.get("title") if isinstance(nb.get("title"), str) else "", "on": nb.get("on") if isinstance(nb.get("on"), bool) else False})
        if len(notebooks) == 5:
            break
    mode = data.get("nb_mode")
    return {"libraries": libs, "notebooks": notebooks, "nb_mode": mode if mode in ("answer", "reference") else "answer"}


def set_selection(sel):
    if not isinstance(sel, dict):
        raise ValueError("اختيار المصادر غير صالح.")
    libs, notebooks, mode = sel.get("libraries", []), sel.get("notebooks", []), sel.get("nb_mode", "answer")
    if not isinstance(libs, list) or any(not isinstance(x, str) or x not in {v["id"] for v in LIBRARIES} for x in libs):
        raise ValueError("معرّف المكتبة غير معروف.")
    if not isinstance(notebooks, list) or len(notebooks) > 5:
        raise ValueError("يمكن اختيار خمسة دفاتر كحد أقصى.")
    clean, seen = [], set()
    for nb in notebooks:
        if not isinstance(nb, dict) or not isinstance(nb.get("id"), str) or not nb["id"].strip() or nb["id"] in seen:
            raise ValueError("معرّف الدفتر غير صالح أو مكرر.")
        if not isinstance(nb.get("title", ""), str) or not isinstance(nb.get("on", False), bool):
            raise ValueError("بيانات الدفتر غير صالحة.")
        seen.add(nb["id"])
        clean.append({"id": nb["id"], "title": nb.get("title", ""), "on": nb.get("on", False)})
    if mode not in ("answer", "reference"):
        raise ValueError("وضع الدفاتر غير صالح.")
    result = {"libraries": list(libs), "notebooks": clean, "nb_mode": mode}
    _write(_data() / "sources.json", result)
    return result


def ensure_agent(agent_id, libraries, force=False):
    if agent_id not in ("codex", "claude", "agy"):
        return {"ok": False, "note": "هذا الوكيل لا يدعم المصادر بعد", "added": []}
    added = []           # أسماء الوصلات التي سُجّلت فعلًا في هذا النداء (الوكيل الحيّ لا يراها حتى يُعاد تشغيله)
    try:
        needed = []
        if "shamela" in libraries:
            needed.append(("shamela-mcp" if agent_id == "agy" else "zajel_shamela", "/Users/mohamad/SHAMILA/server.py"))
        if any(x in ("aljam3:1", "aljam3:2", "aljam3:3") for x in libraries):
            needed.append(("aljam3" if agent_id == "agy" else "zajel_aljam3", "/Users/mohamad/SHAMILA/aljam3_mcp.py"))
        if not needed:
            return {"ok": True, "note": "", "added": []}
        cache_path = _data() / "sources_agents.json"
        cache = _read(cache_path, {})
        if not isinstance(cache, dict):
            cache = {}
        saved = cache.get(agent_id, [])
        confirmed = set(x for x in saved if isinstance(x, str)) if isinstance(saved, list) else set()
        if not force and all(name in confirmed for name, _ in needed):
            return {"ok": True, "note": "", "added": []}
        if force:
            confirmed.difference_update(name for name, _ in needed)
            cache[agent_id] = sorted(confirmed)
            _write(cache_path, cache)
        code, out, err = RUN([agent_id, "mcp", "list"], 30)
        if code:
            raise ValueError(err or out or "فشل عرض الوصلات")
        for name, path in needed:
            if re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", out):
                continue
            argv = [agent_id, "mcp", "add"]
            if agent_id == "claude":
                argv += ["-s", "user"]
            argv += [name] + ([] if agent_id == "agy" else ["--"]) + ["python3", path]
            code, msg, err = RUN(argv, 30)
            if code:
                raise ValueError(err or msg or "فشل تسجيل الوصلة")
            added.append(name)
        confirmed.update(name for name, _ in needed)
        cache[agent_id] = sorted(confirmed)
        _write(cache_path, cache)
        return {"ok": True, "note": "", "added": added}
    except Exception as exc:
        return {"ok": False, "note": "تعذّر إعداد وصلات المصادر: " + str(exc), "added": added}


def source_note(libraries, evidence_path=""):
    lines = []
    if evidence_path:
        lines.append("اقرأ أولًا ملف الأدلة: " + str(evidence_path))
    if libraries:
        names = [x["name"] for x in LIBRARIES if x["id"] in libraries]
        if names:
            lines.append("ابحث في المصادر المختارة: " + "، ".join(names) + ".")
            ids = [x.split(":", 1)[1] for x in libraries if x in ("aljam3:1", "aljam3:2", "aljam3:3")]
            if ids:
                lines.append("للبحث في الجامع استخدم library_id: " + "، ".join(ids) + ".")
            lines.append("ابحث بحثًا ذكيًا بأكثر من صياغة، وافتح الصفحة واقرأها قبل النقل. انقل النص حرفيًا مع الكتاب والمؤلف والجزء والصفحة، ورابط الصفحة للجامع. صرّح إن لم تتوفر لك أدوات أي مصدر.")
    return "\n\n" + "\n".join(lines) if lines else ""


def ask_notebook(nb_id, question, timeout=150):
    try:
        code, out, err = RUN(["notebooklm", "ask", "-n", nb_id, "--json", question], timeout)
        if code:
            raise ValueError(err or out or "فشل سؤال الدفتر")
        data = json.loads(out)
        answer = data["answer"]
        if not isinstance(answer, str) or not isinstance(data.get("references", []), list):
            raise ValueError("صيغة جواب الدفتر غير صالحة")
        raw = [r for r in data.get("references", []) if isinstance(r, dict)]
        titles = _source_titles(nb_id, {r.get("source_id") for r in raw if r.get("source_id")})
        refs = []
        for r in raw:
            text = str(r.get("cited_text") or "").strip()
            if not text:
                continue                        # cited_text يأتي null من بعض الدفاتر؛ ولا يمكن استرداد المقطع من الأداة (انظر _source_titles)
            ref = {"n": int(r["citation_number"]), "text": text}
            if titles.get(r.get("source_id")):
                ref["source"] = titles[r["source_id"]]
            refs.append(ref)
        result = {"ok": True, "answer": answer, "refs": refs, "note": ""}
        used = list(dict.fromkeys(titles[i] for i in (r.get("source_id") for r in raw) if titles.get(i)))
        if used:
            result["sources"] = used            # عناوين مصادر الدفتر التي استند إليها الجواب (حتى لو غابت المقاطع)
        return result
    except subprocess.TimeoutExpired:
        return {"ok": False, "answer": "", "refs": [], "note": "انتهت مهلة سؤال الدفتر."}
    except Exception as exc:
        return {"ok": False, "answer": "", "refs": [], "note": "تعذّر سؤال الدفتر: " + str(exc)}


def _source_titles(nb_id, ids):
    """معرّف المصدر ← عنوانه، من `notebooklm source list` (نداء واحد، مهلة ١٥ ثانية، أي فشل يعيد {}).
    لماذا لا نستخرج المقطع: start_char/end_char في مراجع ask تساوي موضع العلامة في الجواب (كلاهما نطاق من حرف واحد)
    وليست موضعًا في نص المصدر، فلا يمكن اقتطاع المقطع من `source fulltext`."""
    if not ids:
        return {}
    try:
        code, out, err = RUN(["notebooklm", "source", "list", "-n", nb_id, "--json"], 15)
        if code:
            return {}
        return {x["id"]: str(x.get("title") or "") for x in json.loads(out).get("sources", []) if isinstance(x, dict) and x.get("id") in ids}
    except Exception:
        return {}


NO_PASSAGES = "لم يُرجع الدفتر مقاطع حرفية"


def write_evidence(path, items):
    lines = ["# ملف الأدلة", ""]
    for item in items:
        lines.extend(["## " + str(item.get("title") or "(بلا عنوان)"), "", str(item.get("answer") or ""), ""])
        if item.get("sources"):
            lines.extend(["المصادر التي استند إليها الدفتر: " + "، ".join(str(x) for x in item["sources"]), ""])
        refs = [r for r in item.get("refs", []) if str(r.get("text") or "").strip()]
        lines.extend(["### المقاطع الحرفية", ""])
        if refs:
            for ref in refs:
                lines.append("[{}] {}".format(ref.get("n", ""), ref.get("text", "")))
        else:
            lines.append(NO_PASSAGES)
        lines.append("")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def _mcp_verify(quote):
    proc = subprocess.Popen(["python3", "/Users/mohamad/SHAMILA/server.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1, env=_env())
    responses = queue.Queue()
    def read():
        for line in proc.stdout:
            responses.put(line)
        responses.put(None)
    threading.Thread(target=read, daemon=True).start()
    deadline = time.monotonic() + 20
    def send(message):
        proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        proc.stdin.flush()
    def call(ident, method, params):
        send({"jsonrpc": "2.0", "id": ident, "method": method, "params": params})
        while True:
            line = responses.get(timeout=max(0, deadline - time.monotonic()))
            if line is None:
                raise ValueError("انقطع الخادم")
            data = json.loads(line)
            if data.get("id") == ident:
                if "error" in data:
                    err = data["error"]
                    raise ValueError("خطأ من الخادم: " + str(err.get("message", "") if isinstance(err, dict) else err)[:200])
                return data["result"]
    try:
        call(1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "zajel", "version": "1"}})
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        schema = call(2, "tools/list", {})
        tool = next(t for t in schema["tools"] if t.get("name") == "shamela_verify_quote")
        props = tool["inputSchema"]["properties"]
        if "quote" not in props:
            raise ValueError("مخطط الأداة غير صالح")
        args = {"quote": quote}
        if "response_format" in props:
            args["response_format"] = "json"
        return call(3, "tools/call", {"name": "shamela_verify_quote", "arguments": args})
    finally:
        proc.kill()
        proc.wait()
        proc.stdin.close()
        proc.stdout.close()


_VERIFY_LOCK = threading.Lock()    # الشاملة تسمح لحساب واحد بعدد محدود من النداءات المتزامنة (HTTP 429): نُسلسل الفحوص
RETRY_WAIT = 1.5


def _verify_serial(quote):
    with _VERIFY_LOCK:
        for attempt in range(3):
            try:
                return _mcp_verify(quote)
            except ValueError as exc:
                if attempt == 2 or "429" not in str(exc):
                    raise
                time.sleep(RETRY_WAIT)


def shamela_verify(quote):
    try:
        result = _verify_serial(quote)
        if result.get("isError"):
            return None
        data = result.get("structuredContent")
        if not isinstance(data, dict):
            text = next(c["text"] for c in result.get("content", []) if c.get("type") == "text")
            data = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip()))
        status = data.get("status")
        if status not in ("verbatim", "differs", "partial", "not_found", "found"):
            return None
        found = status in ("verbatim", "differs", "found")
        locations = data.get("locations") or []
        locations = [loc for loc in locations if isinstance(loc, dict)]
        def _ratio(x):
            try:
                return float(x["matched_words"]) / float(x["quote_words"])
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                return None
        best = max(locations, key=lambda x: _ratio(x) or 0.0) if locations else {}
        loc = next((loc for loc in locations if loc.get("match") == "verbatim"), best)
        where = "، ".join(str(x) for x in (loc.get("book_name"), loc.get("printed_page")) if x)
        return {"found": found, "where": where, "in_footnote": bool(loc) and loc.get("field") != "body", "url": loc.get("source_url") or "", "match": status, "ratio": _ratio(loc) if loc else None}
    except Exception:
        return None
