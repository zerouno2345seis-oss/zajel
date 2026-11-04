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
DEFAULTS = {"enabled": False, "chat_id": 0, "notify_error": True, "notify_long": True, "notify_update": True, "notify_done": True, "long_secs": 60, "offset": 0, "conv": "telegram", "approve_red": True}


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
    err = STATE["error"]
    if err.startswith("هذا البوت يستمع إليه"):
        gw = [h for h, p in MAIL["presence"].items() if h != HOST and p.get("gateway")]
        if gw or not c["chat_id"]:
            err = (f"الجهاز {gw[0]} يستقبل رسائل البوت الآن، وهذا طبيعي ما دام المفتاح نفسه على الجهازين. " if gw else
                   "جهاز آخر يستقبل رسائل البوت الآن (إن كان مفتاحك على الـiMac أيضًا فهذا طبيعي). ") + \
                  ("هذا الجهاز ينضم تلقائيًا بعد «زامن الآن» على الجهازين، ولا يلزمه اقتران." if not c["chat_id"] else "يجيب هذا الجهاز عندما تختاره من «الأجهزة».")
    return {"pair_link": f"https://t.me/{c.get('bot')}?start={STATE['pair_code']}" if live and c.get("bot") else "", **{"has_token": bool(_token()) if DATA else False, "enabled": c["enabled"], "bot": c.get("bot", ""), "paired": bool(c["chat_id"]), "machine": socket.gethostname().split(".")[0],
            "gateway": STATE["gateway"], "running": STATE["running"], "error": err,
            "pair_code": STATE["pair_code"] if live else "", "notify_error": c["notify_error"], "notify_long": c["notify_long"], "notify_update": c["notify_update"], "notify_done": c["notify_done"], "approve_red": c["approve_red"]}}


def configure(b):
    d = {k: bool(b[k]) for k in ("notify_error", "notify_long", "notify_update", "notify_done", "approve_red") if k in b}
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
        global _mail_thread
        if not (_mail_thread and _mail_thread.is_alive()):
            _mail_thread = threading.Thread(target=_mail_loop, daemon=True)
            _mail_thread.start()
        global _pusher
        if not (_pusher and _pusher.is_alive()):
            _pusher = threading.Thread(target=_pending_loop, daemon=True)
            _pusher.start()


def stop():
    _stop.set()
    STATE["running"] = False
    STATE["gateway"] = False


def _tok():
    global _TOK
    if not _TOK:
        _TOK = _token()
    return _TOK


_TOK = ""


def send(text, chat_id=None, kb=None, reply_kb=None):
    """يرسل نصًّا (يقسّمه إن طال) ويعيد رقم آخر رسالة؛ kb أزرار داخل الرسالة، reply_kb لوحة المفاتيح الدائمة."""
    chat = chat_id or _cfg()["chat_id"]
    if not _tok() or not chat:
        return 0
    text = re.sub(r"^>\s?", "", re.sub(r"\*\*|`", "", str(text)), flags=re.M) or "…"      # تيليجرام هنا نصّ خام: لا تُعرض علامات الماركداون
    parts = [text[i:i + 3900] for i in range(0, len(text), 3900)]
    mid = 0
    for n, part in enumerate(parts):
        p = {"chat_id": chat, "text": part}
        if n == len(parts) - 1:
            if kb:
                p["reply_markup"] = {"inline_keyboard": kb}
            elif reply_kb:
                p["reply_markup"] = {"keyboard": reply_kb, "resize_keyboard": True, "is_persistent": True}
        try:
            mid = _api(_tok(), "sendMessage", p, timeout=20).get("message_id", 0)
        except (ValueError, ConflictError):
            return 0
    return mid


def edit(chat, mid, text, kb=None):
    p = {"chat_id": chat, "message_id": mid, "text": str(text)[:3900] or "…"}
    if kb is not None:
        p["reply_markup"] = {"inline_keyboard": kb}
    try:
        _api(_tok(), "editMessageText", p, timeout=20)
    except (ValueError, ConflictError):
        pass


def _quiet(method, params):
    try:
        return _api(_tok(), method, params, timeout=15)
    except (ValueError, ConflictError):
        return None


def notify(kind, text):
    """إشعار تلقائي إن كان النوع مفعّلًا وكان هذا الجهاز مربوطًا؛ لا يعطّل أبدًا العمل الذي استدعاه."""
    try:
        c = _cfg()
        if c["enabled"] and c["chat_id"] and c.get("notify_" + kind):
            threading.Thread(target=send, args=(f"[{socket.gethostname().split('.')[0]}] {text}",), daemon=True).start()
    except Exception:
        pass


def notify_job(label, state, secs, error="", detail=""):
    """إشعار نهاية مهمة (تحليل، تنظيف، تفريغ، تحويل). ما دون ثلاث ثوانٍ لا يُشعِر حتى لا يغرقك البوت."""
    try:
        if state == "done" and secs >= 3:
            notify("done", f"اكتمل {label} بعد {int(secs)} ثانية. {detail}".strip())
        elif state == "error":
            notify("error", f"فشل {label}: {str(error)[:200]}")
    except Exception:
        pass


# ================= الاستماع والتوجيه =================
MAIN_KB = [["الرئيسية", "الأجهزة", "الوكلاء"], ["المجلس", "الطرفية", "واتساب"], ["العمليات", "الأتمتة", "بحث"], ["الذاكرة", "الأوامر", "المساعدة"], ["المزامنة", "التحديث", "حديث"]]
ONESHOT = {"host": ""}


def _alias(h):
    return h.split("-")[0] or h


def _kb():
    """لوحة المفاتيح الدائمة: صف أول بزر لكل جهاز (▶ الحالي)، ثم الأقسام."""
    hs = sorted(_presence())
    row = [("▶ " if h == _target() else "") + "💻 " + _alias(h) for h in hs] if len(hs) > 1 else []
    return ([row] if row else []) + MAIN_KB


def _host_by_button(text):
    t = text.replace("▶", "").replace("💻", "").strip().lower()
    for h in _presence():
        if t in (h.lower(), _alias(h).lower()):
            return h
    return ""
BTN = {"الرئيسية": "home", "الأجهزة": "pc", "حديث": "talk", "الوكلاء": "agents", "العمليات": "ops", "الأتمتة": "auto", "بحث": "findhelp",
       "الذاكرة": "mem", "الأوامر": "cmds", "المهام": "jobs", "المساعدة": "help",
       "المجلس": "council", "الطرفية": "term", "واتساب": "wa", "المزامنة": "sync", "التحديث": "update"}
