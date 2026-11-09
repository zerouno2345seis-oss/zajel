"""فحص صحة وكلاء الـCLI وسلّم الإصلاح (smoke -> restart -> cleanup -> update)."""
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

AGENTS = ("claude", "codex", "agy", "hermes", "opencode", "pi")
_CUSTOM_CMDS = {}
EXTRA_PATH = [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]
NPM_PKG = {"claude": "@anthropic-ai/claude-code", "codex": "@openai/codex",
           "opencode": "opencode-ai", "pi": "@earendil-works/pi-coding-agent"}
# verified via `<tool> --help` / `<tool> update --help`
UPDATE_CMD = {"claude": ["claude", "update"], "codex": ["codex", "update"], "agy": ["agy", "update"],
              "hermes": ["hermes", "update", "--yes"], "opencode": ["opencode", "upgrade"],
              "pi": ["pi", "update", "--self"]}
DAY = 86400
SLOW_SECS = 20
MARK_WINDOW = 1800
HIST_MAX = 50

_lock = threading.RLock()
_path = None
_state = {"checks": {}, "marks": {}, "history": []}
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_VER = re.compile(r"\d+\.\d+(?:\.\d+)?(?:[-+.\w]*)?")


def init(data_dir):
    global _path, _state
    with _lock:
        try:
            _path = Path(data_dir) / "agent_health.json"
            _path.parent.mkdir(parents=True, exist_ok=True)
            st = {"checks": {}, "marks": {}, "history": []}
            if _path.exists():
                d = json.loads(_path.read_text("utf-8"))
                if isinstance(d, dict):
                    for k in st:
                        if isinstance(d.get(k), type(st[k])):
                            st[k] = d[k]
            _state = st
        except Exception:
            _state = {"checks": {}, "marks": {}, "history": []}


def _save():
    try:
        if _path:
            tmp = _path.with_suffix(".tmp")
            tmp.write_text(json.dumps(_state, ensure_ascii=False), "utf-8")
            os.replace(tmp, _path)
    except Exception:
        pass


def _hist(kind, agent_id, note=""):
    _state["history"].append({"at": time.time(), "kind": kind, "id": agent_id, "note": str(note)[:300]})
    del _state["history"][:-HIST_MAX]


def register(agent_id, cmd):
    w = str(cmd or "").strip().split()[0] if str(cmd or "").strip() else ""
    with _lock:
        if w:
            _CUSTOM_CMDS[agent_id] = w
        else:
            _CUSTOM_CMDS.pop(agent_id, None)


def unregister(agent_id):
    with _lock:
        _CUSTOM_CMDS.pop(agent_id, None)


def all_agents():
    with _lock:
        return list(AGENTS) + [k for k in _CUSTOM_CMDS if k not in AGENTS]


def due_list(force=False):
    return [a for a in all_agents() if due(a, force=force)]


def due_agents(force=False):
    return due_list(force=force)


def _which(name):
    target = _CUSTOM_CMDS.get(name, name)
    return shutil.which(target, path=os.pathsep.join(EXTRA_PATH + [os.environ.get("PATH", "")]))


def _exec(cmd, timeout):
    """ينفّذ الأمر بلا stdin وبمهلة؛ يعيد (rc, نص) أو None."""
    try:
        exe = _which(cmd[0])
        if not exe:
            return None
        p = subprocess.Popen([exe] + list(cmd[1:]), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, start_new_session=True)
        try:
            out, _ = p.communicate(timeout=min(timeout, 45))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, 9)
            except Exception:
                p.kill()
            p.communicate()
            return None
        return p.returncode, _ANSI.sub("", out.decode("utf-8", "replace"))
    except Exception:
        return None


