"""غرفة الوكلاء: جلسات طرفية دائمة داخل tmux، تعرضها واجهة زاجل وتقبل الكتابة.
الجلسات تعيش في خادم tmux مستقل عن زاجل، فلا تموت بإغلاق النافذة أو تحديث التطبيق."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

DATA = Path.home()
SOCK = "zajel"
PREFIX = "z-"
LOCK = threading.Lock()
EXTRA_PATH = [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".opencode/bin"), "/usr/bin", "/bin"]

AGENTS = [
    {"id": "shell", "name": "طرفية", "cmd": ""},
    {"id": "shell2", "name": "طرفية ٢", "cmd": ""},
    {"id": "claude", "name": "Claude", "cmd": "claude"},
    {"id": "codex", "name": "Codex", "cmd": "codex"},
    {"id": "hermes", "name": "Hermes", "cmd": "hermes"},
    {"id": "agy", "name": "Antigravity", "cmd": "agy"},
    {"id": "opencode", "name": "OpenCode", "cmd": "opencode"},
    {"id": "pi", "name": "pi", "cmd": "pi"},
]
BY_ID = {a["id"]: a for a in AGENTS}
SHELLS = {"zsh", "-zsh", "bash", "-bash", "sh", "-sh", "fish", "login"}
KEY_RE = re.compile(r"^(Enter|Tab|BTab|BSpace|Escape|Up|Down|Left|Right|Home|End|PgUp|PgDn|DC|Space|C-[a-z\\\]\[]|M-[a-z]|F([1-9]|1[0-2]))$")
WAIT_RE = re.compile(r"(\(y/n\)|\[y/n\]|\[Y/n\]|\(yes/no\)|press enter|do you want|would you like|allow\b|approve|esc to cancel|❯\s*1\.|\?\s*$|^\s*[❯›>]\s|^\s*│?\s*[❯›]\s)", re.I | re.M)
IDLE_SECS, WORK_SECS = 4, 3
CFG = {"notify": True}
MON = {}          # id ← {"state","worked_since","last_note"}
_mon_thread = None


def init(data_dir):
    global DATA, _mon_thread
    DATA = Path(data_dir)
    try:
        CFG.update(json.loads((DATA / "terminal.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    if not (_mon_thread and _mon_thread.is_alive()):
        _mon_thread = threading.Thread(target=_monitor, daemon=True)
        _mon_thread.start()


def _env():
    # بيئة نظيفة: لا يرث خادم tmux مفتاح الوكيل ولا أسرار زاجل
    home = str(Path.home())
    return {"HOME": home, "USER": os.environ.get("USER", ""), "LOGNAME": os.environ.get("USER", ""), "SHELL": "/bin/zsh",
            "PATH": os.pathsep.join(EXTRA_PATH), "LANG": "en_US.UTF-8", "TERM": "xterm-256color", "TMPDIR": os.environ.get("TMPDIR", "/tmp")}


def tmux_bin():
    for p in EXTRA_PATH:
        f = Path(p) / "tmux"
        if f.exists() and os.access(f, os.X_OK):
            return str(f)
    return shutil.which("tmux") or ""


def available():
    return bool(tmux_bin())


def _t(*args, inp=None, timeout=8):
    b = tmux_bin()
    if not b:
        raise ValueError("tmux غير مثبت على هذا الجهاز. ثبّته بالأمر: brew install tmux")
    r = subprocess.run([b, "-L", SOCK, *args], input=inp, capture_output=True, text=True, timeout=timeout, env=_env())
    return r


def _name(i):
    if i not in BY_ID:
        raise ValueError("وكيل غير معروف.")
    return PREFIX + i


def _live():
    """المعرّف ← (الأمر الحالي، آخر نشاط، ميتة؟) لكل جلسة حيّة."""
    r = _t("list-sessions", "-F", "#{session_name}\t#{pane_current_command}\t#{window_activity}\t#{pane_dead}")
    out = {}
    if r.returncode != 0:
        return out
    for ln in r.stdout.splitlines():
        p = ln.split("\t")
        if len(p) == 4 and p[0].startswith(PREFIX):
            out[p[0][len(PREFIX):]] = (p[1], int(p[2] or 0), p[3] == "1")
    return out


def _tail(i, n=6):
    r = _t("capture-pane", "-p", "-t", _name(i))
    lines = [x for x in r.stdout.splitlines() if x.strip()]
    return "\n".join(lines[-n:])


def state_of(i, live=None):
    """(الحالة، التسمية، ثوانٍ منذ آخر نشاط). الحالات: stopped, working, waiting, idle, shell."""
    live = _live() if live is None else live
    if i not in live:
        return "stopped", "متوقف", 0
    cmd, act, dead = live[i]
    if dead:
        return "stopped", "انتهى", 0
    idle = max(0, int(time.time()) - act)
    a = BY_ID[i]
    if a["cmd"] and cmd in SHELLS:
        return "shell", "خرج الوكيل (الطرفية جاهزة)", idle
    if not a["cmd"] and cmd in SHELLS:
        return ("working", "ينفّذ أمرًا", idle) if idle < WORK_SECS else ("idle", "جاهزة", idle)
    if idle < WORK_SECS:
        return "working", "يعمل", idle
    if WAIT_RE.search(_tail(i)):
        return "waiting", "ينتظر ردّك", idle
    return "idle", "هادئ", idle


def listing():
    ok = available()
    rows = []
    live = _live() if ok else {}
    for a in AGENTS:
        st, lab, idle = state_of(a["id"], live) if ok else ("stopped", "متوقف", 0)
        rows.append({"id": a["id"], "name": a["name"], "cmd": a["cmd"], "state": st, "label": lab, "idle": idle,
                     "installed": (not a["cmd"]) or bool(_which(a["cmd"]))})
    return {"available": ok, "agents": rows, "notify": CFG["notify"],
            "hint": "" if ok else "tmux غير مثبت على هذا الجهاز؛ ثبّته أولًا (brew install tmux)."}


def _which(cmd):
    for p in EXTRA_PATH:
        f = Path(p) / cmd
        if f.exists() and os.access(f, os.X_OK):
            return str(f)
    return ""


def start(i, cwd=""):
    n = _name(i)
    with LOCK:
        if _t("has-session", "-t", n).returncode == 0:
            return {"ok": True, "started": False}
        wd = cwd if cwd and Path(cwd).is_dir() else str(Path.home())
        r = _t("new-session", "-d", "-s", n, "-x", "140", "-y", "40", "-c", wd, "exec /bin/zsh -l")
        if r.returncode != 0:
            raise ValueError("تعذّر فتح الجلسة: " + r.stderr.strip()[:150])
        _t("set-option", "-t", n, "status", "off")
        _t("set-option", "-t", n, "history-limit", "5000")
        _t("set-option", "-t", n, "window-size", "manual")
        cmd = BY_ID[i]["cmd"]
        if cmd:
            time.sleep(0.6)       # ريثما يجهز الـshell
            _t("send-keys", "-t", n, "-l", "--", cmd)
            _t("send-keys", "-t", n, "Enter")
    MON.pop(i, None)
    return {"ok": True, "started": True}


def stop(i):
    _t("kill-session", "-t", _name(i))
    MON.pop(i, None)
    return {"ok": True}


def restart(i):
    stop(i)
    time.sleep(0.3)
    return start(i)


def send(i, text="", keys=None, paste=False):
    n = _name(i)
    if _t("has-session", "-t", n).returncode != 0:
        raise ValueError("الجلسة غير شغّالة؛ شغّلها أولًا.")
    if text:
        text = text[:20000]
        if paste:
            _t("load-buffer", "-b", "zpaste", "-", inp=text)
            _t("paste-buffer", "-p", "-d", "-b", "zpaste", "-t", n)
        else:
            _t("send-keys", "-t", n, "-l", "--", text)
    for k in (keys or [])[:50]:
        if not KEY_RE.match(str(k)):
            raise ValueError("مفتاح غير مسموح: " + str(k)[:20])
        _t("send-keys", "-t", n, str(k))
    return {"ok": True}


def resize(i, cols, rows):
    n = _name(i)
    cols, rows = max(20, min(300, int(cols))), max(5, min(100, int(rows)))
    _t("resize-window", "-t", n, "-x", str(cols), "-y", str(rows))
    return {"ok": True, "cols": cols, "rows": rows}


def screen(i, since="", hist=0):
    n = _name(i)
    args = ["capture-pane", "-p", "-e", "-J", "-t", n]
    if hist:
        args += ["-S", "-" + str(max(1, min(5000, int(hist))))]
    r = _t(*args)
    if r.returncode != 0:
        return {"alive": False, "text": "", "hash": ""}
    info = _t("display-message", "-p", "-t", n, "#{cursor_x} #{cursor_y} #{pane_width} #{pane_height} #{alternate_on}").stdout.split()
    h = hashlib.md5((r.stdout + " ".join(info)).encode("utf-8", "replace")).hexdigest()[:12]
    if since and since == h:
        return {"alive": True, "unchanged": True, "hash": h}
    cx, cy, w, hh, alt = (info + ["0"] * 5)[:5]
    return {"alive": True, "hash": h, "text": r.stdout, "cursor": [int(cx), int(cy)], "cols": int(w), "rows": int(hh), "alt": alt == "1"}


def set_notify(on):
    CFG["notify"] = bool(on)
    try:
        (DATA / "terminal.json").write_text(json.dumps(CFG), encoding="utf-8")
    except OSError:
        pass
    return {"ok": True, "notify": CFG["notify"]}


# ---------- المراقبة والإشعار ----------
def _notify(text):
    try:
        import telegram_link
        telegram_link.notify("done", text)
    except Exception:
        pass


def _monitor():
    while True:
        time.sleep(3)
        try:
            if not available():
                continue
            live = _live()
            for a in AGENTS:
                i = a["id"]
                st, lab, idle = state_of(i, live)
                m = MON.setdefault(i, {"state": st, "worked": 0.0, "note": 0.0})
                prev = m["state"]
                now = time.time()
                if st == "working" and prev != "working":
                    m["worked"] = now
                if CFG["notify"] and st != prev and now - m["note"] > 60:
                    long_work = prev == "working" and m["worked"] and now - m["worked"] >= 10
                    if st == "waiting" and prev in ("working", "idle"):
                        _notify(f"الوكيل {a['name']} ينتظر ردّك.")
                        m["note"] = now
                    elif st in ("idle", "shell") and long_work:
                        _notify(f"الوكيل {a['name']} أنهى ما كان يعمله.")
                        m["note"] = now
                    elif st == "stopped" and prev not in ("stopped",) and long_work:
                        _notify(f"جلسة {a['name']} توقفت.")
                        m["note"] = now
                m["state"] = st
        except Exception:
            pass
