"""تشغيل الوكلاء ببيئة مقيدة."""
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = Path.home()
EXTRA_PATH = [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin",
              str(Path.home() / ".opencode/bin"), "/usr/bin", "/bin"]
_PROFILES = {}
_CHECKS = {}
_LOCK = threading.RLock()
_RUNNER = subprocess.Popen
_EFFORTS = ("low", "medium", "high", "max")
_DEFAULT_MODEL = {"opencode": "opencode/nemotron-3-ultra-free"}
_MCP_SERVERS = ("shamela", "الشاملة", "turath", "تراث", "tafsir", "تفسير", "quran",
                "bahouth", "fiqh", "library", "consensus", "pubmed")
_MCP_DENY = ("send", "create", "delete", "update", "write", "deploy", "trash", "label",
             "upload", "apply", "execute", "merge", "publish", "reply", "forward", "move",
             "rename", "share", "relay", "feedback", "settings")


def _default(agent_id):
    return {"model": _DEFAULT_MODEL.get(agent_id, ""), "effort": "high", "web": True,
            "mcp": True, "enabled": True}


def init(data_dir):
    """يحمل ملفات الإعداد إن توفرت."""
    global DATA, _PROFILES
    DATA = Path(data_dir)
    try:
        loaded = json.loads((DATA / "agent_profiles.json").read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            _PROFILES = {str(k): _clean_profile(str(k), v) for k, v in loaded.items() if isinstance(v, dict)}
    except (OSError, ValueError):
        _PROFILES = {}


def _clean_profile(agent_id, value):
    p = _default(agent_id)
    p.update({k: value[k] for k in p if k in value})
    if p["effort"] not in _EFFORTS:
        p["effort"] = "high"
    p["model"] = str(p["model"] or "")
    for key in ("web", "mcp", "enabled"):
        p[key] = bool(p[key])
    return p


def profiles():
    with _LOCK:
        return {k: dict(v) for k, v in _PROFILES.items()}


def set_profile(agent_id, patch):
    with _LOCK:
        profile = _clean_profile(agent_id, dict(_PROFILES.get(agent_id, _default(agent_id))))
        profile.update({k: patch[k] for k in profile if k in patch})
        profile = _clean_profile(agent_id, profile)
        _PROFILES[agent_id] = profile
        try:
            DATA.mkdir(parents=True, exist_ok=True)
            tmp = DATA / "agent_profiles.json.tmp"
            tmp.write_text(json.dumps(_PROFILES, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(DATA / "agent_profiles.json")
        except OSError:
            pass
        return dict(profile)


def _env():
    home = str(Path.home())
    return {"HOME": home, "USER": os.environ.get("USER", ""), "LOGNAME": os.environ.get("LOGNAME", os.environ.get("USER", "")),
            "SHELL": os.environ.get("SHELL", "/bin/zsh"), "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "TERM": os.environ.get("TERM", "xterm-256color"), "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
            "PATH": os.pathsep.join(EXTRA_PATH)}


def can_run(agent_id):
    name = {"claude": "claude", "codex": "codex", "agy": "agy", "hermes": "hermes", "opencode": "opencode"}.get(agent_id)
    return bool(name and shutil.which(name, path=os.pathsep.join(EXTRA_PATH)))


def _mcp_tools():
    try:
        data = json.loads((DATA / "agent_mcp_tools.json").read_text(encoding="utf-8"))
        if time.time() - float(data.get("time", 0)) < 86400 and isinstance(data.get("tools"), list):
            return data["tools"]
    except (OSError, ValueError, TypeError):
        pass
    return []


def _safe_mcp_tools():
    names = []
    for tool in _mcp_tools():
        name = str(tool.get("name", "")) if isinstance(tool, dict) else str(tool)
        low = name.lower()
        if any(server in low for server in _MCP_SERVERS) and not any(word in low for word in _MCP_DENY):
            names.append(name)
    return names


def _command(agent_id, prompt, profile, depth, add_dirs, answer_file, timeout=900):
    effort = "medium" if depth == "fast" else "max" if depth == "deep" else profile["effort"]
    model = profile["model"]
    if agent_id == "claude":
        allowed = ["Read", "Grep", "Glob"]
        if profile["web"]:
            allowed += ["WebSearch", "WebFetch"]
        allowed += ["Bash(pdftotext:*)", "Bash(textutil:*)", "Bash(ls:*)", "Bash(wc:*)", "Bash(head:*)"]
        if profile["mcp"]:
            allowed += _safe_mcp_tools()
        cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
               "--allowedTools"] + allowed + ["--disallowedTools", "Edit", "Write", "NotebookEdit"]
        # --add-dir و--allowedTools تقبلان قيمًا متعددة فتبتلعان السؤال إن جاء بعدهما؛ نختم بخيار ذي قيمة واحدة
        if add_dirs:
            cmd += ["--add-dir"] + [str(p) for p in add_dirs]
        cmd += ["--effort", effort]
        if model:
            cmd += ["--model", model]
        return cmd + [prompt]
    if agent_id == "codex":
        # --search (بحث الويب) خيار عام يأتي قبل exec لا بعده
        cmd = ["codex"] + (["--search"] if profile["web"] else []) + ["exec", "--skip-git-repo-check", "-s", "read-only", "--json", "-o", str(answer_file)]
        if model:
            cmd += ["-m", model]
        cmd += ["-c", 'model_reasoning_effort="' + effort + '"']
        for path in add_dirs:
            cmd += ["--add-dir", str(path)]
        return cmd + [prompt]
    if agent_id == "agy":
        minutes = max(1, int((timeout + 59) // 60))
        # -p يأخذ السؤال قيمةً له مباشرة، فيأتي آخرًا
        cmd = ["agy", "--mode", "plan", "--output-format", "stream-json", "--print-timeout", str(minutes) + "m"]
        if model:
            cmd += ["--model", model]
        return cmd + ["-p", prompt]
    if agent_id == "hermes":
        cmd = ["hermes", "-z", prompt, "--reasoning", effort]
        if model:
            cmd += ["-m", model]
        return cmd
    if agent_id == "opencode":
        return ["opencode", "run", "--agent", "plan", "-m", model or _DEFAULT_MODEL["opencode"], "--variant", effort, "--format", "json", prompt]
    raise ValueError("وكيل غير معروف")


def _save_mcp_tools(tools):
    try:
        (DATA / "agent_mcp_tools.json").write_text(json.dumps({"time": time.time(), "tools": [t for t in tools if str(t).startswith("mcp__")]},
                                                                 ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _activity(name, inp):
    """وصف عربي قصير لأداة يستعملها الوكيل."""
    inp = inp if isinstance(inp, dict) else {}
    arg = str(inp.get("query") or inp.get("pattern") or inp.get("file_path") or inp.get("url") or inp.get("command") or inp.get("q") or "")[:80]
    low = name.lower()
    if "shamela" in low:
        what = "يبحث في الشاملة"
    elif "turath" in low:
        what = "يبحث في تراث"
    elif "tafsir" in low or "quran" in low or "bahouth" in low:
        what = "يبحث في القرآن والتفسير"
    elif name in ("Read", "Glob", "Grep"):
        what = {"Read": "يقرأ", "Glob": "يبحث عن ملفات", "Grep": "يبحث داخل الملفات"}[name]
        arg = arg.rsplit("/", 1)[-1] if name == "Read" else arg
    elif name == "WebSearch":
        what = "يبحث في الويب"
    elif name == "WebFetch":
        what = "يفتح صفحة"
    elif name == "Bash":
        what = "يشغّل أمر قراءة"
    else:
        what = "يستخدم أداة " + name.split("__")[-1]
    return what + (": " + arg if arg else "")


def _event(agent_id, line, on_event, state):
    try:
        obj = json.loads(line)
    except (ValueError, TypeError):
        obj = None
    if agent_id == "claude" and isinstance(obj, dict):
        kind = obj.get("type")
        if kind == "system" and obj.get("subtype") == "init" and isinstance(obj.get("tools"), list):
            _save_mcp_tools(obj["tools"])          # أسماء أدوات MCP تُكتشف من أول تشغيل وتُخزَّن يومًا
        elif kind == "stream_event":
            ev = obj.get("event") or {}
            d = ev.get("delta") or {}
            if ev.get("type") == "content_block_delta" and d.get("type") == "text_delta":
                state["live"] = state.get("live", "") + str(d.get("text", ""))
                on_event("text", state["text"] + state["live"])
        elif kind == "assistant":
            state["live"] = ""
            content = obj.get("message", {}).get("content", [])
            for part in content:
                if part.get("type") == "text":
                    state["text"] += part.get("text", "")
                    on_event("text", state["text"])
                elif part.get("type") == "tool_use":
                    on_event("activity", _activity(str(part.get("name", "")), part.get("input")))
        elif kind == "result":
            state["text"] = str(obj.get("result", state["text"]))
            on_event("text", state["text"])
    elif isinstance(obj, dict) and agent_id == "opencode":
        if obj.get("type") == "error":
            e = obj.get("error") or {}
            state["error"] = str((e.get("data") or {}).get("message") or e.get("name") or "خطأ من الوكيل")[:200]
        part = obj.get("part", {})
        if part.get("type") == "text":
            state["text"] += str(part.get("text", ""))
            on_event("text", state["text"])
        elif part.get("type") == "tool":
            on_event("activity", "يستخدم أداة: " + str(part.get("tool", "")))
    elif isinstance(obj, dict) and agent_id == "agy":
        ev = obj.get("event")
        if obj.get("conversation_id"):
            state["conv"] = obj["conversation_id"]
        su = obj.get("step_update") if isinstance(obj.get("step_update"), dict) else None
        if su:
            state["conv"] = su.get("conversation_id") or state.get("conv", "")
            if su.get("step_type") == "tool" and su.get("state") == "ACTIVE":
                info = su.get("tool_info") or {}
                params = info.get("parameters") if isinstance(info.get("parameters"), dict) else {}
                on_event("activity", _activity(str(su.get("tool_name") or info.get("name") or ""),
                                               {"file_path": params.get("Path") or params.get("AbsolutePath"), "query": params.get("Query") or params.get("query"),
                                                "url": params.get("Url"), "command": params.get("CommandLine")}))
            elif su.get("step_type") == "agent_response" and su.get("text_delta"):
                state["live"] = state.get("live", "") + str(su["text_delta"])
                on_event("text", state["live"])
        elif ev == "result":
            res = obj.get("result") or {}
            state["conv"] = res.get("conversation_id") or state.get("conv", "")
            state["denied"] = res.get("denied_actions") or []
            resp = str(res.get("response") or "")
            if resp.strip():
                state["text"] = resp
                on_event("text", resp)
        elif ev in ("tool_call", "tool_use", "tool"):
            on_event("activity", _activity(str(obj.get("name") or obj.get("tool") or ""), obj.get("input") or obj.get("args")))
    elif isinstance(obj, dict) and agent_id == "codex":
        item = obj.get("item") if isinstance(obj.get("item"), dict) else {}
        kind, itype = obj.get("type"), item.get("type")
        if kind == "item.completed" and itype == "agent_message" and item.get("text"):
            state["live"] = str(item["text"])                  # تعليق الوكيل أثناء العمل؛ الإجابة النهائية من ملف -o
            on_event("text", state["live"])
        elif kind == "item.started" and itype == "command_execution":
            cmd = re.sub(r"^/bin/\w+ -lc ", "", str(item.get("command", ""))).strip("\"' ")
            on_event("activity", "يشغّل أمرًا: " + cmd[:100])
        elif kind == "item.started" and itype in ("web_search", "mcp_tool_call"):
            on_event("activity", "يبحث في الويب" if itype == "web_search" else "يستخدم أداة MCP")
        elif kind in ("turn.failed", "error"):
            state["raw"] += json.dumps(obj, ensure_ascii=False)[:400] + "\n"
    elif line.strip() and agent_id in ("agy", "codex"):
        state["raw"] += line + "\n"


def run(agent_id, prompt, *, depth="bal", workdir=None, add_dirs=(), on_event=None, should_stop=None, timeout=900):
    start = time.time()
    profile = _clean_profile(agent_id, _PROFILES.get(agent_id, _default(agent_id)))
    result = {"ok": False, "text": "", "partial": False, "error": "", "secs": 0.0, "model": profile["model"]}
    on_event = on_event or (lambda kind, data: None)
    should_stop = should_stop or (lambda: False)
    proc = None
    try:
        if not profile["enabled"]:
            result["error"] = "الوكيل معطّل من الإعدادات"
            return result
        if not can_run(agent_id):
            result["error"] = "الأداة غير موجودة في PATH"
            return result
        with tempfile.TemporaryDirectory(prefix="agent-") as td:
            answer = Path(td) / "answer.txt"
            stdout_path, stderr_path = Path(td) / "stdout", Path(td) / "stderr"
            cmd = _command(agent_id, str(prompt), profile, depth, list(add_dirs), answer, timeout)
            exe = shutil.which(cmd[0], path=os.pathsep.join(EXTRA_PATH))
            cmd[0] = exe or cmd[0]
            state = {"text": "", "raw": ""}
            pending = b""
            with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
                proc = _RUNNER(cmd, cwd=str(workdir or Path.home()), stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                               env=_env(), start_new_session=True)
                offset = 0
                while proc.poll() is None:
                    if should_stop():
                        os.killpg(proc.pid, signal.SIGTERM)
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            os.killpg(proc.pid, signal.SIGKILL)
                            proc.wait()
                        result["error"] = "stopped"
                        break
                    if time.time() - start >= timeout:
                        os.killpg(proc.pid, signal.SIGTERM)
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            os.killpg(proc.pid, signal.SIGKILL)
                            proc.wait()
                        result["error"] = "timeout"
                        break
                    out.flush()
                    with stdout_path.open("rb") as reader:
                        reader.seek(offset)
                        chunk = reader.read()
                        offset += len(chunk)
                    if chunk:
                        pending += chunk
                        lines = pending.split(b"\n")
                        pending = lines.pop()
                        for line in lines:
                            _event(agent_id, line.decode("utf-8", "replace"), on_event, state)
                    time.sleep(0.04)
                out.flush()
                with stdout_path.open("rb") as reader:
                    reader.seek(offset)
                    tail = reader.read().decode("utf-8", "replace")
                pending += tail.encode("utf-8")
                if pending:
                    _event(agent_id, pending.decode("utf-8", "replace"), on_event, state)
            if agent_id == "agy" and not state["text"] and state.get("conv") and not result["error"]:
                # رُفض إذن أداة في الوضع الصامت فانتهى الدور بلا نص؛ نستأنف المحادثة ونطلب الإجابة بلا أدوات
                resume = ["agy", "--mode", "plan", "--output-format", "stream-json", "--print-timeout", "5m", "--conversation", state["conv"],
                          "-p", "تعذّر استعمال بعض الأدوات لأنها تحتاج إذنًا. لا تستعمل أدوات أخرى؛ أجب الآن عن السؤال الأصلي كاملًا بما لديك."]
                resume[0] = shutil.which("agy", path=os.pathsep.join(EXTRA_PATH)) or "agy"
                try:
                    rp = subprocess.run(resume, cwd=str(workdir or Path.home()), stdin=subprocess.DEVNULL, capture_output=True, env=_env(),
                                        timeout=max(60, min(600, timeout - (time.time() - start))))
                    for ln in rp.stdout.decode("utf-8", "replace").splitlines():
                        _event(agent_id, ln, on_event, state)
                except (subprocess.TimeoutExpired, OSError):
                    pass
            if agent_id == "codex" and answer.is_file():
                state["text"] = answer.read_text(encoding="utf-8", errors="replace")
            elif agent_id in ("agy", "codex") and not state["text"]:
                state["text"] = state.get("live", "")       # انتهت المهلة قبل النتيجة: ما بُثّ حتى الآن (لا نُرجع JSON الخام أبدًا)
            elif agent_id == "opencode" and not state["text"]:
                if not state.get("error"):          # لا نُرجع JSON الخام نصًّا أبدًا
                    state["error"] = "لم يُرجع الوكيل نصًّا"
            elif agent_id == "hermes" or not state["text"]:
                raw = stdout_path.read_text(encoding="utf-8", errors="replace")
                state["text"] = raw.strip() if agent_id == "hermes" else (state["text"] or raw.strip())
            result["text"] = state["text"].strip()
            if state.get("error") and not result["text"]:
                result["error"] = state["error"]
            if len(result["text"]) < 300 and re.search(r"hit your .*limit|usage limit|quota|rate limit|resets \d", result["text"], re.I):
                result["error"] = "بلغ الوكيل حدّ استخدامه: " + result["text"]     # رسالة الحصة ليست إجابة
                result["text"] = ""
            result["partial"] = bool(result["text"] and (proc.returncode != 0 or result["error"] == "timeout"))
            result["ok"] = bool(result["text"] and (proc.returncode == 0 or result["partial"])) and result["error"] != "stopped"
            if proc.returncode and not result["error"]:
                result["error"] = "انتهى الوكيل برمز " + str(proc.returncode)
    except Exception as exc:
        result["error"] = str(exc) or exc.__class__.__name__
    finally:
        result["secs"] = round(time.time() - start, 2)
    return result


def _check_one(agent_id):
    start = time.time()
    result = run(agent_id, "اكتب: جاهز", timeout=60)
    secs = round(time.time() - start, 2)
    if result["ok"]:
        return {"state": "slow" if secs > 25 else "ready", "note": "استجاب الوكيل", "secs": secs}
    if result["error"] == "timeout":
        return {"state": "slow", "note": "بطيء جدًا: لم يجب خلال دقيقة", "secs": secs}
    note = result["error"] or "لم تصل إجابة"
    if any(x in note.lower() for x in ("auth", "login", "api key", "credential", "مفتاح", "مصادقة")):
        note = "تعذرت المصادقة: " + note
    return {"state": "off", "note": note, "secs": secs}


def cached_check(agent_id, max_age=1800):
    """آخر فحص جاهزية حديث للوكيل (بلا تشغيل جديد) أو None."""
    with _LOCK:
        v = _CHECKS.get(agent_id)
    return dict(v[1]) if v and time.time() - v[0] < max_age else None


def check(agent_ids, force=False):
    now = time.time()
    with _LOCK:
        if not force and all(i in _CHECKS and now - _CHECKS[i][0] < 600 for i in agent_ids):
            return {i: dict(_CHECKS[i][1]) for i in agent_ids}
    with ThreadPoolExecutor(max_workers=max(1, len(agent_ids))) as pool:
        values = list(pool.map(_check_one, agent_ids))
    with _LOCK:
        for agent_id, value in zip(agent_ids, values):
            _CHECKS[agent_id] = (time.time(), value)
    return dict(zip(agent_ids, values))
