"""غرفة الوكلاء: جلسات طرفية دائمة داخل tmux، تعرضها واجهة زاجل وتقبل الكتابة.
الجلسات تعيش في خادم tmux مستقل عن زاجل، فلا تموت بإغلاق النافذة أو تحديث التطبيق."""
import hashlib
import json
import os
import re
import secrets
import shlex
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
WAIT_RE = re.compile(r"(\(y/n\)|\[y/n\]|\[Y/n\]|\(yes/no\)|press enter to|do you want to|would you like to|allow (this|once|always)|approve this|esc to cancel|❯\s*1\.|^\s*[❯›]\s*1\.\s)", re.I | re.M)
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
    _load_council()
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


# ================= مجلس الوكلاء: سؤال واحد إلى عدّة وكلاء، ثم وكيل رئيسي يقارن =================
COUNCIL = {}
COUNCIL_ORDER = []
COUNCIL_MAX = 12
AGENT_LOCKS = {}
ANSWER_TIMEOUT = 900          # أقصى انتظار لإجابة وكيل (ثوانٍ)
MAX_Q = 8000
MAX_ANS_IN_EVAL = 14000


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
    # العلامة لا تُكتب هنا حرفيًا: لو ظهرت في التعليمة المعروضة على الشاشة لظنّ المجلس أن الإجابة انتهت قبل أن تبدأ
    return (f"{text.strip()}\n\n[تنسيق الإجابة فقط] ابدأ إجابتك بسطر مستقل فيه: القوس ⟦ ثم A- ثم {tok} ثم القوس ⟧ ملتصقة بلا مسافات، "
            f"واختمها بسطر مستقل بالطريقة نفسها لكن بحرف Z بدل A. اعمل بكامل أدواتك وخذ وقتك، ثم اكتب الإجابة كاملة بين السطرين. "
            f"لا تكتب العلامتين في أي مكان آخر.")