COMMANDS = [("home", "الرئيسية: ملخص الجهاز الحالي"), ("pc", "الأجهزة: بدّل بين الكمبيوترين"), ("agents", "الوكلاء: الحال وتبديل المساعد"),
            ("ops", "العمليات الجارية: إيقاف مؤقت وإلغاء"), ("auto", "الأتمتة: عرض وتشغيل وإيقاف"), ("find", "بحث في كل الأجهزة: /find كلمة"),
            ("space", "المساحة الحرة"), ("jobs", "المهام والموافقات المعلّقة"), ("mem", "الذاكرة"), ("cmds", "الأوامر الجاهزة"),
            ("new", "محادثة جديدة مع المساعد"), ("chats", "تابع محادثة من زاجل"), ("settings", "الإعدادات"), ("help", "المساعدة"),
            ("council", "مجلس الوكلاء: اختيار الفريق وإرسال سؤال: /council سؤال"), ("cres", "نتيجة آخر مجلس"), ("cfollow", "متابعة على آخر حكم: /cfollow سؤال"),
            ("cstop", "إيقاف المجلس"), ("cweb", "رابط موقع تُرسل إليه النتيجة: /cweb رابط"), ("term", "الطرفية: جلسات الوكلاء"),
            ("tsend", "إرسال نص لطرفية وكيل: /tsend وكيل نص"), ("sync", "المزامنة بين الجهازين"), ("update", "فحص التحديث وتثبيته"), ("wa", "واتساب: الحال والملخص"),
            ("mail", "البريد: الحسابات والبحث: /mail كلمة"), ("auth", "حالة دخول الوكلاء"), ("disks", "الأقراص ومساحتها"), ("clean", "التنظيف الكامل بخطة وموافقة"), ("talk", "حديث مباشر مع وكيل في طرفيته"), ("endtalk", "إنهاء الحديث المباشر")]
HOST = socket.gethostname().split(".")[0]
FIND = {}
OPTS = {}          # خيارات الأزرار المقترحة من المساعد: رقم ← نص
CODES = {}         # رمز التأكيد الثاني لكل طلب أحمر
SEEN_PENDING = set()


def _loop():
    STATE["running"] = True
    global _TOK
    _TOK = _token()
    tok = _TOK
    try:
        _quiet("setMyCommands", {"commands": [{"command": c, "description": d} for c, d in COMMANDS]})
    except Exception:
        pass
    while not _stop.is_set() and tok:
        other = _other_gateway()
        if other:                                   # جهاز آخر يستقبل وحضوره حديث: لا ننازعه (كل طلب استقبال يقطع طلب الآخر)
            if STATE["gateway"]:
                STATE["gw_changed"] = True
            STATE["gateway"], STATE["error"] = False, f"الجهاز {other} يستقبل رسائل البوت الآن؛ هذا الجهاز يجيب حين تختاره من «الأجهزة»، ويتولى الاستقبال تلقائيًا إن أُغلق ذاك."
            _stop.wait(30)
            continue
        try:
            c = _cfg()
            ups = _api(tok, "getUpdates", {"offset": c["offset"], "timeout": 25, "allowed_updates": ["message", "callback_query"]}, timeout=40)
            if not STATE["gateway"]:
                STATE["gw_changed"] = True          # صرنا المستقبِل: سجّل الحضور فورًا ليعرفه الجهاز الآخر
            STATE["gateway"], STATE["error"] = True, ""
            for u in ups:
                _save_cfg({"offset": u["update_id"] + 1})
                threading.Thread(target=_route, args=(u,), daemon=True).start()      # كل طلب في خيط: لا يحجب الاستماع
        except ConflictError:
            if STATE["gateway"]:
                STATE["gw_changed"] = True
            STATE["gateway"] = False
            STATE["error"] = "هذا البوت يستمع إليه برنامج آخر الآن (جهاز آخر، أو برنامج استعملتَ مفتاحه نفسه مثل Hermes أو AutoClaw)."
            _stop.wait(45 if HOST > min([HOST] + list(MAIL["presence"])) else 20)      # كسر التعادل: الاسم الأصغر يعود أسرع
        except ValueError as exc:
            STATE["gateway"], STATE["error"] = False, str(exc)
            _stop.wait(15)
        except Exception as exc:
            STATE["error"] = str(exc)[:100]
            _stop.wait(15)
    STATE["running"] = False
    STATE["gateway"] = False


GW_FRESH = 420      # الحضور يُعدّ حيًّا ٧ دقائق (يُجدَّد كل ٣ دقائق)


def _is_laptop():
    try:
        return "InternalBattery" in subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5).stdout   # له بطارية ← محمول
    except Exception:
        return False


LAPTOP = None


def _other_gateway():
    """من يستقبل رسائل البوت؟ الجهاز المكتبي أولًا (لا ينام بإغلاق الغطاء)، ثم من يعلن الاستقبال بحضور حديث.
    عند التعادل يبقى صاحب الاسم الأصغر. يعيد اسم الجهاز الذي يجب أن نترك له الاستقبال، أو فارغًا."""
    global LAPTOP
    if LAPTOP is None:
        LAPTOP = _is_laptop()
    now = time.time()
    fresh = {h: p for h, p in MAIL["presence"].items() if h != HOST and now - p.get("ts", 0) < GW_FRESH}
    if LAPTOP:
        desk = sorted(h for h, p in fresh.items() if not p.get("laptop"))
        if desk:
            return desk[0]                  # جهاز مكتبي حيّ: هو المستقبِل
    for h, p in sorted(fresh.items()):
        if p.get("gateway") and bool(p.get("laptop")) == bool(LAPTOP):
            if STATE["gateway"] and HOST < h:
                continue
            return h
    return ""


def _dispatch(u):
    chat = None
    try:
        cb = u.get("callback_query")
        if cb:
            chat = cb["message"]["chat"]["id"]
            _quiet("answerCallbackQuery", {"callback_query_id": cb["id"]})
            if _authorized(chat):
                _on_callback(chat, cb["message"]["message_id"], cb.get("data") or "")
            return
        m = u.get("message") or {}
        chat = m.get("chat", {}).get("id")
        if not chat:
            return
        if m.get("voice") or m.get("audio"):
            if _authorized(chat):
                _on_voice(chat, m.get("voice") or m.get("audio"))
        elif m.get("text"):
            _on_text(chat, m["text"].strip())
    except Exception as exc:
        if chat:
            send("تعذّر تنفيذ الطلب: " + str(exc)[:150], chat)


