"""غرفة الوكلاء: جلسات طرفية دائمة داخل tmux، تعرضها واجهة زاجل وتقبل الكتابة.
الجلسات تعيش في خادم tmux مستقل عن زاجل، فلا تموت بإغلاق النافذة أو تحديث التطبيق."""
import copy
import hashlib
import json
import os
import random
import re
import secrets
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

DATA = Path.home()
SOCK = "zajel"
MAX_BROADCAST = 9      # كل وكلاء الطرفية في جولة واحدة
PREFIX = "z-"
LOCK = threading.Lock()
EXTRA_PATH = [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".opencode/bin"), "/usr/bin", "/bin"]

BUILTIN = [
    {"id": "shell", "name": "طرفية", "cmd": ""},
    {"id": "shell2", "name": "طرفية ٢", "cmd": ""},
    {"id": "claude", "name": "Claude", "cmd": "claude"},
    {"id": "codex", "name": "Codex", "cmd": "codex"},
    {"id": "hermes", "name": "Hermes", "cmd": "hermes"},
    {"id": "agy", "name": "Antigravity", "cmd": "agy"},
    {"id": "opencode", "name": "OpenCode", "cmd": "opencode"},
    {"id": "pi", "name": "pi", "cmd": "pi"},
]
AGENTS = [dict(a) for a in BUILTIN]
BY_ID = {a["id"]: a for a in AGENTS}
BUILTIN_HEADLESS = {
    "claude": ["claude", "-p", "--allowedTools=Read,Grep,Glob,WebSearch,WebFetch", "--disallowedTools=Edit,Write,NotebookEdit"],
    "codex": ["codex", "exec", "--skip-git-repo-check", "-s", "read-only"],
    "hermes": ["hermes", "-z"],
    "agy": ["agy", "--mode", "plan", "--print-timeout", "10m", "-p"],
    "opencode": ["opencode", "run", "-m", "opencode/nemotron-3-ultra-free"],
}
HEADLESS = dict(BUILTIN_HEADLESS)
_CUSTOM = {"agents": [], "shortcuts": [], "updated": 0.0}
AGENT_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,19}$")


def _custom_file():
    return DATA / "terminal_custom.json"


