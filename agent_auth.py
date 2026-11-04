"""تسجيل الدخول والخروج لكل وكيل: حالة سريعة موحّدة + فتح الدخول في نافذة طرفية + خروج مباشر.

لا يقرأ هذا الملف ولا يعرض أي رمز أو مفتاح: يعرض أسماء الحسابات (البريد) وتواريخ الانتهاء فقط.
"""
import json
import os
import re
import shlex
import stat
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import agent_runner as R

_CACHE = {"t": 0, "v": None}
TTL = 20

# الأمر الذي يُفتح في الطرفية للدخول؛ hint: تلميح يظهر للمستخدم حين لا يوجد أمر دخول مباشر
LOGIN = {
    "claude": {"cmd": ["claude", "auth", "login"]},
    "codex": {"cmd": ["codex", "login"]},
    "opencode": {"cmd": ["opencode", "auth", "login"]},
    "hermes": {"cmd": ["hermes", "auth", "add"]},
    "pi": {"cmd": ["pi"], "hint": "اكتب في الواجهة التي ستفتح:  /login  ثم اختر Antigravity (Google) وأكمل في المتصفح. بعدها اكتب /exit."},
    "agy": {"cmd": ["agy"], "hint": "إن طلب الدخول فأكمله في المتصفح؛ وإلا اكتب  /login  ثم اختر حسابك. بعدها اكتب /exit."},
}
# خروج مباشر بلا طرفية (الباقي يُفتح في الطرفية)
LOGOUT = {
    "claude": ["claude", "auth", "logout"],
    "codex": ["codex", "logout"],
    "hermes": ["hermes", "logout"],
}
LOGOUT_TERMINAL = {
    "opencode": {"cmd": ["opencode", "auth", "logout"]},
    "pi": {"cmd": ["pi"], "hint": "اكتب في الواجهة:  /logout  ثم اختر الحساب. بعدها اكتب /exit."},
    "agy": {"cmd": ["agy"], "hint": "اكتب في الواجهة:  /logout  ثم أكّد. بعدها اكتب /exit."},
}


def _run(cmd, timeout=10):
    e = {"PATH": R._env_path(), "HOME": str(Path.home()), "LANG": "en_US.UTF-8", "NO_COLOR": "1"} | {k: os.environ[k] for k in ("USER", "LOGNAME", "SHELL", "TMPDIR", "XDG_CONFIG_HOME", "__CF_USER_TEXT_ENCODING") if k in os.environ}
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=e, stdin=subprocess.DEVNULL)
    except Exception as ex:  # noqa: BLE001
        return type("X", (), {"returncode": 1, "stdout": "", "stderr": str(ex)})()


def _out(r):
    return ((getattr(r, "stdout", "") or "") + "\n" + (getattr(r, "stderr", "") or "")).strip()


def _ago(ms):
    d = ms / 1000 - time.time()
    if d <= 0:
        return "انتهت منذ " + _span(-d)
    return "تنتهي بعد " + _span(d)


def _span(s):
    if s < 3600:
        return f"{int(s // 60)} دقيقة"
    if s < 172800:
        return f"{int(s // 3600)} ساعة"
    return f"{int(s // 86400)} يومًا"


def _claude():
    r = _run(["claude", "auth", "status"])
    try:
        d = json.loads(r.stdout)
    except Exception:  # noqa: BLE001
        return {"state": "unknown", "detail": "تعذرت قراءة الحالة"}
    if d.get("loggedIn"):
        who = d.get("email") or d.get("orgName") or ""
        return {"state": "in", "who": who, "detail": d.get("subscriptionType") or d.get("authMethod") or ""}
    return {"state": "out", "detail": "غير مسجَّل"}


def _codex():
    t = _out(_run(["codex", "login", "status"]))
    if re.search(r"logged in", t, re.I):
        return {"state": "in", "detail": t.splitlines()[0][:80]}
    return {"state": "out", "detail": "غير مسجَّل"}


def _opencode():
    t = _out(_run(["opencode", "auth", "list"]))
    t = re.sub(r"\x1b\[[0-9;]*m", "", t)
    names = [re.sub(r"\s+(api|oauth|wellknown)\s*$", "", m).strip() for m in re.findall(r"●\s+(.+)", t)]
    if names:
        return {"state": "in", "detail": "، ".join(names[:4])}
    return {"state": "out", "detail": "لا مزوّد مسجَّل"}


def _hermes():
    t = re.sub(r"\x1b\[[0-9;]*m", "", _out(_run(["hermes", "auth", "list"], 12)))
    prov = re.findall(r"^(\w[\w.-]*) \(\d+ credentials?\)", t, re.M)
    if prov:
        return {"state": "in", "detail": "، ".join(prov[:4])}
    return {"state": "out", "detail": "لا مزوّد مسجَّل"}