def _authorized(chat):
    return bool(_cfg()["chat_id"]) and chat == _cfg()["chat_id"]


def _on_text(chat, text):
    c = _cfg()
    if not c["chat_id"]:                       # غير مقترن: لا ردّ إلا على رمز الاقتران
        m = re.match(r"/start\s+(\d{6})$", text)
        if m and STATE["pair_code"] == m.group(1) and STATE["pair_until"] > time.time():
            _save_cfg({"chat_id": chat})
            STATE["pair_code"] = ""
            send("تم الربط بزاجل على " + socket.gethostname().split(".")[0] + ".\nاكتب لي أو سجّل رسالة صوتية كما تكلّم المساعد في زاجل تمامًا. الأزرار أدناه للتنقّل السريع.", chat, reply_kb=_kb())
        return
    if chat != c["chat_id"]:
        return
    if chat in WAITWORD:
        import agent_server
        pid = WAITWORD.pop(chat)
        try:
            agent_server.approve(pid, text)
            send("✅ تم تنفيذ الطلب.", chat)
        except ValueError as e:
            send("لم يُنفَّذ: " + str(e), chat)
        return
    import telegram_extras as X
    if X.pending_text(chat, text):
        return
    word = text.split()[0] if text.split() else ""
    name = BTN.get(text) or (word[1:].split("@")[0] if word.startswith("/") else "")
    if not name and word == "مجلس" and len(text.split()) > 1:
        name = "council"
    if name in ("cweb", "cstop", "cres", "cfollow", "tsend") and X.on_special(chat, name, text):
        return
    if name in X.NAMES and X.on_command(chat, name, text):
        return
    if name in X.NAMES:
        _show(chat, name)
    elif name in ("home", "agents", "mem", "cmds", "jobs", "help", "chats", "settings", "ops", "auto", "space", "pc", "findhelp"):
        _show(chat, name)
    elif name == "find":
        _find(chat, text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else "")
    elif name == "new":
        _save_cfg({"conv": "telegram-" + time.strftime("%m%d%H%M%S")})
        send("بدأت محادثة جديدة مع المساعد.", chat)
    elif name == "run":
        import assistant_store
        try:
            p = assistant_store.prompts_list()[int(text.split()[1]) - 1]
        except (IndexError, ValueError):
            raise ValueError("اكتب /run ثم رقم الأمر كما في قائمة الأوامر.")
        _ask(chat, p.get("text") or "")
    elif name == "endtalk":
        import telegram_new
        telegram_new.talk_end(chat)
    else:
        import telegram_new
        if not word.startswith("/") and telegram_new.talk_message(chat, text):
            return
        _ask_batched(chat, re.sub(r"^/ask\s*", "", text))


BATCH = {"msgs": [], "timer": None}
BATCH_LOCK = threading.Lock()
BATCH_WAIT = 4.0
BATCH_WAIT_PART = 12.0      # رسالة قصيرة أو رابط وحده غالبًا جزء من طلب أطول؛ والتمرير بين الجهازين عبر المزامنة قد يفصل الرسائل بعدة ثوانٍ


def _ask_batched(chat, q):
    """رسائل تصل متتابعة (رابط ثم «تحليل» ثم رابط معاد توجيهه) تخص طلبًا واحدًا: ننتظر هدوءًا قصيرًا ونرسلها معًا.
    وإلا بدأ المساعد العمل على أول رسالة وحدها بلا الباقي فيسأل «ماذا تريد؟»."""
    with BATCH_LOCK:
        BATCH["msgs"].append(q)
        if BATCH["timer"]:
            BATCH["timer"].cancel()
        part = len(q.split()) <= 2 or bool(re.match(r"^\S*https?://\S+$", q.strip()))
        BATCH["timer"] = threading.Timer(BATCH_WAIT_PART if part else BATCH_WAIT, _flush_batch, args=(chat,))
        BATCH["timer"].daemon = True
        BATCH["timer"].start()


def _flush_batch(chat):
    with BATCH_LOCK:
        msgs, BATCH["msgs"], BATCH["timer"] = BATCH["msgs"], [], None
    msgs = [m for m in msgs if m.strip()]
    if not msgs:
        return
    q = msgs[0] if len(msgs) == 1 else "[رسائل متتابعة من تيليجرام تخص طلبًا واحدًا؛ اقرأها معًا:]\n" + "\n".join(f"{i}. {m}" for i, m in enumerate(msgs, 1))
    try:
        _ask(chat, q)
    except Exception as exc:
        send("تعذّر تنفيذ الطلب: " + str(exc)[:150], chat)


def _on_voice(chat, v):
    """رسالة صوتية ← تفريغ محلي بـ faster-whisper (لا يغادر الجهاز) ← يُعامل كأنك كتبته."""
    import media
    note = send("استمعت… أفرّغ الصوت.", chat)
    raw = _api(_tok(), "getFile", {"file_id": v["file_id"]}, timeout=20)
    with urllib.request.urlopen(f"https://api.telegram.org/file/bot{_tok()}/{raw['file_path']}", timeout=60) as r:
        data = r.read(25 * 1024 * 1024)
    saved = media.save_upload(data, f"telegram_voice_{int(time.time())}.ogg")
    res = media.transcribe(saved["path"], lang="ar", model="small", wait_seconds=90)
    if res.get("error"):
        edit(chat, note, "تعذّر التفريغ: " + str(res.get("error"))[:120] + ("\n" + str(res["hint"])[:160] if res.get("hint") else ""))
        return
    if res.get("state") not in (None, "done") and not res.get("text"):
        edit(chat, note, "التفريغ ما زال جاريًا (المرة الأولى تنزّل النموذج وقد تطول). أعد الإرسال بعد قليل.")
        return
    text = (res.get("text") or "").strip()
    if not text:
        edit(chat, note, "لم أسمع كلامًا واضحًا. أعد التسجيل.")
        return
    edit(chat, note, "فهمت: «" + text[:600] + "»")
    _ask(chat, text)


def _pick_agent():
    import agent_runner
    s = agent_runner.settings()
    order = [s["default_agent"]] + [a for a in agent_runner.ORDER if a != s["default_agent"]]
    for a in order:
        if agent_runner._which(agent_runner.AGENTS[a]["bin"]):
            return a
    raise ValueError("لا يوجد وكيل مثبّت على هذا الجهاز. ثبّت أحدهم (مثل Claude أو Antigravity) ثم أعد المحاولة.")


