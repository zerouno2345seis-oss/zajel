"""الوصل مع Telegram: إشعارات، وأسئلة للمساعد، وأوامر جاهزة، من بوت واحد.
- مفتاح البوت يُحفظ في سلسلة مفاتيح الماك فقط (لا في أي ملف).
- لا يُصغى إلا لمحادثتك أنت: تُربط مرة واحدة برمز اقتران يظهر في الإعدادات.
- أي عملية حمراء (حذف، نقل…) لا تتم من Telegram: تبقى بانتظار موافقتك داخل زاجل.
- أكثر من كمبيوتر على البوت نفسه: Telegram يسمح بمستمع واحد، فمن يفتح أولًا يصير «البوابة»، وإن أُغلق يتولى الآخر تلقائيًا."""
import json
import random
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

DATA = None
LOCK = threading.RLock()
SERVICE = "zajel-telegram-bot"
STATE = {"gateway": False, "running": False, "error": "", "bot": "", "pair_code": "", "pair_until": 0}
_thread = None
_stop = threading.Event()
DEFAULTS = {"enabled": False, "chat_id": 0, "notify_error": True, "notify_long": True, "notify_update": True, "long_secs": 60, "offset": 0}


def init(data_dir):
    global DATA
    DATA = __import__("pathlib").Path(data_dir)
    if _cfg()["enabled"] and _token():
        start()