def _pi_like(which):
    """pi وAntigravity يشتركان في حساب Google؛ نقرأ تاريخ الانتهاء والبريد دون إظهار الرموز."""
    f = Path.home() / ".pi/agent/auth.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        d = {}
    entry = d.get("antigravity") or d.get("google-antigravity")
    email = (d.get("antigravity") or {}).get("email", "")
    if not email:
        try:
            acc = json.loads((Path.home() / ".pi/agent/antigravity-accounts.json").read_text(encoding="utf-8"))
            email = next(iter(acc.get("accounts") or {}), "")
        except Exception:  # noqa: BLE001
            pass
    if not entry:
        return {"state": "out", "detail": "لا حساب Google مسجَّل"}
    exp = entry.get("expires") or 0
    has_refresh = bool(entry.get("refresh"))
    if exp and exp / 1000 < time.time() and not has_refresh:
        return {"state": "expired", "who": email, "detail": "انتهت الجلسة ولا رمز تجديد: سجّل الدخول من جديد"}
    return {"state": "in", "who": email, "detail": ("الرمز " + _ago(exp)) + (" · يتجدد تلقائيًا" if has_refresh else "") if exp else "حساب Google"}


FETCH = {"claude": _claude, "codex": _codex, "opencode": _opencode, "hermes": _hermes,
         "pi": lambda: _pi_like("pi"), "agy": lambda: _pi_like("agy")}


def _one(aid):
    if not R._which(R.AGENTS[aid]["bin"]):
        return {"id": aid, "name": R.AGENTS[aid]["name"], "installed": False, "state": "missing", "detail": "غير مثبّت"}
    try:
        v = FETCH[aid]()
    except Exception as e:  # noqa: BLE001
        v = {"state": "unknown", "detail": str(e)[:80]}
    out = {"id": aid, "name": R.AGENTS[aid]["name"], "installed": True, "who": "", "detail": "", "logout_direct": aid in LOGOUT} | v
    return out


def status(force=False):
    now = time.time()
    if not force and _CACHE["v"] and now - _CACHE["t"] < TTL:
        return _CACHE["v"]
    with ThreadPoolExecutor(max_workers=len(R.ORDER)) as pool:
        vals = list(pool.map(_one, R.ORDER))
    _CACHE.update(t=now, v=vals)
    return vals


def _terminal(cmd, title, hint=""):
    """يفتح نافذة Terminal تنفّذ الأمر؛ كلمات المرور ورموز التحقق يكتبها المستخدم بنفسه ولا يراها زاجل."""
    path_env = R._env_path()
    fd, path = tempfile.mkstemp(suffix=".command", prefix="zajel-auth-")
    lines = ["#!/bin/zsh", "clear", f"export PATH={shlex.quote(path_env)}", f"echo {shlex.quote(title)}", "echo"]
    if hint:
        lines += [f"echo {shlex.quote(hint)}", "echo"]
    lines += [" ".join(shlex.quote(c) for c in cmd), 'rm -f "$0"', "echo", "echo 'انتهى. ارجع إلى زاجل واضغط «تحقق الآن». يمكنك إغلاق هذه النافذة.'"]
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    subprocess.Popen(["/usr/bin/open", "-a", "Terminal", path])


def login(aid):
    spec = LOGIN.get(aid)
    if aid not in R.AGENTS or not spec:
        raise ValueError("وكيل غير معروف.")
    if not R._which(R.AGENTS[aid]["bin"]):
        raise ValueError("هذا الوكيل غير مثبّت على هذا الجهاز.")
    _terminal(spec["cmd"], "تسجيل الدخول: " + R.AGENTS[aid]["name"], spec.get("hint", ""))
    _CACHE["v"] = None
    return {"ok": True, "terminal": True, "message": "فُتحت نافذة الطرفية: أكمل الدخول فيها ثم اضغط «تحقق الآن»."}


def logout(aid):
    if aid not in R.AGENTS:
        raise ValueError("وكيل غير معروف.")
    if aid in LOGOUT:
        r = _run(LOGOUT[aid], 20)
        _CACHE["v"] = None
        if r.returncode != 0:
            raise ValueError((_out(r) or "فشل الخروج")[:200])
        return {"ok": True, "message": "تم تسجيل الخروج من " + R.AGENTS[aid]["name"] + "."}
    spec = LOGOUT_TERMINAL.get(aid)
    if not spec:
        raise ValueError("لا يدعم هذا الوكيل الخروج من هنا.")
    _terminal(spec["cmd"], "تسجيل الخروج: " + R.AGENTS[aid]["name"], spec.get("hint", ""))
    _CACHE["v"] = None
    return {"ok": True, "terminal": True, "message": "فُتحت نافذة الطرفية لإتمام الخروج ثم اضغط «تحقق الآن»."}