def _opts_kb(text):
    m = re.search(r"\[\[خيارات:(.*?)\]\]", text, flags=re.S)
    if not m:
        return text.strip(), None
    opts = [o.strip() for o in m.group(1).split("|") if o.strip()][:6]
    kb = []
    for o in opts:
        k = uuid_short()
        OPTS[k] = o
        kb.append([{"text": o[:60], "callback_data": "ans:" + k}])
    return re.sub(r"\[\[خيارات:.*?\]\]", "", text, flags=re.S).strip(), kb


def uuid_short():
    return "%06x" % random.randint(0, 0xFFFFFF)


def _ask(chat, q):
    """الطريق نفسه الذي تسلكه رسالتك في نافذة المساعد: الوكيل نفسه، والأدوات نفسها، والذاكرة نفسها، والمحادثة نفسها تظهر في زاجل."""
    import agent_runner
    if not q.strip():
        raise ValueError("السؤال فارغ.")
    agent = _pick_agent()
    r = agent_runner.start_chat(agent, q, "", _cfg()["conv"])
    if r.get("conversation") and r["conversation"] != _cfg()["conv"]:
        _save_cfg({"conv": r["conversation"]})     # المحادثة الفعلية تأخذ معرّفًا جديدًا؛ بدون حفظه تبدأ كل رسالة محادثة جديدة بلا ذاكرة، وتُرفض الرسالة التالية بـ«يعمل على محادثة أخرى»
    jid = r["job"]
    mid = send("أعمل على طلبك…", chat)
    last, t0, tick = "", time.time(), 0
    while time.time() - t0 < 1200 and not _stop.is_set():
        v = agent_runner.job_view(jid)
        if v["state"] != "running":
            break
        _quiet("sendChatAction", {"chat_id": chat, "action": "typing"})
        steps = (agent_runner.JOBS.get(jid) or {}).get("steps") or []
        label = steps[-1]["label"] if steps else "أفكّر…"
        if label != last and tick % 1 == 0:
            edit(chat, mid, "أعمل على طلبك…\n" + label)
            last = label
        _check_pending(chat, jid)
        tick += 1
        time.sleep(3)
    else:
        edit(chat, mid, "ما زال يعمل. ستجد الردّ في محادثتك داخل زاجل.")
        return
    _quiet("deleteMessage", {"chat_id": chat, "message_id": mid})
    out, kb = _opts_kb(v["text"] or "")
    if v["state"] == "done" and out:
        if len(_presence()) > 1:
            out += f"\n\n— {HOST}"
        send(out, chat, kb=kb)
    else:
        send("تعذّر: " + (v["error"] or "لا ردّ") if v["state"] == "error" else "أُوقفت المهمة.", chat)


def _desc_pending(p):
    pv = p.get("preview") or {}
    lines = [pv.get("title") or p["tool"]]
    for k, lab in (("from", "من"), ("to", "إلى"), ("count", "العدد")):
        if pv.get(k) not in (None, ""):
            lines.append(f"{lab}: {pv[k]}")
    if pv.get("bytes"):
        lines.append("الحجم: %.1f ميغابايت" % (pv["bytes"] / 1048576))
    if pv.get("items"):
        lines.append("أمثلة: " + "، ".join(pv["items"][:4]))
    return "\n".join(lines)


ICONS = {"whatsapp_send_message": "📤", "whatsapp_send_reply": "📤", "whatsapp_send_file": "📎", "whatsapp_send_template": "📤", "phone_delete": "🗑"}
WAITWORD = {}     # محادثة ← رقم طلب ينتظر كلمة تأكيد مكتوبة
_pusher = None


