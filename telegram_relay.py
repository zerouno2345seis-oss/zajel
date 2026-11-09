"""اتصال الماك بالوسيط (Cloudflare Worker): الماك هو الذي يسأل الوسيط عمّا ينتظره ثم يردّ، فلا منفذ مفتوح على الماك.
- مفتاح الماك مع الوسيط يُحفظ في سلسلة مفاتيح الماك فقط، ولا يُكتب في ملف ولا سجل.
- كل طلب يصل موقَّعًا من الوسيط، وتتحقق منه miniapp_api ثانية (المستخدم المقترن وحده)."""
import json
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.request

import telegram_link as TL

SERVICE = "zajel-relay-key"
STATE = {"running": False, "ok": False, "error": "", "last": 0.0, "handled": 0}
_thread = None
_stop = threading.Event()


def _key():
    r = subprocess.run(["security", "find-generic-password", "-a", "zajel", "-s", SERVICE, "-w"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return r.stdout.strip() if r.returncode == 0 else ""


def _set_key(k):
    subprocess.run(["security", "add-generic-password", "-a", "zajel", "-s", SERVICE, "-w", k, "-U"], capture_output=True, stdin=subprocess.DEVNULL, check=True)


def url():
    return (TL._cfg().get("relay_url") or "").rstrip("/")


def configure(relay_url):
    relay_url = str(relay_url or "").strip().rstrip("/")
    if relay_url and not relay_url.startswith("https://"):
        raise ValueError("عنوان الوسيط يجب أن يبدأ بـ https://")
    TL._save_cfg({"relay_url": relay_url})
    if relay_url:
        start()
        set_menu_button()
    return status()


def new_key():
    """مفتاح جديد للماك مع الوسيط؛ يظهر مرة واحدة ليضعه المستخدم في الوسيط (wrangler secret put MAC_KEY)."""
    k = secrets.token_urlsafe(32)
    _set_key(k)
    return k


def status():
    return {"url": url(), "has_key": bool(_key()), "running": STATE["running"], "ok": STATE["ok"], "error": STATE["error"], "handled": STATE["handled"]}


def _http(method, path, body=None, timeout=40):
    req = urllib.request.Request(url() + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"X-Mac-Key": _key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def serve_one(job, handler=None):
    """ينفّذ طلبًا واحدًا ويعيد ردّه إلى الوسيط."""
    import miniapp_api
    h = handler or miniapp_api.handle
    try:
        reply = h({"user": job.get("user"), "op": job.get("op"), "args": job.get("args"), "confirm": job.get("confirm")})
    except Exception as e:
        reply = {"error": "تعذّر التنفيذ: " + str(e)[:100]}
    _http("POST", "/mac/reply", {"id": job["id"], "reply": reply}, timeout=20)
    STATE["handled"] += 1


def poll_once():
    r = _http("GET", "/mac/poll?device=" + urllib.parse.quote(TL.HOST) + "&wait=20", timeout=35)
    STATE.update(ok=True, error="", last=time.time())
    for job in r.get("jobs") or []:
        threading.Thread(target=serve_one, args=(job,), daemon=True).start()
    return len(r.get("jobs") or [])


def _loop():
    STATE["running"] = True
    while not _stop.is_set():
        if not (url() and _key()):
            _stop.wait(15)
            continue
        try:
            poll_once()
        except (urllib.error.URLError, OSError, ValueError) as e:
            STATE.update(ok=False, error=str(getattr(e, "reason", e))[:100])
            _stop.wait(10)
    STATE["running"] = False


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()


def set_menu_button():
    """زر القائمة في محادثة البوت يفتح التطبيق المصغّر."""
    if url():
        TL._quiet("setChatMenuButton", {"menu_button": {"type": "web_app", "text": "زاجل", "web_app": {"url": url() + "/"}}})


import urllib.parse  # noqa: E402  (يُستعمل في poll_once)