def _load_custom():
    global _CUSTOM
    cf = _custom_file()
    try:
        if cf.exists():
            d = json.loads(cf.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                agents = [a for a in d.get("agents", []) if isinstance(a, dict) and a.get("id")]
                shortcuts = [s for s in d.get("shortcuts", []) if isinstance(s, dict) and s.get("id")]
                _CUSTOM = {"agents": agents, "shortcuts": shortcuts, "updated": float(d.get("updated", 0.0))}
                return
    except Exception:
        pass
    _CUSTOM = {"agents": [], "shortcuts": [], "updated": 0.0}


def _apply_custom():
    custom_rows = []
    for a in _CUSTOM.get("agents", []):
        custom_rows.append({"id": a["id"], "name": a.get("name", a["id"]), "cmd": a.get("cmd", ""), "custom": True})
    AGENTS[:] = [dict(b) for b in BUILTIN] + custom_rows
    BY_ID.clear()
    BY_ID.update({a["id"]: a for a in AGENTS})

    # إزالة الأوامر القديمة وإضافة أوامر ask المخصصة
    stale = [k for k in HEADLESS if k not in BUILTIN_HEADLESS]
    for k in stale:
        HEADLESS.pop(k, None)
    for a in _CUSTOM.get("agents", []):
        ask = a.get("ask")
        if ask:
            try:
                HEADLESS[a["id"]] = shlex.split(ask)
            except Exception:
                pass

    try:
        import agent_health
        for a in _CUSTOM.get("agents", []):
            agent_health.register(a["id"], a.get("cmd", ""))
    except Exception:
        pass


def _save_custom():
    try:
        cf = _custom_file()
        cf.parent.mkdir(parents=True, exist_ok=True)
        tmp = cf.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(_CUSTOM, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, cf)
    except Exception:
        pass


_load_custom()
_apply_custom()


def custom_get():
    return {"agents": list(_CUSTOM.get("agents", [])), "shortcuts": list(_CUSTOM.get("shortcuts", []))}


def _derive_id(name, cmd):
    cand = re.sub(r"[^a-zA-Z0-9_-]", "", name or "").lower()
    if cand and cand[0].isalpha() and len(cand) >= 2:
        return cand[:20]
    first_word = str(cmd or "").strip().split()[0] if str(cmd or "").strip() else ""
    cand = re.sub(r"[^a-zA-Z0-9_-]", "", first_word).lower()
    if cand and cand[0].isalpha() and len(cand) >= 2:
        return cand[:20]
    return ""


def agent_add(b):
    if not isinstance(b, dict):
        raise ValueError("بيانات غير صالحة.")
    cand = str(b.get("id") or "").strip()
    if not cand:
        cand = _derive_id(b.get("name", ""), b.get("cmd", ""))
    if not cand or not AGENT_ID_RE.match(cand):
        raise ValueError("معرّف الوكيل غير صالح (يجب أن يبدأ بحرف إنجليزي صغير ويتكون من 2 إلى 20 حرفًا وأرقامًا وشرطات).")
    builtin_ids = {a["id"] for a in BUILTIN}
    if cand in builtin_ids:
        raise ValueError("المعرّف محجوز للوكلاء المدمجين.")
    if any(a.get("id") == cand for a in _CUSTOM.get("agents", [])):
        raise ValueError("معرّف الوكيل موجود مسبقًا.")
    name = str(b.get("name") or "").strip()
    if not name:
        raise ValueError("اسم الوكيل مطلوب.")
    cmd = str(b.get("cmd") or "").strip()
    if not cmd:
        raise ValueError("أمر الوكيل مطلوب.")
    words = shlex.split(cmd)
    if not words or not _which(words[0]):
        raise ValueError(f"الأمر «{words[0] if words else ''}» غير موجود في النظام.")
    ask = str(b.get("ask") or "").strip()
    if ask:
        try:
            shlex.split(ask)
        except Exception:
            raise ValueError("أمر الاستدعاء المباشر (ask) غير صالح.")
    agent_row = {"id": cand, "name": name, "cmd": cmd}
    if ask:
        agent_row["ask"] = ask
    _CUSTOM.setdefault("agents", []).append(agent_row)
    _CUSTOM["updated"] = time.time()
    _save_custom()
    _apply_custom()
    return {"ok": True, "agent": agent_row}


def agent_remove(i):
    i = str(i or "").strip()
    builtin_ids = {a["id"] for a in BUILTIN}
    if i in builtin_ids:
        raise ValueError("لا يمكن حذف وكيل مدمج.")
    found = False
    for idx, a in enumerate(_CUSTOM.get("agents", [])):
        if a.get("id") == i:
            found = True
            _CUSTOM["agents"].pop(idx)
            break
    if not found:
        raise ValueError("الوكيل غير موجود.")
    try:
        stop(i)
    except Exception:
        pass
    _CUSTOM["updated"] = time.time()
    _save_custom()
    _apply_custom()
    return {"ok": True}


def shortcut_add(b):
    if not isinstance(b, dict):
        raise ValueError("بيانات غير صالحة.")
    kind = str(b.get("kind") or "").strip()
    if kind not in ("path", "agent"):
        raise ValueError("نوع الاختصار غير صالح (يجب أن يكون path أو agent).")
    name = str(b.get("name") or "").strip()
    if not name:
        raise ValueError("اسم الاختصار مطلوب.")
    raw_path = str(b.get("path") or "").strip()
    if not raw_path:
        raise ValueError("مسار المجلد مطلوب.")
    exp_path = os.path.expanduser(raw_path)
    if not os.path.isdir(exp_path):
        raise ValueError("المسار غير موجود أو ليس مجلدًا.")
    clean_path = str(Path(exp_path).resolve())
    sid = "s" + secrets.token_hex(3)
    existing_sids = {s.get("id") for s in _CUSTOM.get("shortcuts", [])}
    while sid in existing_sids:
        sid = "s" + secrets.token_hex(3)
    sc = {"id": sid, "kind": kind, "name": name, "path": clean_path}
    if kind == "agent":
        ag = str(b.get("agent") or "").strip()
        if not ag or ag not in BY_ID:
            raise ValueError("الوكيل غير معروف.")
        sc["agent"] = ag
    _CUSTOM.setdefault("shortcuts", []).append(sc)
    _CUSTOM["updated"] = time.time()
    _save_custom()
    return {"ok": True, "shortcut": sc}


def shortcut_remove(i):
    i = str(i or "").strip()
    found = False
    for idx, s in enumerate(_CUSTOM.get("shortcuts", [])):
        if s.get("id") == i:
            found = True
            _CUSTOM["shortcuts"].pop(idx)
            break
    if not found:
        raise ValueError("الاختصار غير موجود.")
    _CUSTOM["updated"] = time.time()
    _save_custom()
    return {"ok": True}


def cwd(i):
    if not i or i not in BY_ID:
        return {"ok": False}
    try:
        n = _name(i)
        r = _t("display-message", "-p", "-t", n, "#{pane_current_path}")
        if r.returncode == 0 and r.stdout.strip():
            return {"ok": True, "path": r.stdout.strip()}
    except Exception:
        pass
    return {"ok": False}


def open_path(i, path):
    if not i or i not in BY_ID:
        raise ValueError("وكيل غير معروف.")
    exp = os.path.expanduser(str(path or "").strip())
    if not exp or not os.path.isdir(exp):
        raise ValueError("المسار غير موجود أو ليس مجلدًا.")
    cmd = BY_ID[i].get("cmd", "")
    n = _name(i)
    is_running = (_t("has-session", "-t", n).returncode == 0)
    if not cmd:
        if not is_running:
            start(i, cwd=exp)
        else:
            send(i, f"cd {shlex.quote(exp)}", keys=["Enter"])
        return {"ok": True}
    else:
        if is_running:
            return {"ok": False, "error": "الوكيل يعمل الآن؛ أعد تشغيله ليفتح في هذا المسار", "running": True}
        start(i, cwd=exp)
        return {"ok": True}
SHELLS = {"zsh", "-zsh", "bash", "-bash", "sh", "-sh", "fish", "login"}
KEY_RE = re.compile(r"^(Enter|Tab|BTab|BSpace|Escape|Up|Down|Left|Right|Home|End|PgUp|PgDn|DC|Space|C-[a-z\\\]\[]|M-[a-z]|F([1-9]|1[0-2]))$")
WAIT_RE = re.compile(r"(\(y/n\)|\[y/n\]|\[Y/n\]|\(yes/no\)|press enter to|do you want to|would you like to|allow (this|once|always)|approve this|esc to cancel|❯\s*1\.|^\s*[❯›]\s*1\.\s|0:\s*Dismiss)", re.I | re.M)
IDLE_SECS, WORK_SECS = 4, 3
CFG = {"notify": True, "guard": True, "guarded": []}
GUARD = {}        # id ← {"bad": عدّاد قراءات سيئة متتالية، "tries": [أوقات محاولات الإنعاش]}
MON = {}          # id ← {"state","worked_since","last_note"}
_mon_thread = None


def init(data_dir):
    global DATA, _mon_thread
    DATA = Path(data_dir)
    try:
        CFG.update(json.loads((DATA / "terminal.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    _load_custom()
    _apply_custom()
    try:
        import agent_cli
        agent_cli.init(str(DATA))
    except Exception:
        pass
    try:
        import agent_health
        agent_health.init(str(DATA))
    except Exception:
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


_STABLE = {}      # معرّف ← (نص الشاشة بلا أرقام ورموز دوران، منذ متى لم يتغير)
_SPIN = re.compile(r"[0-9⠀-⣿◐◓◑◒✻✶✳✢·•*|/\\\-.]+")


def _still(i):
    """بعض الوكلاء (Antigravity وHermes) يحرّكون شاشتهم دائمًا: مؤشر يدور، ساعة، عدّاد.
    فحركة الشاشة وحدها ليست عملًا: إن لم يتغير نصها الحقيقي منذ ثوانٍ فالوكيل هادئ."""
    cur = _SPIN.sub("", _tail(i, 12))
    old = _STABLE.get(i)
    now = time.time()
    if not old or old[0] != cur:
        _STABLE[i] = (cur, now)
        return False
    return now - old[1] >= IDLE_SECS


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
    if idle < WORK_SECS and not _still(i):
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
        row = {"id": a["id"], "name": a["name"], "cmd": a["cmd"], "state": st, "label": lab, "idle": idle,
                     "installed": (not a["cmd"]) or bool(_which(a["cmd"])), "direct": bool(a["cmd"]) and can_direct(a["id"]),
                     "health": _health_brief(a["id"])}
        if a.get("custom"):
            row["custom"] = True
        rows.append(row)
    return {"available": ok, "agents": rows, "notify": CFG["notify"], "guard": CFG["guard"], "guarded": list(CFG["guarded"]),
            "hint": "" if ok else "tmux غير مثبت على هذا الجهاز؛ ثبّته أولًا (brew install tmux)."}


def _which(cmd):
    w = str(cmd or "").strip().split()[0] if str(cmd or "").strip() else ""
    if not w:
        return ""
    for p in EXTRA_PATH:
        f = Path(p) / w
        if f.exists() and os.access(f, os.X_OK):
            return str(f)
    return ""


_PERSIST_DONE = set()


def _persist_model_choice(i):
    """/model في Hermes يغيّر النموذج لهذه الجلسة فقط ويعود إلى الأساسي عند إعادة التشغيل؛ هذا المفتاح يجعل كل اختيار يُحفظ افتراضيًا."""
    if i != "hermes" or i in _PERSIST_DONE:
        return
    _PERSIST_DONE.add(i)
    exe = shutil.which("hermes") or str(Path.home() / ".local/bin/hermes")

    def run():
        try:
            subprocess.run([exe, "config", "set", "model.persist_switch_by_default", "true"], capture_output=True, timeout=30, env=_env())
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


def start(i, cwd=""):
    n = _name(i)
    _persist_model_choice(i)
    with LOCK:
        if _t("has-session", "-t", n).returncode == 0:
            return {"ok": True, "started": False}
        wd = cwd if cwd and Path(cwd).is_dir() else str(Path.home())
        r = _t("new-session", "-d", "-s", n, "-x", "140", "-y", "40", "-c", wd, "cd " + shlex.quote(wd) + " && exec env PWD=" + shlex.quote(wd) + " /bin/zsh -l")
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
    _guard_add(i)
    health_check(i)
    return {"ok": True, "started": True}


def stop(i, _keep_guard=False):
    if not _keep_guard:
        _guard_remove(i)         # إيقاف المستخدم المقصود لا يُنعَش
    _PREV.pop(i, None)
    _ARCH.pop(i, None)
    _t("kill-session", "-t", _name(i))
    MON.pop(i, None)
    return {"ok": True}


def restart(i, cwd=""):
    stop(i, _keep_guard=True)
    time.sleep(0.3)
    return start(i, cwd=cwd)


def send(i, text="", keys=None, paste=False):
    n = _name(i)
    # لا نفحص الجلسة بأمر مستقل (عملية إضافية في كل ضغطة)؛ فشل أول أمر إرسال يعني أنها غير شغّالة
    ks = [str(k) for k in (keys or [])[:100]]
    for k in ks:
        if not KEY_RE.match(k):
            raise ValueError("مفتاح غير مسموح: " + k[:20])
    dead = ValueError("الجلسة غير شغّالة؛ شغّلها أولًا.")
    if text:
        text = text[:20000]
        if paste:
            if _t("load-buffer", "-b", "zpaste", "-", inp=text).returncode != 0 or _t("paste-buffer", "-p", "-d", "-b", "zpaste", "-t", n).returncode != 0:
                raise dead
        elif _t("send-keys", "-t", n, "-l", "--", text).returncode != 0:
            raise dead
    if ks and _t("send-keys", "-t", n, *ks).returncode != 0:   # كل المفاتيح بأمر واحد بدل عملية لكل مفتاح
        raise dead
    return {"ok": True}


def resize(i, cols, rows):
    n = _name(i)
    cols, rows = max(20, min(300, int(cols))), max(5, min(100, int(rows)))
    _t("resize-window", "-t", n, "-x", str(cols), "-y", str(rows))
    return {"ok": True, "cols": cols, "rows": rows}


_PREV, _ARCH = {}, {}


def _scrolled_off(prev, cl):
    """كم سطرًا خرج من أعلى الشاشة السابقة؟ نبحث عن أصغر إزاحة s تجعل prev[s:] مطابقًا لرأس cl (تساهل: أسطر متغيرة قليلة كالمؤشر)."""
    n = len(prev)
    for s in range(1, n):
        m = min(n - s, len(cl))
        if m < 4:
            break
        same = sum(1 for a, b in zip(prev[s:s + m], cl[:m]) if a == b)
        solid = sum(1 for a, b in zip(prev[s:s + m], cl[:m]) if a == b and a.strip())
        if solid >= 3 and same >= m * 0.8:
            return s
    return 0


def _keep_history(i, cur):
    """واجهات الوكلاء تعيد الرسم وتمحو السجل (ESC[3J) أو تعمل بشاشة كاملة؛ فنحفظ نحن كل سطر يخرج من أعلى الشاشة بين لقطتين،
    وإذا امتُحيت الشاشة كلها حفظنا السابقة كاملة، ثم نضمّ المحفوظ أمام الشاشة الحالية دون تكرار."""
    cl = cur.split("\n")
    prev = _PREV.get(i)
    arch = _ARCH.get(i, [])
    if prev is not None and prev != cl:
        s = _scrolled_off(prev, cl)
        if s:
            arch = arch + prev[:s]
        elif len(cl) < len(prev) - 3 or sum(1 for a, b in zip(prev, cl) if a == b and a.strip()) < 2:
            arch = arch + [x for x in prev]       # تغيّرت الشاشة كلها: نحفظ ما كان عليها
    _PREV[i] = cl
    if not arch:
        return cur
    k = 0                                    # نزيل التكرار بين ذيل المحفوظ ورأس الشاشة الحالية
    for n in range(min(len(arch), len(cl), 400), 0, -1):
        if arch[-n:] == cl[:n]:
            k = n
            break
    arch = arch[:len(arch) - k] if k else arch
    while arch and not arch[-1].strip() and len(arch) > 1 and not arch[-2].strip():
        arch.pop()                               # لا نكدّس أسطرًا فارغة متتالية
    arch = arch[-5000:]
    _ARCH[i] = arch
    return "\n".join(arch + cl)


def screen(i, since="", hist=0):
    n = _name(i)
    args = ["capture-pane", "-p", "-e", "-J", "-t", n]
    if hist:
        args += ["-S", "-" + str(max(1, min(5000, int(hist))))]
    # لقطة الشاشة ومعلومات المؤشر بعملية tmux واحدة (سطر المعلومات هو آخر سطر في المخرجات)
    r = _t(*args, ";", "display-message", "-p", "-t", n, "#{cursor_x} #{cursor_y} #{pane_width} #{pane_height} #{alternate_on}")
    if r.returncode != 0:
        return {"alive": False, "text": "", "hash": ""}
    out = r.stdout
    cut = out.rstrip("\n").rfind("\n")
    info = out[cut + 1:].split()
    body = out[:cut + 1]
    h = hashlib.md5((body + " ".join(info)).encode("utf-8", "replace")).hexdigest()[:12]
    if since and since == h:
        return {"alive": True, "unchanged": True, "hash": h}
    cx, cy, w, hh, alt = (info + ["0"] * 5)[:5]
    text = body
    if hist and alt != "1":
        text = _keep_history(i, text)
        h = hashlib.md5((text + " ".join(info)).encode("utf-8", "replace")).hexdigest()[:12]
        if since and since == h:
            return {"alive": True, "unchanged": True, "hash": h}
    return {"alive": True, "hash": h, "text": text, "cursor": [int(cx), int(cy)], "cols": int(w), "rows": int(hh), "alt": alt == "1"}


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
        telegram_link.notify("term", text)
    except Exception:
        pass


# ---------- ترميم الوكلاء: فحص يومي وعند البطء أو العطل، وسلّم إصلاح ----------
HEALTH_RUNNING = set()
HEALTH_AR = {"ok": "سليم", "slow": "بطيء", "outdated": "يحتاج تحديثًا", "broken": "معطّل", "missing": "غير مثبّت"}


def _hm():
    try:
        import agent_health
        return agent_health
    except ImportError:
        return None


def _health_brief(i):
    h = _hm()
    c = (h.status().get(i) if h else None) or {}
    return {"status": c.get("status", ""), "label": HEALTH_AR.get(c.get("status"), ""), "version": c.get("version"), "latest": c.get("latest"),
            "at": c.get("at", 0), "checking": i in HEALTH_RUNNING} if c or i in HEALTH_RUNNING else {"status": "", "label": "", "checking": False}


def health_check(i, force=False, repair=False, confirm=False):
    """يفحص وكيلًا في الخلفية (مرة يوميًا ما لم يُجبَر)؛ عند العطل يجرّب سلّم الإصلاح ويُنبّه بتغيّر الحال فقط."""
    h = _hm()
    a = BY_ID.get(i)
    if not h or not a or not a["cmd"] or i in HEALTH_RUNNING:
        return {"ok": bool(h), "started": False}
    if not force and not h.due(i):
        return {"ok": True, "started": False}

    def work():
        HEALTH_RUNNING.add(i)
        try:
            before = (h.status().get(i) or {}).get("status", "")
            c = h.check(i, force=True)
            steps = []
            if repair and c["status"] in ("broken", "slow"):
                steps = h.repair(i, ["restart", "smoke"] if c["status"] == "broken" else ["smoke"], confirm=confirm, restart=lambda x: restart(x) if _t("has-session", "-t", _name(x)).returncode == 0 else True)
                c = h.check(i, force=True)
            if repair and c["status"] == "outdated" and confirm:
                steps += h.repair(i, ["update"], confirm=True)
                c = h.check(i, force=True)
            if CFG["notify"] and c["status"] != before and c["status"] in ("broken", "outdated", "missing"):
                _notify(f"فحص الوكيل {a['name']}: {HEALTH_AR.get(c['status'])}" + (f" ({c.get('error')})" if c.get("error") else "")
                        + (f" — الإصدار {c.get('version')} والأحدث {c.get('latest')}" if c["status"] == "outdated" else ""))
        except Exception:
            pass
        finally:
            HEALTH_RUNNING.discard(i)
    threading.Thread(target=work, daemon=True).start()
    return {"ok": True, "started": True}


def health_mark(i, kind, why=""):
    h = _hm()
    if not h or i not in BY_ID:
        return
    try:
        (h.mark_slow if kind == "slow" else h.mark_failure)(i, why)
        if len(h._recent_marks(i)) >= 2:
            health_check(i, force=True, repair=True)
    except Exception:
        pass


def health_all():
    h = _hm()
    return {"ok": True, "agents": {a["id"]: _health_brief(a["id"]) for a in AGENTS if a["cmd"]},
            "history": h.history()[-20:] if h else []}


# ---------- جهاز التحكم: يراقب الوكلاء دائمًا وينعش من يخرج عن الخدمة ----------
GUARD_MAX_TRIES, GUARD_WINDOW = 3, 600


def _save_cfg():
    try:
        (DATA / "terminal.json").write_text(json.dumps(CFG), encoding="utf-8")
    except OSError:
        pass


def _guard_add(i):
    if i not in CFG["guarded"]:
        CFG["guarded"].append(i)
        _save_cfg()


def _guard_remove(i):
    GUARD.pop(i, None)
    GUARD.pop("_seeded_" + i, None)
    if i in CFG["guarded"]:
        CFG["guarded"].remove(i)
        _save_cfg()


def set_guard(on):
    CFG["guard"] = bool(on)
    _save_cfg()
    return {"ok": True, "guard": CFG["guard"]}


def guard_status():
    return {"on": CFG["guard"], "guarded": list(CFG["guarded"]),
            "agents": {i: {"bad": g.get("bad", 0), "revived": len(g.get("tries", [])), "last": g.get("last", "")} for i, g in GUARD.items() if not i.startswith("_")}}


def _guard_tick(live):
    """يُنعش كل وكيل مفعَّل خرج إلى الطرفية أو ماتت جلسته: يعيد تشغيل أمره، وبعد محاولات فاشلة ينبّه المستخدم."""
    if not CFG["guard"]:
        return
    now = time.time()
    for i in list(CFG["guarded"]):
        a = BY_ID.get(i)
        if not a or not a["cmd"] or not _which(a["cmd"]):
            continue
        st, _, idle = state_of(i, live)
        g = GUARD.setdefault(i, {"bad": 0, "tries": []})
        if st not in ("shell", "stopped") or (st == "shell" and idle < 4):
            g["bad"] = 0
            continue
        g["bad"] += 1
        if g["bad"] < 2:                      # قراءتان متتاليتان (≈6 ث) حتى لا نُنعش عن وهم
            continue
        g["tries"] = [t for t in g["tries"] if now - t < GUARD_WINDOW]
        if len(g["tries"]) >= GUARD_MAX_TRIES:
            if g.get("last") != "gaveup":
                g["last"] = "gaveup"
                if CFG["notify"]:
                    _notify(f"الوكيل {a['name']} يخرج عن الخدمة مرارًا ولم ينجح إنعاشه؛ افحصه يدويًا.")
                health_mark(i, "failure", "خروج متكرر من الطرفية")
            continue
        g["tries"].append(now)
        g["bad"] = 0
        try:
            if st == "stopped":
                start(i)
            else:                              # الجلسة حيّة والوكيل خرج: أعد كتابة أمره في الطرفية نفسها
                _t("send-keys", "-t", _name(i), "-l", "--", a["cmd"])
                _t("send-keys", "-t", _name(i), "Enter")
            g["last"] = "revived"
            if CFG["notify"]:
                _notify(f"أعاد جهاز التحكم تشغيل الوكيل {a['name']} بعد خروجه.")
        except Exception as exc:
            g["last"] = "failed: " + str(exc)[:80]


def _monitor():
    while True:
        time.sleep(3)
        try:
            if not available():
                continue
            live = _live()
            for k in live:                       # كل جلسة حيّة تدخل الحراسة تلقائيًا
                if k in BY_ID and BY_ID[k]["cmd"] and k not in CFG["guarded"] and not GUARD.get("_seeded_" + k):
                    GUARD["_seeded_" + k] = True
                    _guard_add(k)
            _guard_tick(live)
            for a in AGENTS:
                i = a["id"]
                st, lab, idle = state_of(i, live)
                m = MON.setdefault(i, {"state": st, "worked": 0.0, "note": 0.0})
                prev = m["state"]
                now = time.time()
                if st == "working" and prev != "working":
                    m["worked"] = now
                if CFG["notify"] and st != prev and now - m["note"] > 900:
                    long_work = prev == "working" and m["worked"] and now - m["worked"] >= 90      # أقصر من ذلك تذبذب شاشة لا عمل حقيقي
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


AGENT_LOCKS = {}
ANSWER_TIMEOUT = 900
NOISE = re.compile(r"RTL Support Plugin|Commands: |Build · |ctrl\+p|tab agents|Brewed for|Churned for|Worked for|for shortcuts|MCP: |LSP: |\$\d+\.\d+|[─━▀▄█╹┃│]{4,}")


def _meaningful(text):
    """كم كلمة حقيقية في النص بعد حذف سطور واجهة الطرفية (شعارات، شريط حالة، خطوط)."""
    keep = [ln for ln in str(text or "").splitlines() if ln.strip() and not NOISE.search(ln) and not re.search(r"⟦[AZ]-", ln)]
    return len(re.findall(r"[\w\u0600-\u06FF]{2,}", "\n".join(keep)))


def _plain(i, hist=5000):
    r = _t("capture-pane", "-p", "-J", "-t", _name(i), "-S", "-" + str(hist), timeout=15)
    return r.stdout if r.returncode == 0 else ""


def _clean_body(body):
    out = []
    for ln in body.splitlines():
        ln = re.sub(r"^\s*[│┃]\s?", "", ln)
        ln = re.sub(r"\s*[│┃]\s*$", "", ln).rstrip()
        out.append(ln)
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    ind = min((len(x) - len(x.lstrip()) for x in out if x.strip()), default=0)
    out = [x[ind:] if x.strip() else "" for x in out]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def extract_answer(text, tok):
    """النص بين سطر ⟦A-tok⟧ وسطر ⟦Z-tok⟧ (الأخير المكتمل)، أو None. العلامتان تُقبلان فقط في سطر مستقل
    (مع رموز زخرفة خفيفة) حتى لا يلتقط الاستخراج نص التعليمات المرتدّ في الشاشة."""
    text = re.sub(r"[ \t]+$", "", text, flags=re.M)      # capture-pane -J يُبقي فراغات نهاية السطر فتُسقط المطابقة
    a = re.compile(r"^[^\w⟦]{0,6}⟦A-%s⟧[^\w]{0,6}$" % re.escape(tok), re.M)
    z = re.compile(r"^[^\w⟦]{0,6}⟦Z-%s⟧[^\w]{0,6}$" % re.escape(tok), re.M)
    for m in reversed(list(a.finditer(text))):
        e = z.search(text, m.end())
        if e:
            return _clean_body(text[m.end():e.start()])
    zs = list(z.finditer(text))
    if zs:                                           # علامة نهاية بلا بداية: نبدأ بعد آخر تعليمة تنسيق مرتدّة
        tail = text[:zs[-1].start()]
        k = max(tail.rfind("في أي مكان آخر."), tail.rfind("العلامتين في أي مكان آخر."))
        if k != -1:
            body = _clean_body(tail[k + len("في أي مكان آخر."):])
            body = "\n".join(ln for ln in body.splitlines() if "⟦A-" not in ln and re.search(r"\w", ln) or not ln.strip())
            if body.strip():
                return body.strip()
    return None


def _wrap_question(text, tok):
    return (f"{text.strip()}\n\n[تنسيق الإجابة فقط] ابدأ إجابتك بسطر مستقل فيه: القوس ⟦ ثم A- ثم {tok} ثم القوس ⟧ ملتصقة بلا مسافات، "
            f"واختمها بسطر مستقل بالطريقة نفسها لكن بحرف Z بدل A. اعمل بكامل أدواتك وخذ وقتك، ثم اكتب الإجابة كاملة بين السطرين. "
            f"لا تكتب العلامتين في أي مكان آخر.")


def _ensure_ready(i, timeout=45):
    """يشغّل الوكيل إن لزم، وينتظر حتى تهدأ شاشته ويظهر أنه جاهز لاستقبال الكتابة."""
    if _t("has-session", "-t", _name(i)).returncode != 0:
        start(i)
    t0 = time.time()
    time.sleep(0.5)
    while time.time() - t0 < timeout:
        st, _, idle = state_of(i)
        if st in ("idle", "waiting") and idle >= 1.5:
            return True
        if st == "shell" and time.time() - t0 > 8:
            raise ValueError("خرج الوكيل إلى الطرفية؛ أعد تشغيله.")
        time.sleep(0.5)
    return False


def _type_message(i, text):
    # سطر واحد يُكتب حرفًا حرفًا؛ لصق الحافظة كانت بعض الواجهات (Codex وHermes) تُسقط أول حرف منه
    send(i, text, paste="\n" in text)
    time.sleep(0.4)
    send(i, "", keys=["Enter"])


def _direct(rd, i, entry, prompt, add_dirs=()):
    """يسأل الوكيل عبر agent_cli.run ويحدّث النص الحي والنشاط في entry. يعيد نتيجة run."""
    def on_event(kind, data):
        if kind == "text":
            entry["live"] = str(data or "")[-3000:]
        elif kind == "activity":
            entry["activity"] = str(data or "")[:200]
    if (BY_ID.get(i) or {}).get("custom"):
        t = _headless(i, prompt, entry, rd, timeout=ANSWER_TIMEOUT)
        return {"ok": bool(t), "text": t or "", "error": "" if t else "لا إجابة من الأمر المباشر"}
    try:
        import agent_cli
        return agent_cli.run(i, prompt, depth=rd.get("depth", "bal"), add_dirs=[str(d) for d in add_dirs if d], on_event=on_event,
                             should_stop=lambda: bool(rd.get("stop")), timeout=ANSWER_TIMEOUT)
    except Exception as exc:
        return {"ok": False, "text": "", "error": str(exc)[:200]}


def _headless(i, question, entry=None, rd=None, timeout=900):
    """احتياط وضع الطرفيات: سؤال الوكيل بلا شاشة. يعيد الإجابة كاملة أو None."""
    if not (BY_ID.get(i) or {}).get("custom"):
        try:
            import agent_cli
            r = _direct(rd or {}, i, entry if entry is not None else {}, question)
            return r.get("text") if r.get("ok") and str(r.get("text") or "").strip() else None
        except ImportError:
            pass
    base = HEADLESS.get(i)
    exe = base and _which(base[0])
    if not exe:
        return None
    with tempfile.TemporaryFile() as fo, tempfile.TemporaryFile() as fe:
        try:
            pr = subprocess.Popen([exe] + base[1:] + [question], cwd=str(Path.home()), stdin=subprocess.DEVNULL, stdout=fo, stderr=fe,
                                  env=_env(), start_new_session=True)
        except OSError:
            return None
        t0 = time.time()
        while pr.poll() is None:
            if (rd and rd.get("stop")) or time.time() - t0 > timeout:
                pr.kill()
                pr.wait()
                return None
            if entry is not None:
                entry["live"] = f"يقرأ ويعمل بكامل أدواته في الخلفية… ({int(time.time() - t0)} ث)"
            time.sleep(1)
        fo.seek(0)
        out = re.sub(r"\x1b\[[0-9;]*m", "", fo.read().decode("utf-8", "replace")).strip()
    return out if out and (pr.returncode == 0 or _meaningful(out) >= 20) else None


def can_direct(i):
    if (BY_ID.get(i) or {}).get("custom"):
        base = HEADLESS.get(i)
        return bool(base and _which(base[0]))
    try:
        import agent_cli
        return bool(agent_cli.can_run(i))
    except Exception:
        base = HEADLESS.get(i)
        return bool(base and _which(base[0]))


def EXTRA_PATH_STR():
    return os.pathsep.join(EXTRA_PATH)


def _ask(rd, i, entry, question, tok, add_dirs=()):
    """يرسل السؤال إلى وكيل (مباشرة أو عبر شاشته) ويملأ entry بالإجابة."""
    if rd.get("mode", "direct") == "direct" and can_direct(i):
        try:
            entry.update(state="asking", sent_at=time.time(), via="direct", live="", activity="", partial=False, error="")
            r = _direct(rd, i, entry, question, add_dirs)
            txt = str(r.get("text") or "").strip()
            if rd.get("stop") or r.get("error") == "stopped":
                entry.update(state="stopped", answer=txt if r.get("ok") else entry.get("answer", ""), finished_at=time.time())
            elif r.get("ok") and txt:
                entry.update(state="done", answer=txt, partial=bool(r.get("partial")), model=r.get("model") or "", finished_at=time.time())
            else:
                why = r.get("error") or "لم يُرجع الوكيل إجابة"
                health_mark(i, "failure", str(why)[:120])
                entry.update(state="timeout" if "timeout" in str(why).lower() else "error",
                             error=f"{why} (تحقق من تسجيل دخوله أو مفتاحه، أو أن المهمة تجاوزت المهلة)."[:300], finished_at=time.time())
        except Exception as exc:
            entry.update(state="error", error=str(exc)[:200], finished_at=time.time())
        finally:
            entry["live"] = ""
        return
    lock = AGENT_LOCKS.setdefault(i, threading.Lock())
    with lock:
        try:
            entry["state"] = "starting"
            _ensure_ready(i)
            if rd["stop"]:
                entry["state"] = "stopped"
                return
            entry["state"] = "asking"
            entry["sent_at"] = time.time()
            _type_message(i, _wrap_question(question, tok))
            quiet_since = None
            worked = False
            while time.time() - entry["sent_at"] < ANSWER_TIMEOUT:
                if rd["stop"]:
                    entry["state"] = "stopped"
                    return
                time.sleep(0.8)
                txt = _plain(i, 1500)
                if "⟦A-%s⟧" % tok in txt:            # الإجابة قيد الكتابة: نعرض ما بعد علامة البداية حيًّا
                    entry["live"] = _clean_body(txt.rsplit("⟦A-%s⟧" % tok, 1)[1].replace("⟦Z-%s⟧" % tok, ""))[-3000:]
                ans = extract_answer(txt, tok)
                if ans is not None:
                    entry.update(state="done", answer=ans, finished_at=time.time())
                    return
                st, _, idle = state_of(i)
                if st == "working":
                    worked, quiet_since = True, None
                elif not worked and time.time() - entry["sent_at"] > 60:   # لم يبدأ العمل أصلًا: نجرّب الوضع غير التفاعلي مرة واحدة
                    hl = _headless(i, question, rd=rd)
                    if hl:
                        entry.update(state="done", answer=hl, via="headless", finished_at=time.time())
                    else:
                        entry.update(state="error", error="لم يستجب الوكيل (تحقق من تسجيل دخوله أو مفتاحه).", finished_at=time.time())
                    return
                elif worked:
                    quiet_since = quiet_since or time.time()
                    if time.time() - quiet_since > 25:        # انتهى العمل بلا علامات: نعرض آخر الشاشة خامًا
                        hl = _headless(i, question, rd=rd)
                        if hl:
                            entry.update(state="done", answer=hl, via="headless", finished_at=time.time())
                            return
                        tail = "\n".join(_clean_body(txt).splitlines()[-60:])
                        entry.update(state="done_raw", answer=tail, finished_at=time.time())
                        return
            hl = _headless(i, question, rd=rd)
            if hl:
                entry.update(state="done", answer=hl, via="headless", finished_at=time.time())
            else:
                entry.update(state="timeout", answer="", finished_at=time.time())
        except Exception as exc:
            entry.update(state="error", error=str(exc)[:200], finished_at=time.time())


DOC_EXT = (".docx", ".doc", ".rtf", ".odt", ".pages", ".html", ".htm", ".rtfd")


def extract_text(path):
    """يحوّل Word/PDF إلى ملف نصي بجانبه (يُقرأ بلا أدوات ولا أذونات). يعيد مسار النص أو None."""
    src = Path(path)
    if not src.is_file():
        return None
    out = src.with_suffix(src.suffix + ".txt")
    if out.is_file() and out.stat().st_mtime >= src.stat().st_mtime:
        return str(out)
    ext = src.suffix.lower()
    if ext in (".md", ".markdown", ".txt"):
        return None          # نص عادي أصلًا: يُقرأ مباشرة من مساره
    try:
        if ext in DOC_EXT:
            subprocess.run(["/usr/bin/textutil", "-convert", "txt", "-encoding", "UTF-8", "-output", str(out), str(src)],
                           capture_output=True, timeout=120)
        elif ext == ".pdf":
            try:
                import fitz
                with fitz.open(str(src)) as d:
                    out.write_text("\n\n".join(f"--- صفحة {n + 1} ---\n" + pg.get_text() for n, pg in enumerate(d)), encoding="utf-8")
            except ImportError:
                exe = shutil.which("pdftotext", path=EXTRA_PATH_STR())
                if exe:
                    subprocess.run([exe, "-layout", str(src), str(out)], capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.is_file() and _meaningful(re.sub(r"--- صفحة \d+ ---", "", out.read_text(encoding="utf-8", errors="ignore")[:200000])) < 40:
        out.unlink()                       # ملف مصوَّر (صفحات صور بلا نص): لا نوهم الوكلاء بنص فارغ
        return None
    return str(out) if out.is_file() and out.stat().st_size > 20 else None


PATH_RE = re.compile(r"(?:~|/Users|/Volumes|/private|/tmp)[^\n\"'«»<>|]*?\.(?:md|markdown|txt|docx?|rtf|odt|pages|pdf|html?)\b", re.I)


def paths_in(text):
    """مسارات ملفات موجودة فعلًا ذُكرت في نص السؤال."""
    found = []
    for m in PATH_RE.finditer(text or ""):
        p = os.path.expanduser(m.group(0).strip().strip("`'\""))
        if os.path.isfile(p) and p not in found:
            found.append(p)
    return found[:8]


BROADCAST_STATE = {}   # معرّف الوكيل ← حالة آخر إرسال إليه (تعرضها الواجهة)


def broadcast(ids, text):
    """إرسال الرسالة نفسها إلى جلسات عدة وكلاء (أو طرفيات) في آن واحد."""
    text = str(text or "").strip()
    if not text:
        raise ValueError("الرسالة فارغة.")
    if len(text) > 20000:
        text = text[:20000]
    if isinstance(ids, str):
        ids = [x.strip() for x in ids.split(",") if x.strip()]
    if not ids or not isinstance(ids, (list, tuple)):
        raise ValueError("اختر جلسة واحدة على الأقل.")
    clean = []
    for i in ids:
        if i not in BY_ID:
            raise ValueError(f"جلسة غير معروفة: {i}")
        a = BY_ID[i]
        if not (a.get("cmd") or i in ("shell", "shell2") or a.get("id", "").startswith("shell")):
            raise ValueError(f"جلسة غير معروفة: {i}")
        if i not in clean:
            clean.append(i)
    clean = clean[:MAX_BROADCAST]
    if not clean:
        raise ValueError("اختر جلسة واحدة على الأقل.")

    def run_one(target_id):
        name = BY_ID[target_id]["name"]
        try:
            BROADCAST_STATE[target_id] = {"state": "starting", "note": "يجهز…"}
            start(target_id)
            # لا يُكتب في وكيل يعرض سؤالًا (موافقة، استبيان، نعم/لا): كانت الرسالة تذهب جوابًا لذلك السؤال فتضيع
            st = _wait_idle(target_id)
            if st == "waiting":
                BROADCAST_STATE[target_id] = {"state": "skipped", "note": f"{name} يعرض سؤالًا ينتظر ردّك؛ ردّ عليه ثم أعد الإرسال"}
                return
            if st != "idle":
                BROADCAST_STATE[target_id] = {"state": "skipped", "note": f"{name} لم يجهز بعد ({st}); أعد الإرسال بعد قليل"}
                return
            _type_message(target_id, text)
            BROADCAST_STATE[target_id] = {"state": "sent", "note": f"وصلت إلى {name}"}
        except Exception as exc:
            BROADCAST_STATE[target_id] = {"state": "error", "note": f"{name}: {str(exc)[:120]}"}

    for i in clean:
        BROADCAST_STATE[i] = {"state": "queued", "note": ""}
        threading.Thread(target=run_one, args=(i,), daemon=True).start()
    return {"ok": True, "ids": clean}


def export_answer(i):
    """آخر سؤال وجوابه عند الوكيل ← مستند Word في التنزيلات، ويُفتح."""
    if i not in BY_ID:
        raise ValueError("وكيل غير معروف.")
    n = _name(i)
    if _t("has-session", "-t", n).returncode != 0:
        raise ValueError("الوكيل متوقف.")
    text = _t("capture-pane", "-p", "-J", "-S", "-5000", "-t", n, timeout=15).stdout
    import answer_export
    r = answer_export.export(i, BY_ID[i]["name"], text, cwd(i).get("path", ""))
    subprocess.Popen(["open", r["path"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r


def export_all(ids, extra=None):
    """أجوبة الوكلاء المعروضين الآن ← مستند Word واحد."""
    import answer_export
    entries = []
    for i in [x for x in dict.fromkeys(ids or []) if x in BY_ID and BY_ID[x]["cmd"]]:
        n = _name(i)
        if _t("has-session", "-t", n).returncode != 0:
            continue
        text = _t("capture-pane", "-p", "-J", "-S", "-5000", "-t", n, timeout=15).stdout
        entries.append((i, BY_ID[i]["name"], text, cwd(i).get("path", "")))
    extra = [(str(x.get("name") or "Perplexity"), str(x.get("question") or ""), str(x.get("answer") or "")) for x in (extra or []) if isinstance(x, dict)]
    if not entries and not extra:
        raise ValueError("لا وكيل يعمل في الشاشات المعروضة.")
    r = answer_export.export_many(entries, extra=extra)
    subprocess.Popen(["open", r["path"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r


def last_answer(i):
    """آخر سؤال وجوابه كاملين للقراءة (من سجلّ الوكيل؛ Claude وCodex لا يُبقيان أول الجواب على الشاشة)."""
    if i not in BY_ID:
        raise ValueError("وكيل غير معروف.")
    n = _name(i)
    text = _t("capture-pane", "-p", "-J", "-S", "-5000", "-t", n, timeout=15).stdout if _t("has-session", "-t", n).returncode == 0 else ""
    import answer_export
    q, a = answer_export.last_exchange(i, text, cwd(i).get("path", "") if text else "")
    return {"ok": True, "question": q, "answer": a, "name": BY_ID[i]["name"]}


def export_text(b):
    import answer_export
    r = answer_export.export_text(str(b.get("name") or "Perplexity"), str(b.get("question") or ""), str(b.get("answer") or ""))
    subprocess.Popen(["open", r["path"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r


def broadcast_status(ids):
    ids = [x for x in (ids or "").split(",") if x]
    return {"ok": True, "agents": {i: BROADCAST_STATE.get(i, {"state": "unknown", "note": ""}) for i in ids}}


def _wait_idle(i, timeout=45):
    """ينتظر حتى يصير الوكيل جاهزًا للكتابة. يعيد idle أو waiting أو shell.
    بعض الوكلاء (Antigravity وHermes) يحرّكون شاشتهم دائمًا (مؤشر يدور، ساعة، سطر حالة)، فلا تُعدّ «حركة الشاشة» انشغالًا:
    يُعدّ جاهزًا حين يثبت نص شاشته (بعد حذف الأرقام ورموز الدوران) نحو ثانيتين،
    وبعد المهلة يُكتب فيه على كل حال: الوكلاء يضعون الرسالة في طابورهم إن كانوا ما زالوا يجيبون."""
    norm = lambda t: re.sub(r"[0-9⠀-⣿◐◓◑◒|/\\\-·•.]+", "", t or "")
    t0, prev, same = time.time(), None, 0
    time.sleep(0.5)
    while time.time() - t0 < timeout:
        st, _, idle = state_of(i)
        if st == "shell" and time.time() - t0 > 8:
            return "shell"
        tail = _tail(i)
        if WAIT_RE.search(tail):
            return "waiting"
        cur = norm(tail)
        same = same + 1 if cur and cur == prev else 0
        prev = cur
        if st == "idle" or same >= 3:
            return "idle"
        time.sleep(0.7)
    return "idle" if prev else st


def chat_ask(i, text, timeout=None):
    """محادثة مباشرة مع جلسة وكيل واحد في الطرفية (تبقى الجلسة والسياق بين الرسائل). يعيد {"ok","text"|"error"}."""
    if i not in BY_ID or not BY_ID[i]["cmd"]:
        return {"ok": False, "error": "وكيل غير معروف."}
    tok = secrets.token_hex(3)
    entry = {"state": "starting", "answer": "", "live": ""}
    rd = {"mode": "terminal", "stop": False, "tok": tok, "letters": {}, "agents": {i: entry}}
    _ask(rd, i, entry, text, tok)
    if entry.get("answer"):
        return {"ok": True, "text": entry["answer"], "state": entry.get("state")}
    return {"ok": False, "error": entry.get("error") or "لم يُرجع الوكيل إجابة (" + str(entry.get("state")) + ")."}