def _push_pending(chat, p):
    """يعرض طلب موافقة في تيليجرام بأزرار، أيًّا كان مصدره (نافذة زاجل أو تيليجرام أو أتمتة أو وكيل)."""
    ic = ICONS.get(p["tool"], "⚠️")
    host = f"\n💻 {HOST}" if len(_presence()) > 1 else ""
    body = f"{ic} طلب يحتاج موافقتك\n" + _desc_pending(p) + host + "\n⏳ ينتهي خلال %d دقيقة." % max(1, p["expires_in"] // 60)
    if not _cfg()["approve_red"]:
        send(body + "\n\nاعتماد العمليات من تيليجرام مغلق؛ وافق عليها داخل زاجل.", chat)
    elif p.get("needs_word"):
        send(body + "\n\nعملية حساسة: بعد الضغط على «اعتمد» اكتب كلمة التأكيد.", chat,
             kb=[[{"text": "✅ اعتمد", "callback_data": "word:" + p["id"]}, {"text": "❌ ارفض", "callback_data": "no:" + p["id"]}]])
    else:
        send(body, chat, kb=[[{"text": "✅ راجعتُ، تابع", "callback_data": "ok1:" + p["id"]}, {"text": "❌ ارفض", "callback_data": "no:" + p["id"]}]])


def _check_pending(chat, jid=None):
    import agent_server
    for p in agent_server.pending_list():
        if p["id"] in SEEN_PENDING:
            continue
        SEEN_PENDING.add(p["id"])
        _push_pending(chat, p)


def _pending_loop():
    while not _stop.is_set():
        try:
            c = _cfg()
            if c["chat_id"] and _token():
                _check_pending(c["chat_id"])
        except Exception:
            pass
        _stop.wait(4)


def _on_callback(chat, mid, data):
    import agent_server
    kind, _, rest = data.partition(":")
    if kind in ("cg", "cr", "tm", "sy", "up", "wa", "ml", "au", "fc", "tk"):
        import telegram_extras as X
        X.on_callback(chat, mid, kind, rest)
        return
    if kind == "ans":
        txt = OPTS.get(rest)
        if txt:
            edit(chat, mid, "اخترت: " + txt, [])
            _ask(chat, txt)
    elif kind == "no":
        try:
            agent_server.deny(rest); edit(chat, mid, "❌ رفضتَ الطلب.", [])
        except ValueError as e:
            edit(chat, mid, str(e), [])
    elif kind == "word":
        import agent_server
        pv = next((x for x in agent_server.pending_list() if x["id"] == rest), None)
        if not pv:
            edit(chat, mid, "الطلب غير موجود أو انتهت صلاحيته.", [])
        elif not _cfg()["approve_red"]:
            edit(chat, mid, "اعتماد العمليات من تيليجرام مغلق.", [])
        else:
            WAITWORD[chat] = rest
            edit(chat, mid, "اكتب الآن كلمة التأكيد «%s» في رسالة للموافقة، أو اكتب غير ذلك للإلغاء." % pv.get("needs_word"), [])
    elif kind == "ok1":
        code = "%04d" % random.randint(0, 9999)
        CODES[rest] = code
        edit(chat, mid, "تأكيد أخير: سيُنفَّذ الطلب فور ضغط الزر.", [[{"text": "نفّذ الآن (" + code + ")", "callback_data": f"ok2:{rest}:{code}"}], [{"text": "ارفض", "callback_data": "no:" + rest}]])
    elif kind == "ok2":
        pid, _, code = rest.partition(":")
        if not _cfg()["approve_red"] or CODES.get(pid) != code:
            edit(chat, mid, "رمز التأكيد غير صحيح أو أُغلق الاعتماد من تيليجرام.", [])
            return
        try:
            agent_server.approve(pid)
            CODES.pop(pid, None)
            edit(chat, mid, "✅ تم تنفيذ الطلب.", [])
        except ValueError as e:
            edit(chat, mid, str(e), [])
    elif kind == "scr":
        _show(chat, rest, mid)
    elif kind == "ping":
        import agent_runner
        r = agent_runner.ping(rest)
        edit(chat, mid, ("يستجيب" if r["alive"] else "لا يستجيب: " + r["why"]) + f" ({r['ms']} ميلي ثانية)", [[{"text": "رجوع", "callback_data": "scr:agents"}]])
    elif kind == "memdel":
        import assistant_store
        edit(chat, mid, "حذف هذا العنصر؟", [[{"text": "نعم احذف", "callback_data": "memdel2:" + rest}, {"text": "لا", "callback_data": "scr:mem"}]])
    elif kind == "memdel2":
        import assistant_store
        assistant_store.memory_delete(rest); _show(chat, "mem", mid)
    elif kind == "run":
        import assistant_store
        _ask(chat, assistant_store.prompts_list()[int(rest)].get("text") or "")
    elif kind == "cv":
        _save_cfg({"conv": rest}); edit(chat, mid, "تابعنا المحادثة المختارة. اكتب رسالتك.", [])
    elif kind == "def":
        import agent_runner
        agent_runner.set_settings({"default_agent": rest})
        _save_cfg({"conv": "telegram-" + time.strftime("%m%d%H%M%S")})      # مساعد جديد ← محادثة جديدة
        edit(chat, mid, "صار المساعد: " + agent_runner.AGENTS[rest]["name"] + ". بدأت محادثة جديدة معه.", [[_b("رجوع", "scr:agents")]])
    elif kind in ("opp", "opr", "opc"):
        import agent_server
        if kind == "opc":
            r = agent_server.call("cancel_op", {"id": rest}, agent="telegram")
        else:
            r = agent_server.call("pause_op", {"id": rest, "paused": kind == "opp"}, agent="telegram")
        if r.get("error"):
            send(r["error"], chat)
        _show(chat, "ops", mid)
    elif kind in ("aur", "auon", "auoff"):
        import agent_server
        if kind == "aur":
            r = agent_server.call("run_automation_now", {"id": rest}, agent="telegram")
            send((r.get("result") or {}).get("note") or r.get("error") or "فُحصت القاعدة.", chat)
        else:
            agent_server.call("toggle_automation", {"id": rest, "enabled": kind == "auon"}, agent="telegram")
            _show(chat, "auto", mid)
    elif kind == "snd":
        f = FIND.get(rest)
        if f:
            import agent_server
            r = agent_server.call("send_to_telegram", {"place": f[0], "path": f[1]}, agent="telegram")
            if r.get("error"):
                send(r["error"], chat)
    elif kind == "pc":
        _set_target(rest)
        _show(chat, "pc", mid)
        send(f"صار الجهاز الحالي: {rest}.", chat, reply_kb=_kb())
    elif kind == "one":
        ONESHOT["host"] = rest
        edit(chat, mid, f"اكتب سؤالك الآن (أو سجّله صوتًا)، وسيجيب عنه {rest} وحده، ثم نعود إلى {_target()}.", [])
    elif kind == "tg" and rest in ("notify_error", "notify_long", "notify_update", "notify_done"):     # اعتماد الحمراء يُفتح من زاجل وحده، لا من القناة نفسها
        _save_cfg({rest: not _cfg()[rest]}); _show(chat, "settings", mid)


def _show(chat, name, mid=None):
    text, kb = _screen(name)
    if mid:
        edit(chat, mid, text, kb)
    else:
        send(text, chat, kb=kb, reply_kb=_kb() if name in ("help", "home", "pc") else None)


def _b(t, d):
    return {"text": t, "callback_data": d}


def _screen(name):
    import agent_runner, agent_metrics, agent_server, assistant_store
    more = _screen_more(name)
    if more:
        return more
    back = [[_b("رجوع", "scr:home")]]
    if name == "home":
        ag = agent_metrics.stats(24, {a["id"]: a["installed"] for a in agent_runner.agents()}, [a["id"] for a in agent_runner.agents()])["agents"]
        up = sum(1 for a in ag if a["status"] in ("ok", "slow"))
        pend = len(agent_server.pending_list())
        return (f"زاجل {_version()} على {HOST}\nالمساعد: {agent_runner.AGENTS[agent_runner.settings()['default_agent']]['name']}\nالوكلاء العاملون: {up} من {len(ag)}\nطلبات تنتظر موافقتك: {pend}\nالمحادثة: {_cfg()['conv']}",
                [[_b("الأجهزة", "scr:pc"), _b("الوكلاء", "scr:agents")], [_b("العمليات", "scr:ops"), _b("الأتمتة", "scr:auto")], [_b("المساحة", "scr:space"), _b("الذاكرة", "scr:mem")],
                 [_b("المهام", "scr:jobs"), _b("الأوامر", "scr:cmds")], [_b("المجلس", "scr:council"), _b("الطرفية", "scr:term")],
                 [_b("واتساب", "scr:wa"), _b("التحديث", "scr:update")], [_b("المحادثات", "scr:chats"), _b("الإعدادات", "scr:settings")]])
    if name == "agents":
        names = {a["id"]: a["name"] for a in agent_runner.agents()}
        s = agent_metrics.stats(24, {a["id"]: a["installed"] for a in agent_runner.agents()}, list(names))
        lab = {"ok": "يعمل", "slow": "بطيء", "down": "متوقف", "idle": "لم يُجرَّب"}
        lines = [f"{names.get(a['id'], a['id'])}: {lab[a['status']]}" + (f" — وسيط {a['median']} ثانية" if a["median"] else "") + (f" ({a['why']})" if a["status"] == "down" else "") for a in s["agents"]]
        cur = agent_runner.settings()["default_agent"]
        inst = {a["id"]: a["installed"] for a in agent_runner.agents()}
        kb = [[_b("فحص " + names.get(a["id"], a["id"]), "ping:" + a["id"])] + ([_b("اجعله المساعد", "def:" + a["id"])] if inst.get(a["id"]) and a["id"] != cur else []) for a in s["agents"]]
        return f"المساعد الحالي: {names.get(cur, cur)}\n\n" + "\n".join(lines), kb + back
    if name == "mem":
        rows = assistant_store.memory_list()[-8:]
        txt = "الذاكرة: %d عنصرًا\n" % len(assistant_store.memory_list()) + "\n".join("• " + r["text"][:90] for r in rows)
        return txt, [[_b("حذف: " + r["text"][:28], "memdel:" + r["id"])] for r in rows[-4:]] + back
    if name == "cmds":
        ps = assistant_store.prompts_list()
        return ("الأوامر الجاهزة:\n" + "\n".join(f"{i + 1}. {p.get('title')}" for i, p in enumerate(ps))) if ps else "لا أوامر جاهزة بعد. أضفها من تبويب «الأوامر» في زاجل.", [[_b("شغّل: " + p.get("title", "")[:30], f"run:{i}")] for i, p in enumerate(ps[:8])] + back
    if name == "jobs":
        run = [j for j in agent_runner.JOBS.values() if j["state"] == "running"]
        pend = agent_server.pending_list()
        return f"مهام جارية: {len(run)}\nطلبات تنتظر موافقة: {len(pend)}" + "".join("\n• " + _desc_pending(p).split("\n")[0] for p in pend), back
    if name == "chats":
        cs = assistant_store.chats_list()[:6]
        return "محادثات زاجل (اضغط لمتابعة واحدة):", [[_b((c["title"] or "محادثة")[:40], "cv:" + c["id"])] for c in cs] + back
    if name == "settings":
        c = _cfg()
        on = lambda k: "مفعّل" if c[k] else "مغلق"
        return "الإعدادات:\nاعتماد العمليات الحمراء من تيليجرام: " + on("approve_red") + " (يُغيَّر من إعدادات زاجل فقط). يتطلب ضغطتين ورمزًا، والحذف النهائي لا يتم من هنا أبدًا.", [
            [_b("إشعار الفشل: " + on("notify_error"), "tg:notify_error")], [_b("إشعار الردّ الطويل: " + on("notify_long"), "tg:notify_long")],
            [_b("إشعار اكتمال المهام: " + on("notify_done"), "tg:notify_done")],
            ] + back
    return ("أنا نفس المساعد الذي في زاجل. اكتب لي بكلامك العادي، أو سجّل رسالة صوتية، وسأفهم وأنفّذ.\n"
            "أمثلة: «ما حال الوكلاء؟» · «انسخ صور هاتفي إلى القرص الأزرق» · «ابحث عن ملف العقد».\n"
            "اطلب «اعرض لي الملف كذا» فيصلك الملف هنا.\n"
            "الأوامر: /pc الأجهزة · /agents الوكلاء وتبديل المساعد · /ops العمليات · /auto الأتمتة · /find بحث · /space المساحة · /jobs الموافقات · /new محادثة جديدة.\n"
            "لتسأل الجهاز الآخر لمرة واحدة: اكتب اسمه ثم طلبك.\n"
            "العمليات الحمراء (نسخ ونقل وحذف) تصلك ببطاقة موافقة."), None


def _human(n):
    n = float(n or 0)
    for u in ("بايت", "كيلوبايت", "ميغابايت", "غيغابايت", "تيرابايت"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "بايت" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} بيتابايت"


def _screen_more(name):
    """شاشات إضافية: الأجهزة، العمليات، الأتمتة، المساحة، تعليمات البحث."""
    import agent_server
    import telegram_extras as X
    extra = X.screen(name)
    if extra:
        return extra
    back = [[_b("رجوع", "scr:home")]]
    if name == "ops":
        ops = (agent_server.call("list_ops", {}, agent="telegram").get("result") or {}).get("ops", [])
        run = [o for o in ops if o["state"] == "running"]
        lines = [f"• {o['title']}: {o['done']}/{o['total']}" + (" (موقوفة مؤقتًا)" if o.get("paused") else "") + (f" · متبقٍ {o['eta']} ث" if o.get("eta") else "") for o in run]
        lines += [f"✓ {o['title']} ({'تمت' if o['state'] == 'done' else o['state']})" for o in ops if o["state"] != "running"][:5]
        kb = [[_b("استئناف" if o.get("paused") else "إيقاف مؤقت", ("opr:" if o.get("paused") else "opp:") + o["id"]), _b("إلغاء", "opc:" + o["id"])] for o in run[:5]]
        return ("العمليات:\n" + "\n".join(lines)) if lines else "لا عمليات جارية ولا حديثة.", kb + [[_b("تحديث", "scr:ops")]] + back
    if name == "auto":
        res = agent_server.call("list_automations", {}, agent="telegram").get("result") or {}
        rules = res.get("rules", [])
        lines = [f"{'🟢' if r['enabled'] else '⚪'} {r['name']} — كل {r.get('every')} د" + (f" · آخر نتيجة: {r['last_note'][:60]}" if r.get("last_note") else "") for r in rules]
        kb = [[_b("شغّل الآن: " + r["name"][:20], "aur:" + r["id"]), _b("أوقف" if r["enabled"] else "شغّل", ("auoff:" if r["enabled"] else "auon:") + r["id"])] for r in rules[:6]]
        txt = ("قواعد الأتمتة:\n" + "\n".join(lines)) if rules else "لا قواعد أتمتة بعد. اطلب من المساعد مثلًا: «راقب مجلد التنزيلات كل ساعة وانقل ملفات PDF إلى مجلد الكتب»."
        n = res.get("notices") or []
        if n:
            txt += "\n\nإشعارات غير مقروءة:\n" + "\n".join("• " + str(x.get("text"))[:90] for x in n[:5])
        return txt, kb + back
    if name == "space":
        r = agent_server.call("disk_space", {}, agent="telegram").get("result") or {}
        c = r.get("computer") or {}
        lines = [f"الكمبيوتر: متاح {_human(c.get('free'))} من {_human(c.get('total'))}"]
        lines += [f"{d['name']}: متاح {_human(d.get('free'))} من {_human(d.get('total'))}" for d in r.get("disks", [])]
        ph = r.get("phone") or {}
        if ph.get("free"):
            lines.append(f"الهاتف: متاح {_human(ph.get('free'))}")
        return "المساحة:\n" + "\n".join(lines), back
    if name == "findhelp":
        return "اكتب: /find ثم جزءًا من اسم الملف.\nمثال: /find عقد الإيجار\nأو اطلب من المساعد بكلامك: «ابحث عن صور رحلة الصيف وأرسل لي أحدثها».", back
    if name == "pc":
        tgt = _target()
        rows, kb = [], []
        for h, p in sorted(_presence().items()):
            age = time.time() - p.get("ts", 0)
            st = "متصل" if age < GW_FRESH else f"غير متصل منذ {int(age // 3600)} ساعة" if age > 3600 else f"غير متصل منذ {int(age // 60)} دقيقة"
            rows.append(("▶ " if h == tgt else "• ") + f"{h} — {st}" + (" · الإصدار " + p.get("version", "") if p.get("version") else ""))
            if h != tgt:
                kb.append([_b("اجعله الحالي: " + _alias(h), "pc:" + h), _b("سؤال واحد له", "one:" + h)])
        warn = "" if MAIL["repo"] else "\n\nتنبيه: هذا الجهاز لا يصل إلى المستودع الخاص، فلا يرى الجهاز الآخر. سجّل الدخول عليه مرة: gh auth login ثم «زامن الآن» في زاجل."
        if len(rows) < 2 and not warn:
            warn = "\n\nلا يظهر الجهاز الآخر بعد: حدّثه إلى آخر إصدار واضغط فيه «زامن الآن» مرة."
        return "الأجهزة (▶ هو الذي يجيبك الآن):\n" + "\n".join(rows) + warn + "\n\nلتسأل جهازًا لمرة واحدة اكتب أول اسمه ثم طلبك، مثل: «" + " ".join(sorted({h.split('-')[0] for h in _presence()})[:1]) + " ما المساحة الحرة؟». أو اضغط زرًّا ليصير هو الحالي.", kb + [[_b("تحديث", "scr:pc")]] + back
    return None


def _find(chat, q):
    import agent_server
    if not q.strip():
        _show(chat, "findhelp")
        return
    note = send("أبحث عن «" + q + "» في كل الأجهزة…", chat)
    r = agent_server.call("search_all", {"q": q}, agent="telegram")
    res = r.get("result") or {}
    ents = res.get("entries") or []
    if not ents:
        edit(chat, note, "لا نتائج لـ «" + q + "»." + (" " + r["error"] if r.get("error") else ""))
        return
    kb = []
    for e in ents[:8]:
        k = uuid_short()
        FIND[k] = (e.get("place") or e.get("sid"), e.get("path"))
        kb.append([_b(("📁 " if e.get("is_dir") else "📄 ") + (e.get("name") or "")[:40] + " · " + str(e.get("label") or e.get("sid") or "")[:14], "snd:" + k)])
    edit(chat, note, f"وجدت {res.get('count', len(ents))} نتيجة لـ «{q}». اضغط ملفًا ليصلك هنا:", kb)


def send_file(path, caption=""):
    """يرسل ملفًا إلى محادثة المستخدم المقترنة (صورة تُعرض صورة، وغيرها مستندًا)."""
    from pathlib import Path
    p = Path(path)
    c = _cfg()
    if not _tok() or not c["chat_id"]:
        raise ValueError("تيليجرام غير مقترن على هذا الجهاز.")
    if p.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("الملف أكبر من ٥٠ ميغابايت، وهو حد تيليجرام للبوتات.")
    photo = p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and p.stat().st_size < 10 * 1024 * 1024
    field, method = ("photo", "sendPhoto") if photo else ("document", "sendDocument")
    bnd = "zajel" + uuid_short() * 3
    name = p.name.replace('"', "")
    body = b""
    for k, v in (("chat_id", str(c["chat_id"])), ("caption", str(caption)[:900])):
        body += f'--{bnd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += f'--{bnd}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + p.read_bytes() + f"\r\n--{bnd}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{_tok()}/{method}", data=body, headers={"Content-Type": "multipart/form-data; boundary=" + bnd})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            ok = json.loads(r.read().decode()).get("ok")
    except (urllib.error.URLError, OSError) as exc:
        raise ValueError("تعذّر الإرسال إلى تيليجرام: " + str(exc)[:80])
    return {"sent": bool(ok), "name": p.name, "size": p.stat().st_size}


