"""ربط البريد عبر صفحة الدخول الرسمية (OAuth 2.0 + PKCE) بدل كلمة مرور التطبيق.

يفتح زاجل صفحة الدخول الرسمية لجيميل/أوتلوك/ياهو في المتصفح؛ تسجّل أنت الدخول هناك، فيعيدك المزوّد إلى زاجل على
127.0.0.1 ويستلم زاجل رمزًا للقراءة فقط (لا يرى كلمة مرورك أبدًا). الرموز تُحفظ في سلسلة مفاتيح macOS.
يلزم مرة واحدة معرّف تطبيق (Client ID) يسجّله المستخدم عند المزوّد، لأن المزوّدين لا يسمحون بتطبيق بلا تسجيل.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.parse
import urllib.request

PORT = 8766
PROVIDERS = {
    "google": {"name": "جيميل (Google)", "host": "imap.gmail.com", "domains": ["gmail.com", "googlemail.com"],
               "auth": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
               "scope": "https://mail.google.com/ openid email", "extra": {"access_type": "offline", "prompt": "consent"},
               "console": "https://console.cloud.google.com/apis/credentials", "secret": True,
               "howto": "في Google Cloud: أنشئ مشروعًا ← فعّل Gmail API ← «OAuth client ID» من نوع «Desktop app» وانسخ المعرّف والسرّ هنا."},
    "microsoft": {"name": "أوتلوك / هوتميل (Microsoft)", "host": "outlook.office365.com", "domains": ["outlook.com", "hotmail.com", "live.com", "msn.com"],
                  "auth": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize", "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                  "scope": "https://outlook.office.com/IMAP.AccessAsUser.All offline_access openid email", "extra": {"prompt": "select_account"},
                  "console": "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade", "secret": False,
                  "howto": "في Microsoft Entra: App registrations ← تطبيق جديد (أي حسابات) ← أضف Redirect URI من نوع «Mobile and desktop» بالقيمة الظاهرة أسفل ← انسخ Application (client) ID."},
    "yahoo": {"name": "ياهو (Yahoo)", "host": "imap.mail.yahoo.com", "domains": ["yahoo.com", "ymail.com"],
              "auth": "https://api.login.yahoo.com/oauth2/request_auth", "token": "https://api.login.yahoo.com/oauth2/get_token",
              "scope": "mail-r openid", "extra": {}, "console": "https://developer.yahoo.com/apps/", "secret": True,
              "howto": "في Yahoo Developer: أنشئ تطبيقًا بصلاحية Mail (قراءة) وRedirect URI الظاهر أسفل، وانسخ المعرّف والسرّ."},
}
PENDING: dict[str, dict] = {}
_TOK: dict[str, tuple[str, float]] = {}
LOCK = threading.Lock()


def redirect_uri():
    return f"http://127.0.0.1:{PORT}/api/assistant/mail/oauth/callback"


def provider_for(addr):
    dom = (addr or "").split("@")[-1].lower()
    for k, p in PROVIDERS.items():
        if dom in p["domains"]:
            return k
    return ""


def _kc():
    import zajel_mail as M
    return M


def _client(provider):
    raw = _kc()._kc_get("oauth-client:" + provider)
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


def config():
    out = []
    for k, p in PROVIDERS.items():
        c = _client(k)
        out.append({"id": k, "name": p["name"], "configured": bool(c.get("client_id")), "needs_secret": p["secret"], "console": p["console"], "howto": p["howto"]})
    return {"providers": out, "redirect": redirect_uri()}


def set_client(provider, client_id, client_secret=""):
    if provider not in PROVIDERS:
        raise ValueError("مزوّد غير معروف.")
    client_id = (client_id or "").strip()
    if len(client_id) < 8:
        raise ValueError("أدخل معرّف التطبيق (Client ID) كاملًا.")
    if PROVIDERS[provider]["secret"] and not (client_secret or "").strip():
        raise ValueError("هذا المزوّد يطلب أيضًا السرّ (Client Secret).")
    _kc()._kc_set("oauth-client:" + provider, json.dumps({"client_id": client_id, "client_secret": (client_secret or "").strip()}))
    return config()


def start(provider, email_hint=""):
    p = PROVIDERS.get(provider)
    if not p:
        raise ValueError("مزوّد غير معروف.")
    c = _client(provider)
    if not c.get("client_id"):
        raise ValueError("NEED_CLIENT")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    with LOCK:
        for k in [k for k, v in PENDING.items() if time.time() - v["t"] > 900]:
            PENDING.pop(k, None)
        PENDING[state] = {"provider": provider, "verifier": verifier, "email": (email_hint or "").strip().lower(), "t": time.time(), "result": None}
    q = {"client_id": c["client_id"], "redirect_uri": redirect_uri(), "response_type": "code", "scope": p["scope"], "state": state,
         "code_challenge": challenge, "code_challenge_method": "S256"} | p["extra"]
    if email_hint and provider in ("google", "microsoft"):
        q["login_hint"] = email_hint
    return {"url": p["auth"] + "?" + urllib.parse.urlencode(q), "state": state}


def _post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            d = {}
        raise ValueError((d.get("error_description") or d.get("error") or f"HTTP {e.code}")[:200])


def _id_email(id_token):
    try:
        seg = id_token.split(".")[1]
        seg += "=" * (-len(seg) % 4)
        d = json.loads(base64.urlsafe_b64decode(seg))
        return (d.get("email") or d.get("preferred_username") or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def callback(params):
    """يُستدعى من المتصفح بعد دخول المستخدم؛ يعيد (ok, رسالة)."""
    state = (params.get("state") or [""])[0]
    with LOCK:
        pend = PENDING.get(state)
    if not pend:
        return False, "طلب الربط غير معروف أو انتهت مهلته؛ ابدأ من زاجل من جديد."
    if (params.get("error") or [""])[0]:
        pend["result"] = {"ok": False, "error": (params.get("error_description") or params.get("error"))[0][:200]}
        return False, "لم يكتمل الدخول: " + pend["result"]["error"]
    code = (params.get("code") or [""])[0]
    p, c = PROVIDERS[pend["provider"]], _client(pend["provider"])
    try:
        data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(), "client_id": c["client_id"], "code_verifier": pend["verifier"]}
        if c.get("client_secret"):
            data["client_secret"] = c["client_secret"]
        tok = _post(p["token"], data)
        addr = _id_email(tok.get("id_token", "")) or pend["email"]
        if not addr or not tok.get("refresh_token"):
            raise ValueError("لم يُرجع المزوّد حسابًا أو رمز تجديد؛ أعد المحاولة ووافق على كل الصلاحيات." if not addr else "لم يُرجع المزوّد رمز تجديد؛ أعد المحاولة.")
        M = _kc()
        M._kc_set(addr, json.dumps({"oauth": pend["provider"], "refresh": tok["refresh_token"]}))
        _TOK[addr] = (tok["access_token"], time.time() + int(tok.get("expires_in", 3000)) - 60)
        a = {"email": addr, "host": p["host"], "label": "", "auth": "oauth", "provider": pend["provider"]}
        with M.LOCK:
            rows = [r for r in M._load() if r["email"] != addr] + [a]
            M._save(rows)
        pend["result"] = {"ok": True, "email": addr}
        return True, "تم ربط " + addr
    except ValueError as e:
        pend["result"] = {"ok": False, "error": str(e)}
        return False, str(e)


def poll(state):
    pend = PENDING.get(state)
    return (pend or {}).get("result") or {"pending": bool(pend)}


def access_token(addr):
    tok = _TOK.get(addr)
    if tok and tok[1] > time.time():
        return tok[0]
    raw = _kc()._kc_get(addr)
    try:
        d = json.loads(raw)
        prov = d["oauth"]
    except Exception:  # noqa: BLE001
        raise ValueError("لا رمز دخول محفوظ لهذا الحساب؛ أعد ربطه.")
    p, c = PROVIDERS[prov], _client(prov)
    data = {"grant_type": "refresh_token", "refresh_token": d["refresh"], "client_id": c.get("client_id", "")}
    if c.get("client_secret"):
        data["client_secret"] = c["client_secret"]
    r = _post(p["token"], data)
    _TOK[addr] = (r["access_token"], time.time() + int(r.get("expires_in", 3000)) - 60)
    if r.get("refresh_token") and r["refresh_token"] != d["refresh"]:
        _kc()._kc_set(addr, json.dumps({"oauth": prov, "refresh": r["refresh_token"]}))
    return r["access_token"]


def open_browser(url_or_provider, console=False):
    """يفتح المتصفح الافتراضي من الخادم (نافذة التطبيق لا تفتح روابط خارجية)؛ لا يقبل إلا روابط المزوّدين المعروفة."""
    import subprocess
    if console:
        p = PROVIDERS.get(url_or_provider)
        if not p:
            raise ValueError("مزوّد غير معروف.")
        url = p["console"]
    else:
        url = url_or_provider
        if not any(url.startswith(q["auth"] + "?") for q in PROVIDERS.values()):
            raise ValueError("رابط غير مسموح.")
    subprocess.Popen(["/usr/bin/open", url])
    return {"ok": True}