def _cfg():
    try:
        d = json.loads((DATA / "telegram.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {**DEFAULTS, **d}


def _save_cfg(d):
    with LOCK:
        c = {**_cfg(), **d}
        (DATA / "telegram.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        return c


def _token():
    r = subprocess.run(["security", "find-generic-password", "-a", "zajel", "-s", SERVICE, "-w"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return r.stdout.strip() if r.returncode == 0 else ""


def set_token(tok):
    tok = str(tok or "").strip()
    if not re.fullmatch(r"\d{6,12}:[A-Za-z0-9_\-]{30,}", tok):
        raise ValueError("شكل المفتاح غير صحيح. انسخه كما أعطاه BotFather.")
    me = _api(tok, "getMe", {}, timeout=15)           # تحقق قبل الحفظ
    subprocess.run(["security", "add-generic-password", "-a", "zajel", "-s", SERVICE, "-w", tok, "-U"], capture_output=True, stdin=subprocess.DEVNULL, check=True)
    STATE["bot"] = me.get("username", "")
    _save_cfg({"bot": STATE["bot"], "enabled": True, "chat_id": 0})
    new_pair_code()                       # الاقتران تلقائي: رابط واحد يضغطه المستخدم في تيليجرام
    start()
    return STATE["bot"]


def forget():
    stop()
    subprocess.run(["security", "delete-generic-password", "-a", "zajel", "-s", SERVICE], capture_output=True, stdin=subprocess.DEVNULL)
    _save_cfg({"enabled": False, "chat_id": 0, "bot": ""})
    STATE.update(bot="", gateway=False, error="")


def _api(tok, method, params, timeout=40):
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/{method}", data=json.dumps(params).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 409:
            raise ConflictError()
        raise ValueError("رفض Telegram الطلب (%s)." % e.code)
    except (urllib.error.URLError, OSError):
        raise ValueError("لا اتصال بـ Telegram.")
    if not d.get("ok"):
        raise ValueError(str(d.get("description"))[:100])
    return d["result"]


class ConflictError(Exception):
    pass


def status():
    c = _cfg()
    if DATA and not c["chat_id"] and _token():
        if not c["enabled"]:
            c = _save_cfg({"enabled": True})      # مفتاح محفوظ بلا اقتران: لا معنى لتركه معطّلًا
        if STATE["pair_until"] <= time.time():
            new_pair_code()
        start()                                   # يعيد التشغيل إن كان الاستماع متوقفًا
    live = STATE["pair_until"] > time.time()
    return {"pair_link": f"https://t.me/{c.get('bot')}?start={STATE['pair_code']}" if live and c.get("bot") else "", **{"has_token": bool(_token()) if DATA else False, "enabled": c["enabled"], "bot": c.get("bot", ""), "paired": bool(c["chat_id"]), "machine": socket.gethostname().split(".")[0],
            "gateway": STATE["gateway"], "running": STATE["running"], "error": STATE["error"],
            "pair_code": STATE["pair_code"] if live else "", "notify_error": c["notify_error"], "notify_long": c["notify_long"], "notify_update": c["notify_update"]}}


def configure(b):
    d = {k: bool(b[k]) for k in ("notify_error", "notify_long", "notify_update") if k in b}
    if "enabled" in b:
        d["enabled"] = bool(b["enabled"])
        if d["enabled"] and not _token():
            raise ValueError("احفظ مفتاح البوت أولًا.")
    _save_cfg(d)
    if d.get("enabled"):
        start()
    elif "enabled" in d:
        stop()
    return status()


def new_pair_code():
    STATE["pair_code"] = "%06d" % random.randint(0, 999999)
    STATE["pair_until"] = time.time() + 600
    return STATE["pair_code"]


def unpair():
    _save_cfg({"chat_id": 0})


def start():
    global _thread
    with LOCK:
        if _thread and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, daemon=True)
        _thread.start()


def stop():
    _stop.set()
    STATE["running"] = False
    STATE["gateway"] = False


def send(text, chat_id=None):
    tok, c = _token(), _cfg()
    chat = chat_id or c["chat_id"]
    if not tok or not chat:
        return False
    text = str(text)
    for i in range(0, len(text) or 1, 3900):
        try:
            _api(tok, "sendMessage", {"chat_id": chat, "text": text[i:i + 3900]}, timeout=20)
        except (ValueError, ConflictError):
            return False
    return True


def notify(kind, text):
    """إشعار تلقائي إن كان النوع مفعّلًا وكان هذا الجهاز مربوطًا؛ لا يعطّل أبدًا العمل الذي استدعاه."""
    try:
        c = _cfg()
        if c["enabled"] and c["chat_id"] and c.get("notify_" + kind):
            threading.Thread(target=send, args=(f"[{socket.gethostname().split('.')[0]}] {text}",), daemon=True).start()
    except Exception:
        pass


def _loop():
    STATE["running"] = True
    tok = _token()
    while not _stop.is_set() and tok:
        try:
            c = _cfg()
            ups = _api(tok, "getUpdates", {"offset": c["offset"], "timeout": 25, "allowed_updates": ["message"]}, timeout=40)
            STATE["gateway"], STATE["error"] = True, ""
            for u in ups:
                _save_cfg({"offset": u["update_id"] + 1})
                m = u.get("message") or {}
                if m.get("text"):
                    try:
                        _handle(tok, m["chat"]["id"], m["text"].strip())
                    except Exception as exc:
                        send("تعذّر تنفيذ الطلب: " + str(exc)[:150], m["chat"]["id"])
        except ConflictError:
            STATE["gateway"], STATE["error"] = False, "هذا البوت يستمع إليه برنامج آخر الآن (جهاز آخر، أو برنامج استعملتَ مفتاحه نفسه مثل Hermes أو AutoClaw)، أو عليه رابط ويب قديم. استعمل بوتًا جديدًا لزاجل وحده من BotFather."
            _stop.wait(20)
        except ValueError as exc:
            STATE["gateway"], STATE["error"] = False, str(exc)
            _stop.wait(15)
        except Exception as exc:
            STATE["error"] = str(exc)[:100]
            _stop.wait(15)
    STATE["running"] = False
    STATE["gateway"] = False


def _handle(tok, chat, text):
    import agent_runner
    c = _cfg()
    if not c["chat_id"]:
        m = re.match(r"/start\s+(\d{6})$", text)
        if m and STATE["pair_code"] == m.group(1) and STATE["pair_until"] > time.time():
            _save_cfg({"chat_id": chat})
            STATE["pair_code"] = ""
            send("تم الربط بزاجل على " + socket.gethostname().split(".")[0] + ". اكتب /help لمعرفة الأوامر.", chat)
        return                                    # غير المقترن: لا ردّ إطلاقًا
    if chat != c["chat_id"]:
        return
    if text.startswith("/help") or text == "/start":
        send("الأوامر:\n/status حال الوكلاء\n/cmds الأوامر الجاهزة\n/run رقم تنفيذ أمر جاهز\n/ask سؤالك (أو اكتب السؤال مباشرة)\n\nالعمليات الحمراء (حذف، نقل…) لا تتم من هنا؛ تنتظر موافقتك داخل زاجل.", chat)
    elif text.startswith("/status"):
        import agent_metrics
        s = agent_metrics.stats(24, {a["id"]: a["installed"] for a in agent_runner.agents()}, [a["id"] for a in agent_runner.agents()])
        nm = {a["id"]: a["name"] for a in agent_runner.agents()}
        lab = {"ok": "يعمل", "slow": "بطيء", "down": "متوقف", "idle": "لم يُجرَّب"}
        send("\n".join(f"{nm.get(a['id'], a['id'])}: {lab[a['status']]}" + (f" — وسيط {a['median']} ث" if a["median"] else "") for a in s["agents"]), chat)
    elif text.startswith("/cmds"):
        import assistant_store
        ps = assistant_store.prompts_list()
        send("\n".join(f"{i + 1}. {p.get('title') or p.get('text', '')[:40]}" for i, p in enumerate(ps)) or "لا أوامر جاهزة بعد. أضفها من تبويب «الأوامر» في زاجل.", chat)
    elif text.startswith("/run"):
        import assistant_store
        ps = assistant_store.prompts_list()
        try:
            p = ps[int(text.split()[1]) - 1]
        except (IndexError, ValueError):
            raise ValueError("اكتب /run ثم رقم الأمر كما في /cmds")
        _ask(chat, p.get("text") or p.get("prompt") or "")
    else:
        _ask(chat, re.sub(r"^/ask\s*", "", text))


def _ask(chat, q):
    import agent_runner
    if not q.strip():
        raise ValueError("السؤال فارغ.")
    s = agent_runner.settings()
    r = agent_runner.start_chat(s["default_agent"], q, "", "telegram")
    send("وصلني، أعمل عليه…", chat)
    t0 = time.time()
    while time.time() - t0 < 600:
        v = agent_runner.job_view(r["job"])
        if v["state"] != "running":
            break
        time.sleep(3)
    else:
        send("ما زال يعمل أو ينتظر موافقتك داخل زاجل. ستجد الردّ في محادثة «telegram».", chat)
        return
    out = re.sub(r"\[\[خيارات:.*?\]\]", "", v["text"] or "", flags=re.S).strip()
    send(out or ("تعذّر: " + (v["error"] or "لا ردّ")), chat)