# ================= الكمبيوتران: صندوق مشترك في المستودع الخاص =================
# الجهاز «البوابة» يستلم من تيليجرام؛ إن كان الجهاز المختار غيره يضع الرسالة في صندوقه داخل المستودع الخاص،
# والجهاز الآخر يمرّ على صندوقه كل ١٠ ثوانٍ وينفّذ ويردّ إليك مباشرة (الإرسال إلى تيليجرام مسموح لأكثر من جهاز).
MAIL = {"repo": None, "presence": {}, "target": "", "last_presence": 0, "last_pull": 0}
MAIL_LOCK = threading.Lock()
_mail_thread = None


def _git(*args, timeout=60):
    import app_update
    return app_update._run(["git", "-c", "user.name=zajel", "-c", "user.email=zajel@localhost", *args], cwd=MAIL["repo"], timeout=timeout)


def _mail_repo():
    if MAIL["repo"]:
        return MAIL["repo"]
    try:
        import app_update
        MAIL["repo"] = app_update.ensure_repo()
    except Exception:
        MAIL["repo"] = None
    return MAIL["repo"]


def _push(msg):
    _git("add", "-A")
    if not _git("status", "--porcelain").stdout.strip():
        return True
    _git("commit", "-q", "-m", msg)
    for _ in range(3):
        if _git("push", "-q", timeout=90).returncode == 0:
            return True
        _git("pull", "--rebase", "-q", timeout=60)
    return False