def _save_council():
    try:
        rows = [COUNCIL[k] for k in COUNCIL_ORDER[-COUNCIL_MAX:] if k in COUNCIL]
        (DATA / "terminal_council.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _load_council():
    try:
        for r in json.loads((DATA / "terminal_council.json").read_text(encoding="utf-8")):
            if r.get("phase") in ("asking", "evaluating"):
                r["phase"] = "stopped"
            COUNCIL[r["id"]] = r
            COUNCIL_ORDER.append(r["id"])
    except (OSError, ValueError, KeyError):
        pass


def _ensure_ready(i, timeout=45):
    """يشغّل الوكيل إن لزم، وينتظر حتى تهدأ شاشته ويظهر أنه جاهز لاستقبال الكتابة."""
    if _t("has-session", "-t", _name(i)).returncode != 0:
        start(i)
    t0 = time.time()
    time.sleep(2)
    while time.time() - t0 < timeout:
        st, _, idle = state_of(i)
        if st in ("idle", "waiting") and idle >= 3:
            return True
        if st == "shell" and time.time() - t0 > 8:
            raise ValueError("خرج الوكيل إلى الطرفية؛ أعد تشغيله.")
        time.sleep(1.5)
    return False


def _type_message(i, text):
    send(i, text, paste=True)
    time.sleep(0.6)
    send(i, "", keys=["Enter"])


HEADLESS = {"claude": ["claude", "-p", "--allowedTools=Read,Grep,Glob,WebSearch,WebFetch"], "codex": ["codex", "exec", "--skip-git-repo-check"], "hermes": ["hermes", "-z"],
            "agy": ["agy", "--print-timeout", "10m", "-p"], "opencode": ["opencode", "run", "-m", "opencode/glm-5.3-flash-free"]}


def _headless(i, question, entry=None, rd=None, timeout=900):
    """يسأل الوكيل بوضعه غير التفاعلي (بلا شاشة) ويعيد إجابته كاملة، أو None. يكتب في entry زمن العمل حيًّا."""
    base = HEADLESS.get(i)
    exe = base and shutil.which(base[0], path=EXTRA_PATH_STR())
    if not exe:
        return None
    try:
        pr = subprocess.Popen([exe] + base[1:] + [question], cwd=str(Path.home()), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, env={**os.environ, "PATH": EXTRA_PATH_STR()})
    except OSError:
        return None
    t0 = time.time()
    while pr.poll() is None:
        if (rd and rd.get("stop")) or time.time() - t0 > timeout:
            pr.kill()
            return None
        if entry is not None:
            entry["live"] = f"يقرأ ويعمل بكامل أدواته في الخلفية… ({int(time.time() - t0)} ث)"
        time.sleep(2)
    out, _err = pr.communicate()
    out = re.sub(r"\x1b\[[0-9;]*m", "", out or "").strip()
    return out if pr.returncode == 0 and out and "Error:" not in out[:200] else None


def can_direct(i):
    base = HEADLESS.get(i)
    return bool(base and shutil.which(base[0], path=EXTRA_PATH_STR()))


def EXTRA_PATH_STR():
    return os.pathsep.join([str(Path.home() / ".local" / "bin"), "/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".opencode" / "bin"), os.environ.get("PATH", "")])


def _ask(rd, i, entry, question, tok):
    """يرسل السؤال إلى وكيل ويلتقط إجابته من شاشته. يملأ entry ويعيد."""
    if rd.get("mode", "direct") == "direct" and can_direct(i):
        try:
            entry.update(state="asking", sent_at=time.time(), via="direct")
            ans = _headless(i, question, entry, rd)
            if rd.get("stop"):
                entry.update(state="stopped", finished_at=time.time())
            elif ans:
                entry.update(state="done", answer=ans, finished_at=time.time())
            else:
                entry.update(state="error", error="لم يُرجع الوكيل إجابة (تحقق من تسجيل دخوله أو مفتاحه، أو أن المهمة تجاوزت ١٥ دقيقة).", finished_at=time.time())
        except Exception as exc:
            entry.update(state="error", error=str(exc)[:200], finished_at=time.time())
        finally:
            _save_council()
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
                time.sleep(2)
                txt = _plain(i)
                if "⟦A-%s⟧" % tok in txt:            # الإجابة قيد الكتابة: نعرض ما بعد علامة البداية حيًّا
                    entry["live"] = _clean_body(txt.rsplit("⟦A-%s⟧" % tok, 1)[1].replace("⟦Z-%s⟧" % tok, ""))[-3000:]
                ans = extract_answer(txt, tok)
                if ans is not None:
                    entry.update(state="done", answer=ans, finished_at=time.time())
                    return
                st, _, idle = state_of(i)
                if st == "working":
                    worked, quiet_since = True, None
                elif not worked and time.time() - entry["sent_at"] > 90:   # لم يبدأ العمل أصلًا: نجرّب الوضع غير التفاعلي مرة واحدة
                    hl = _headless(i, question)
                    if hl:
                        entry.update(state="done", answer=hl, via="headless", finished_at=time.time())
                    else:
                        entry.update(state="error", error="لم يستجب الوكيل (تحقق من تسجيل دخوله أو مفتاحه).", finished_at=time.time())
                    return
                elif worked:
                    quiet_since = quiet_since or time.time()
                    if time.time() - quiet_since > 40:        # انتهى العمل بلا علامات: نعرض آخر الشاشة خامًا
                        hl = _headless(i, question)
                        if hl:
                            entry.update(state="done", answer=hl, via="headless", finished_at=time.time())
                            return
                        tail = "\n".join(_clean_body(txt).splitlines()[-60:])
                        entry.update(state="done_raw", answer=tail, finished_at=time.time())
                        return
            hl = _headless(i, question)
            if hl:
                entry.update(state="done", answer=hl, via="headless", finished_at=time.time())
            else:
                entry.update(state="timeout", answer="", finished_at=time.time())
        except Exception as exc:
            entry.update(state="error", error=str(exc)[:200], finished_at=time.time())
        finally:
            _save_council()


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


def _att(path, name="", to="*"):
    text = extract_text(path)
    scanned = not text and Path(path).suffix.lower() == ".pdf"
    return {"path": path, "name": name or Path(path).name, "to": to, "text": text, "scanned": scanned}


PATH_RE = re.compile(r"(?:~|/Users|/Volumes|/private|/tmp)[^\n\"'«»<>|]*?\.(?:md|markdown|txt|docx?|rtf|odt|pages|pdf|html?)\b", re.I)


def paths_in(text):
    """مسارات ملفات موجودة فعلًا ذُكرت في نص السؤال (تُعامَل كمرفقات للجميع)."""
    found = []
    for m in PATH_RE.finditer(text or ""):
        p = os.path.expanduser(m.group(0).strip().strip("`'\""))
        if os.path.isfile(p) and p not in found:
            found.append(p)
    return found[:8]


def _prev_note(rd):
    pr = COUNCIL.get(rd.get("parent") or "")
    return f"\n\n(هذه متابعة لسؤال سابق في المجلس: «{pr['question'][:300]}»)" if pr else ""


def _files_note(rd, who):
    """سطور المرفقات الموجَّهة إلى وكيل معيّن (who: معرّف الوكيل أو "main")."""
    mine = [a for a in rd.get("attachments", []) if a.get("to") in ("*", who)]
    if not mine:
        return ""
    lines = []
    for a in mine:
        if a.get("scanned"):
            lines.append(f"- {a.get('name') or Path(a['path']).name}: ملف PDF مصوَّر (صفحاته صور بلا نص) في {a['path']} — اقرأه بأداة تعرّف ضوئي إن كانت لديك، وإلا فصرّح بأنك لم تستطع قراءته ولا تخمّن محتواه")
        elif a.get("text"):
            lines.append(f"- {a.get('name') or Path(a['path']).name}: نصّه الكامل جاهز للقراءة في {a['text']} (الأصل: {a['path']})")
        else:
            lines.append(f"- {a['path']}")
    return ("\n\nملفات مرفقة — اقرأها كاملة قبل الإجابة (النص المستخرج ملف نصي عادي يُقرأ مباشرة):\n" + "\n".join(lines))


def _eval_prompt(rd):
    parts = [f"أنت الوكيل الرئيسي (الحَكَم) في «مجلس الوكلاء» داخل برنامج زاجل. سُئل عدّة وكلاء السؤال التالي:\n\n«{rd['question']}»{_prev_note(rd)}{_files_note(rd, 'main')}\n\nهذه إجاباتهم:"]
    for i in rd["delegates"]:
        e = rd["agents"][i]
        tag = f"{BY_ID[i]['name']} (المعرّف: {i}" + (f"، أعاد زاجل تشغيله {e['retries']} مرة" if e.get("retries") else "") + ")"
        if _real(e):
            parts.append(f"\n===== إجابة {tag} =====\n{e['answer'][:MAX_ANS_IN_EVAL]}")
        elif e.get("answer"):
            parts.append(f"\n===== {tag}: لم تُلتقط إجابته نظيفة، هذا آخر ما على شاشته (قد يكون ضجيجًا) =====\n{e['answer'][:1500]}")
        else:
            parts.append(f"\n===== {tag}: لم تصل إجابة ({e.get('state')}) =====")
    parts.append("\n\nأنت الحكم. احكم على المضمون فقط، وابنِ حكمك على الإجابات الحقيقية، واقرأ المرفقات بنفسك إن احتجت. "
                 "اكتب حكمك بصيغة Markdown بهذه العناوين بالترتيب: ## الاتفاق ، ## الاختلاف (ومن الأصح ولماذا) ، ## الأخطاء والمبالغات ، "
                 "## الترتيب (من الأفضل مع سبب مختصر) ، ## الحكم النهائي (إجابة موحّدة مرجَّحة كاملة). لا تنقل إجاباتهم كاملة (ستُرفق تلقائيًا). "
                 "إن رأيت أن وكيلًا لم يعمل أو جاءت إجابته ناقصة أو غير منطقية، فاكتب في آخر حكمك سطرًا مستقلًا بالصيغة: "
                 "RETRY: معرّف1, معرّف2 — فيعيد زاجل تشغيله ويسأله من جديد ثم يعرض عليك إجابته لتحدّث حكمك. لا تنفّذ أوامر تعدّل الملفات.")
    return "".join(parts)


RETRY_RE = re.compile(r"^\s*\**RETRY\**\s*[:：]\s*(.+)$", re.M | re.I)


def _run_eval(rd):
    """يسأل الحَكَم؛ يعيد قائمة الوكلاء الذين طلب إعادتهم."""
    main = rd["main"]
    if not main:
        return []
    if not any(_real(e) for e in rd["agents"].values()):
        rd["eval"].update(state="error", error="لم تصل أي إجابة حقيقية؛ لم يُطلب الحكم.", answer="")
        return []
    rd["phase"] = "evaluating"
    ev = rd["eval"]
    ev.update(tok=secrets.token_hex(3), state="queued", answer="", live="", version=ev.get("version", 0) + 1)
    _save_council()
    _ask(rd, main, ev, _eval_prompt(rd), ev["tok"])
    want = []
    m = RETRY_RE.search(ev.get("answer") or "")
    if m:
        want = [x for x in re.split(r"[,،\s]+", m.group(1)) if x in rd["agents"]]
        ev["answer"] = RETRY_RE.sub("", ev["answer"]).strip()
    _save_council()
    return want


FINAL = ("done", "done_raw", "error", "timeout", "stopped")
NOISE = re.compile(r"RTL Support Plugin|Commands: |Build · |ctrl\+p|tab agents|Brewed for|Churned for|Worked for|for shortcuts|MCP: |LSP: |\$\d+\.\d+|[─━▀▄█╹┃│]{4,}")


def _meaningful(text):
    """كم كلمة حقيقية في النص بعد حذف سطور واجهة الطرفية (شعارات، شريط حالة، خطوط)."""
    keep = [ln for ln in str(text or "").splitlines() if ln.strip() and not NOISE.search(ln) and not re.search(r"⟦[AZ]-", ln)]
    return len(re.findall(r"[\w\u0600-\u06FF]{2,}", "\n".join(keep)))


def _real(e):
    """إجابة يُبنى عليها حكم: التُقطت بعلاماتها (أو بالوضع الهادئ) وفيها كلام فعلي."""
    return e.get("state") == "done" and _meaningful(e.get("answer")) >= 2


MAX_RETRY = 1


def _weak(e):
    return e.get("state") in ("done_raw", "error", "timeout") or (e.get("state") == "done" and not _real(e))


def _retry(rd, i, why):
    """يعيد تشغيل جلسة الوكيل نظيفة ويسأله من جديد (بالعلامات ثم بالوضع الهادئ احتياطًا)."""
    e = rd["agents"][i]
    e.update(state="restarting", answer="", live="", error="", retries=e.get("retries", 0) + 1, note=why)
    _save_council()
    if not (rd.get("mode", "direct") == "direct" and can_direct(i)):
        try:
            restart(i)
        except Exception:
            pass
    _ask(rd, i, e, rd["question"] + _files_note(rd, i), rd["tok"])


def _run_round(rd):
    threads = {}
    for i in rd["delegates"]:
        t = threading.Thread(target=_ask, args=(rd, i, rd["agents"][i], rd["question"] + _files_note(rd, i), rd["tok"]), daemon=True)
        t.start()
        threads[i] = t

    def supervise():
        """زاجل يراقب: من انتهى بإجابة ضعيفة أو تعطّل يُعاد تشغيله مرة واحدة."""
        for i, t in list(threads.items()):
            e = rd["agents"][i]
            if not t.is_alive() and _weak(e) and e.get("retries", 0) < MAX_RETRY and not rd["stop"]:
                threads[i] = threading.Thread(target=_retry, args=(rd, i, "أعاد زاجل تشغيله: لم تصل إجابة صالحة"), daemon=True)
                threads[i].start()

    def wait(until_cut):
        t0, limit = time.time(), rd.get("limit") or 0
        while any(t.is_alive() for t in threads.values()) and not rd["stop"]:
            time.sleep(1)
            supervise()
            if until_cut and limit and rd["main"] and time.time() - t0 > limit and any(_real(e) for e in rd["agents"].values()):
                rd["cut"] = True       # انتهت المهلة: يحكم الحَكَم بما وصل ويكمل البطيء
                return
            if not until_cut and time.time() - t0 > ANSWER_TIMEOUT:
                return
        supervise()
        if any(t.is_alive() for t in threads.values()) and not rd["stop"]:
            wait(until_cut)

    wait(True)
    if rd["stop"]:
        rd["phase"] = "stopped"; _save_council(); return
    if not (rd["evaluate"] and rd["main"]):
        rd["phase"] = "refining" if rd.get("cut") else "done"
        wait(False)
        rd["phase"] = "stopped" if rd["stop"] else "done"; _save_council(); return

    seen = {i for i, e in rd["agents"].items() if _real(e)}
    want = _run_eval(rd)
    # الحَكَم طلب إعادة وكلاء، أو هناك بطيئون لم يصلوا بعد: ننتظرهم ثم نحدّث الحكم مرة واحدة
    for i in want:
        if rd["agents"][i].get("retries", 0) < MAX_RETRY + 1 and not (threads[i].is_alive()):
            threads[i] = threading.Thread(target=_retry, args=(rd, i, "أعاده الحَكَم: إجابته ناقصة أو غير منطقية"), daemon=True)
            threads[i].start()
    if any(t.is_alive() for t in threads.values()) and not rd["stop"]:
        rd["phase"] = "refining"; _save_council()
        wait(False)
        fresh = {i for i, e in rd["agents"].items() if _real(e)} - seen
        if (fresh or want) and not rd["stop"]:
            rd["eval"]["note"] = "حكم محدَّث بعد وصول إجابات جديدة"
            _run_eval(rd)
    rd["phase"] = "stopped" if rd["stop"] else "done"
    _save_council()


def warm(ids):
    """يجهّز الوكلاء (يشغّل المتوقف وينتظر جاهزيته) في الخلفية قبل أن يُطرح السؤال، فيبدأ الجميع معًا."""
    ids = [i for i in dict.fromkeys(ids or []) if i in BY_ID and BY_ID[i]["cmd"]][:6]
    if not ids or not available():
        return {"ok": True, "warming": []}

    def one(i):
        lock = AGENT_LOCKS.setdefault(i, threading.Lock())
        if lock.acquire(blocking=False):
            try:
                _ensure_ready(i)
            except Exception:
                pass
            finally:
                lock.release()
    for i in ids:
        threading.Thread(target=one, args=(i,), daemon=True).start()
    return {"ok": True, "warming": ids}


def council_start(ids, text, main="", evaluate=True, attachments=None, parent="", limit=300, mode="direct"):
    text = str(text or "").strip()
    if not text or len(text) > MAX_Q:
        raise ValueError(f"اكتب سؤالًا (حتى {MAX_Q} حرف).")
    ids = [i for i in dict.fromkeys(ids or []) if i in BY_ID and BY_ID[i]["cmd"]]
    if not ids:
        raise ValueError("اختر وكيلًا مفوَّضًا واحدًا على الأقل.")
    if main and (main not in BY_ID or not BY_ID[main]["cmd"]):
        raise ValueError("الوكيل الرئيسي غير معروف.")
    if not available():
        raise ValueError("tmux غير مثبت على هذا الجهاز.")
    for k in COUNCIL_ORDER:
        r = COUNCIL.get(k)
        if r and r["phase"] in ("asking", "evaluating") and not r["stop"]:
            raise ValueError("يعمل مجلس الآن؛ أوقفه أو انتظر نهايته.")
    rid = secrets.token_hex(4)
    atts = []
    for a in (attachments or [])[:12]:
        to = str(a.get("to") or "*")
        if str(a.get("path", "")).strip() and (to in ("*", "main") or to in ids):
            atts.append(_att(str(a["path"]), str(a.get("name", ""))[:120], to))
    for p in paths_in(text):
        if not any(a["path"] == p for a in atts):
            atts.append(_att(p))
    rd = {"id": rid, "mode": mode if mode in ("direct", "terminal") else "direct", "limit": max(0, min(int(limit or 0), 3600)), "cut": False, "attachments": atts, "parent": parent if parent in COUNCIL else "", "tok": secrets.token_hex(3), "question": text, "main": main or "", "delegates": ids, "evaluate": bool(evaluate and main),
          "created": time.time(), "phase": "asking", "stop": False,
          "agents": {i: {"name": BY_ID[i]["name"], "state": "queued", "answer": ""} for i in ids},
          "eval": {"name": BY_ID[main]["name"] if main else "", "state": "queued", "answer": ""}}
    COUNCIL[rid] = rd
    COUNCIL_ORDER.append(rid)
    threading.Thread(target=_run_round, args=(rd,), daemon=True).start()
    _save_council()
    return {"ok": True, "id": rid}


def council_view(rid=""):
    rid = rid or (COUNCIL_ORDER[-1] if COUNCIL_ORDER else "")
    rd = COUNCIL.get(rid)
    if not rd:
        return {"round": None}
    pending = sum(1 for e in rd["agents"].values() if e.get("state") not in FINAL)
    return {"round": {k: v for k, v in rd.items() if k != "stop"} | {"stopped": rd["stop"], "pending": pending}}


def council_history():
    return [{"id": k, "question": COUNCIL[k]["question"][:80], "phase": COUNCIL[k]["phase"], "created": COUNCIL[k]["created"], "parent": COUNCIL[k].get("parent", "")}
            for k in reversed(COUNCIL_ORDER[-COUNCIL_MAX:]) if k in COUNCIL]


def council_stop(rid=""):
    rd = COUNCIL.get(rid or (COUNCIL_ORDER[-1] if COUNCIL_ORDER else ""))
    if not rd:
        raise ValueError("لا مجلس.")
    rd["stop"] = True
    return {"ok": True}


def council_evaluate(rid=""):
    """تقييم يدوي بما وصل حتى الآن (دون انتظار الباقين)."""
    rd = COUNCIL.get(rid or (COUNCIL_ORDER[-1] if COUNCIL_ORDER else ""))
    if not rd or not rd["main"]:
        raise ValueError("عيّن وكيلًا رئيسيًا أولًا.")
    if not any(_real(e) for e in rd["agents"].values()):
        raise ValueError("لم تصل أي إجابة حقيقية بعد (رسائل التشغيل وشريط الحالة لا تُحسب).")
    rd["stop"] = False

    def run():
        _run_eval(rd)
        rd["phase"] = "done"
        _save_council()
    threading.Thread(target=run, daemon=True).start()
    return {"ok": True}


def council_export(rid, fmt):
    """يحفظ الجولة في مجلد التنزيلات (md/docx/pdf) ويعيد المسار."""
    import council_export as CE
    rd = COUNCIL.get(rid or (COUNCIL_ORDER[-1] if COUNCIL_ORDER else ""))
    if not rd:
        raise ValueError("لا مجلس.")
    if not any(e.get("answer") for e in rd["agents"].values()):
        raise ValueError("لا توجد إجابات للتصدير بعد.")
    path = CE.export(rd, {k: v["name"] for k, v in BY_ID.items()}, fmt)
    subprocess.run(["open", "-R", path], capture_output=True, timeout=10)
    return {"ok": True, "path": path}