def parse_version(text):
    for line in _ANSI.sub("", text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("⚠") or "warning" in line.lower() and not re.search(r"\bv?\d+\.\d+", line):
            continue
        m = re.search(r"\bv?(\d+\.\d+(?:\.\d+)?(?:[-+.][\w.]+)?)", line)
        if m:
            return m.group(1)
    return None


def version(agent_id):
    try:
        exe = _CUSTOM_CMDS.get(agent_id, agent_id)
        r = _exec([exe, "--version"], 10)
        return parse_version(r[1]) if r else None
    except Exception:
        return None


def latest(agent_id):
    try:
        pkg = NPM_PKG.get(agent_id)
        if not pkg or not _which("npm"):
            return None
        r = _exec(["npm", "view", pkg, "version"], 15)
        if not r or r[0] != 0:
            return None
        lines = [l.strip() for l in r[1].splitlines() if l.strip()]
        m = _VER.fullmatch(lines[-1]) if lines else None
        return lines[-1] if m else None
    except Exception:
        return None


def update_command(agent_id):
    c = UPDATE_CMD.get(agent_id)
    return list(c) if c else None


def smoke(agent_id):
    t0 = time.time()
    try:
        if agent_id in _CUSTOM_CMDS:
            try:
                import terminal
                hl = terminal._headless(agent_id, "أجب بكلمة: تم", timeout=30)
                if hl:
                    return {"ok": True, "secs": round(time.time() - t0, 2), "error": ""}
            except Exception:
                pass
            exe = _CUSTOM_CMDS.get(agent_id, agent_id)
            r = _exec([exe, "--version"], 10)
            ok = bool(r and r[0] == 0)
            return {"ok": ok, "secs": round(time.time() - t0, 2), "error": "" if ok else (r[1] if r else "فشل التشغيل")}
        import agent_cli
        r = agent_cli.run(agent_id, "أجب بكلمة: تم", depth="fast", timeout=30)
        ok = bool(r.get("ok")) and bool(str(r.get("text", "")).strip())
        err = "" if ok else str(r.get("error") or "لا إجابة")[:300]
        return {"ok": ok, "secs": round(time.time() - t0, 2), "error": err}
    except Exception as e:
        return {"ok": False, "secs": round(time.time() - t0, 2), "error": str(e)[:300]}


def _vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", (v or "").split("-")[0])[:4])


def is_outdated(cur, lat):
    try:
        return bool(cur and lat and _vkey(lat) > _vkey(cur))
    except Exception:
        return False


def classify(d):
    if d.get("version") is None and not d.get("ok"):
        return "missing" if not _which(d.get("id", "")) else "broken"
    if not d.get("ok"):
        return "broken"
    if d.get("slow"):
        return "slow"
    if d.get("outdated"):
        return "outdated"
    return "ok"


def due(agent_id, force=False):
    with _lock:
        if force:
            return True
        c = _state["checks"].get(agent_id)
        return not c or time.time() - c.get("at", 0) > DAY


def _recent_marks(agent_id):
    now = time.time()
    m = [x for x in _state["marks"].get(agent_id, []) if now - x["at"] <= MARK_WINDOW]
    _state["marks"][agent_id] = m
    return m


def _mark(kind, agent_id, why):
    with _lock:
        try:
            _state["marks"].setdefault(agent_id, []).append({"at": time.time(), "kind": kind, "why": str(why)[:200]})
            m = _recent_marks(agent_id)
            _hist(kind, agent_id, why)
            _save()
            return len(m) >= 2
        except Exception:
            return False


def mark_slow(agent_id, why=""):
    return _mark("slow", agent_id, why)


def mark_failure(agent_id, why=""):
    return _mark("failure", agent_id, why)


def check(agent_id, force=False):
    try:
        with _lock:
            c = _state["checks"].get(agent_id)
            if not force and c and not due(agent_id) and len(_recent_marks(agent_id)) < 2:
                return dict(c)
        exe = _which(agent_id)
        if not exe:
            d = {"id": agent_id, "version": None, "latest": None, "outdated": False, "ok": False, "secs": 0.0,
                 "error": "الأداة غير موجودة في PATH", "slow": False, "at": time.time(), "status": "missing"}
        else:
            ver = version(agent_id)
            lat = latest(agent_id)
            s = smoke(agent_id)
            d = {"id": agent_id, "version": ver, "latest": lat, "outdated": is_outdated(ver, lat),
                 "ok": s["ok"], "secs": s["secs"], "error": s["error"], "slow": s["secs"] > SLOW_SECS,
                 "at": time.time()}
            d["status"] = classify(d)
        with _lock:
            _state["checks"][agent_id] = d
            _state["marks"][agent_id] = []
            _hist("check", agent_id, d["status"])
            _save()
        return dict(d)
    except Exception as e:
        return {"id": agent_id, "version": None, "latest": None, "outdated": False, "ok": False, "secs": 0.0,
                "error": str(e)[:300], "slow": False, "at": time.time(), "status": "broken"}


def repair(agent_id, steps, confirm=False, restart=None, cleanup=None):
    """سلّم إصلاح: steps من 'smoke','restart','cleanup','update'. يتوقف عند أول smoke ناجح."""
    out = []
    for step in steps or []:
        try:
            if step == "smoke":
                s = smoke(agent_id)
                out.append({"step": step, "ok": s["ok"], "note": s["error"] or f"{s['secs']}s"})
                if s["ok"]:
                    break
            elif step in ("restart", "cleanup"):
                fn = restart if step == "restart" else cleanup
                if not callable(fn):
                    out.append({"step": step, "ok": False, "note": "لا دالة مرّرت"})
                else:
                    r = fn(agent_id)
                    out.append({"step": step, "ok": r is not False, "note": str(r if r not in (None, True, False) else "")[:200]})
            elif step == "update":
                cmd = update_command(agent_id)
                if not confirm:
                    out.append({"step": step, "ok": False, "note": "يتطلب تأكيدًا"})
                elif not cmd:
                    out.append({"step": step, "ok": False, "note": "أمر التحديث غير معروف"})
                else:
                    r = _exec(cmd, 45)
                    out.append({"step": step, "ok": bool(r and r[0] == 0),
                                "note": (r[1].strip()[-200:] if r else "فشل أو انتهت المهلة")})
            else:
                out.append({"step": step, "ok": False, "note": "خطوة غير معروفة"})
        except Exception as e:
            out.append({"step": step, "ok": False, "note": str(e)[:200]})
    with _lock:
        _hist("repair", agent_id, ",".join(f"{o['step']}={'1' if o['ok'] else '0'}" for o in out))
        _save()
    return out


def status():
    with _lock:
        return {k: dict(v) for k, v in _state["checks"].items()}


def history():
    with _lock:
        return list(_state["history"])