def _pull():
    _git("pull", "--rebase", "-q", timeout=60)
    MAIL["last_pull"] = time.time()
    d = MAIL["repo"] / "tg"
    pres = {}
    for f in (d / "presence").glob("*.json") if (d / "presence").exists() else []:
        try:
            pres[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            pass
    MAIL["presence"] = pres
    try:
        MAIL["target"] = json.loads((d / "target.json").read_text(encoding="utf-8")).get("host", "")
    except (OSError, ValueError):
        pass
    try:
        cid = json.loads((d / "chat.json").read_text(encoding="utf-8")).get("chat_id", 0)
        if cid and not _cfg()["chat_id"] and _tok():
            _save_cfg({"chat_id": cid})        # اقترن جهاز آخر بمحادثتك: هذا الجهاز يتبعه تلقائيًا
    except (OSError, ValueError):
        pass


def _presence():
    p = dict(MAIL["presence"])
    p[HOST] = {"ts": time.time(), "version": _version()}
    return p


def _version():
    try:
        import app_update
        return app_update.local_version()
    except Exception:
        return ""


def _target():
    t = MAIL["target"] or HOST
    return t if t in _presence() else HOST


def _set_target(host):
    with MAIL_LOCK:
        if not _mail_repo():
            raise ValueError("التبديل بين الأجهزة يحتاج المزامنة الخاصة: اضغط «زامن الآن» مرة في إعدادات زاجل.")
        _pull()
        d = MAIL["repo"] / "tg"
        d.mkdir(exist_ok=True)
        (d / "target.json").write_text(json.dumps({"host": host, "t": time.time()}), encoding="utf-8")
        MAIL["target"] = host
        _push("تيليجرام: الجهاز الحالي " + host)


def _forward(u, host):
    with MAIL_LOCK:
        d = MAIL["repo"] / "tg" / "inbox" / host
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{u['update_id']}.json").write_text(json.dumps(u, ensure_ascii=False), encoding="utf-8")
        ok = _push("تيليجرام: طلب إلى " + host)
    if not ok:
        send("تعذّر إيصال الطلب إلى " + host + ".")
        return
    threading.Thread(target=_pickup_watch, args=(u, host), daemon=True).start()


def _pickup_watch(u, host):
    """إن لم يستلم الجهاز المختار طلبك خلال ٩٠ ثانية (نائم أو مغلق)، يُنفَّذ هنا وتُبلَّغ."""
    _stop.wait(90)
    with MAIL_LOCK:
        _pull()
        f = MAIL["repo"] / "tg" / "inbox" / host / f"{u['update_id']}.json"
        if not f.exists():
            return
        f.unlink()
        _push("تيليجرام: استرجاع طلب لم يُستلم من " + host)
    send(f"لم يستلم {host} طلبك خلال دقيقة ونصف (قد يكون نائمًا أو مغلقًا)، فنفّذته هنا على {HOST}.")
    _dispatch(u)


def _route(u):
    """يقرّر أين يُنفَّذ التحديث: هنا أو في صندوق الجهاز المختار."""
    m = u.get("message") or {}
    cb = u.get("callback_query") or {}
    text = (m.get("text") or "").strip()
    local = text.startswith("/start") or text.startswith("/pc") or text == "الأجهزة" or (cb.get("data") or "").startswith(("pc:", "scr:pc", "one:"))
    chat = (m.get("chat") or (cb.get("message") or {}).get("chat") or {}).get("id")
    hb = _host_by_button(text) if text else ""
    if hb and _authorized(chat):                # زر جهاز في لوحة المفاتيح: يصير هو الحالي فورًا
        try:
            _set_target(hb)
            send(f"صار الجهاز الحالي: {hb}. كل رسائلك تذهب إليه الآن.", chat, reply_kb=_kb())
        except ValueError as e:
            send(str(e), chat)
        return
    tgt = _target()
    if ONESHOT["host"] and (text or m.get("voice") or m.get("audio")) and not text.startswith("/") and not local:
        tgt, ONESHOT["host"] = ONESHOT["host"], ""
    for h in sorted(_presence(), key=len, reverse=True):     # «اسم الجهاز (أو أوله مثل iMac) ثم الطلب» لمرة واحدة
        for alias in (h, h.split("-")[0]):
            if alias and text.lower().startswith(alias.lower() + " "):
                m["text"] = text[len(alias):].strip(" :،,") or "/home"
                tgt, local = h, False
                break
        else:
            continue
        break
    if local or tgt == HOST or not _mail_repo():
        _dispatch(u)
        return
    age = time.time() - _presence().get(tgt, {}).get("ts", 0)
    if age > GW_FRESH:
        send(f"الجهاز {tgt} غير متصل منذ {int(age // 60)} دقيقة. نفّذتُ طلبك هنا على {HOST}.", m.get("chat", {}).get("id"))
        _dispatch(u)
        return
    _forward(u, tgt)


def _mail_tick():
    """دورة واحدة: سحب، قراءة صندوق هذا الجهاز، تسجيل الحضور، رفع. تعيد الطلبات الواردة."""
    items = []
    with MAIL_LOCK:
        if time.time() - MAIL["last_pull"] > (30 if STATE["gateway"] else 10):
            _pull()
        box = MAIL["repo"] / "tg" / "inbox" / HOST
        todo = sorted(box.glob("*.json")) if box.exists() else []
        for f in todo:
            try:
                items.append(json.loads(f.read_text(encoding="utf-8")))
            except ValueError:
                pass
            f.unlink()
        if time.time() - MAIL["last_presence"] > 180 or todo or STATE.pop("gw_changed", False):
            pd = MAIL["repo"] / "tg" / "presence"
            pd.mkdir(parents=True, exist_ok=True)
            (pd / f"{HOST}.json").write_text(json.dumps({"ts": time.time(), "version": _version(), "gateway": STATE["gateway"], "laptop": bool(LAPTOP if LAPTOP is not None else _is_laptop())}), encoding="utf-8")
            if _cfg()["chat_id"]:
                (MAIL["repo"] / "tg" / "chat.json").write_text(json.dumps({"chat_id": _cfg()["chat_id"]}), encoding="utf-8")
            MAIL["last_presence"] = time.time()
        if todo or _git("status", "--porcelain").stdout.strip():
            _push("تيليجرام: " + HOST)
    return items


def _mail_loop():
    while not _stop.is_set():
        try:
            if _cfg()["enabled"] and _mail_repo():
                for u in _mail_tick():
                    threading.Thread(target=_dispatch, args=(u,), daemon=True).start()
        except Exception as exc:
            STATE["mail_error"] = str(exc)[:120]
        _stop.wait(5)
