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
DEFAULTS = {"enabled": False, "chat_id": 0, "notify_error": True, "notify_long": True, "notify_update": True, "long_secs": 60, "offset": 0, "conv": "telegram", "approve_red": False}


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
            "pair_code": STATE["pair_code"] if live else "", "notify_error": c["notify_error"], "notify_long": c["notify_long"], "notify_update": c["notify_update"], "approve_red": c["approve_red"]}}


def configure(b):
    d = {k: bool(b[k]) for k in ("notify_error", "notify_long", "notify_update", "approve_red") if k in b}
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
    text = str(text) or "…"
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


# ================= الاستماع والتوجيه =================
MAIN_KB = [["الرئيسية", "الوكلاء", "الذاكرة"], ["الأوامر", "المهام", "المساعدة"]]
BTN = {"الرئيسية": "home", "الوكلاء": "agents", "الذاكرة": "mem", "الأوامر": "cmds", "المهام": "jobs", "المساعدة": "help"}
COMMANDS = [("home", "الرئيسية"), ("agents", "حال الوكلاء"), ("mem", "الذاكرة"), ("cmds", "الأوامر الجاهزة"), ("jobs", "المهام والموافقات"),
            ("new", "محادثة جديدة مع المساعد"), ("chats", "محادثات زاجل السابقة"), ("settings", "الإعدادات"), ("help", "المساعدة")]
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
        try:
            c = _cfg()
            ups = _api(tok, "getUpdates", {"offset": c["offset"], "timeout": 25, "allowed_updates": ["message", "callback_query"]}, timeout=40)
            STATE["gateway"], STATE["error"] = True, ""
            for u in ups:
                _save_cfg({"offset": u["update_id"] + 1})
                threading.Thread(target=_dispatch, args=(u,), daemon=True).start()      # كل طلب في خيط: لا يحجب الاستماع
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
            send("تم الربط بزاجل على " + socket.gethostname().split(".")[0] + ".\nاكتب لي أو سجّل رسالة صوتية كما تكلّم المساعد في زاجل تمامًا. الأزرار أدناه للتنقّل السريع.", chat, reply_kb=MAIN_KB)
        return
    if chat != c["chat_id"]:
        return
    word = text.split()[0] if text.split() else ""
    name = BTN.get(text) or (word[1:].split("@")[0] if word.startswith("/") else "")
    if name in ("home", "agents", "mem", "cmds", "jobs", "help", "chats", "settings"):
        _show(chat, name)
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
    else:
        _ask(chat, re.sub(r"^/ask\s*", "", text))


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


def _check_pending(chat, jid):
    import agent_server
    for p in agent_server.pending_list():
        if p.get("job") != jid or p["id"] in SEEN_PENDING:
            continue
        SEEN_PENDING.add(p["id"])
        if not _cfg()["approve_red"]:
            send("طلب يحتاج موافقتك: " + _desc_pending(p) + "\n\nاعتماد العمليات الحمراء من هنا مغلق. وافق عليها داخل زاجل، أو افتحه من إعدادات تيليجرام.", chat)
        elif p.get("needs_word"):
            send("طلب حساس: " + _desc_pending(p) + "\n\nيتطلب كتابة كلمة تأكيد، وهذا لا يتم من تيليجرام. وافق عليه داخل زاجل.", chat)
        else:
            send("طلب يحتاج موافقتك\n" + _desc_pending(p) + "\n\nينتهي خلال %d دقيقة." % max(1, p["expires_in"] // 60), chat,
                 kb=[[{"text": "راجعتُ الأرقام", "callback_data": "ok1:" + p["id"]}], [{"text": "ارفض", "callback_data": "no:" + p["id"]}]])


def _on_callback(chat, mid, data):
    import agent_server
    kind, _, rest = data.partition(":")
    if kind == "ans":
        txt = OPTS.get(rest)
        if txt:
            edit(chat, mid, "اخترت: " + txt, [])
            _ask(chat, txt)
    elif kind == "no":
        try:
            agent_server.deny(rest); edit(chat, mid, "رفضتَ الطلب.", [])
        except ValueError as e:
            edit(chat, mid, str(e), [])
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
            edit(chat, mid, "تم تنفيذ الطلب.", [])
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
    elif kind == "tg" and rest in ("notify_error", "notify_long", "notify_update"):     # اعتماد الحمراء يُفتح من زاجل وحده، لا من القناة نفسها
        _save_cfg({rest: not _cfg()[rest]}); _show(chat, "settings", mid)


def _show(chat, name, mid=None):
    text, kb = _screen(name)
    if mid:
        edit(chat, mid, text, kb)
    else:
        send(text, chat, kb=kb, reply_kb=MAIN_KB if name in ("help", "home") else None)


def _b(t, d):
    return {"text": t, "callback_data": d}


def _screen(name):
    import agent_runner, agent_metrics, agent_server, assistant_store
    back = [[_b("رجوع", "scr:home")]]
    if name == "home":
        ag = agent_metrics.stats(24, {a["id"]: a["installed"] for a in agent_runner.agents()}, [a["id"] for a in agent_runner.agents()])["agents"]
        up = sum(1 for a in ag if a["status"] in ("ok", "slow"))
        pend = len(agent_server.pending_list())
        return (f"زاجل على {socket.gethostname().split('.')[0]}\nالوكلاء العاملون: {up} من {len(ag)}\nطلبات تنتظر موافقتك: {pend}\nالمحادثة الحالية: {_cfg()['conv']}",
                [[_b("الوكلاء", "scr:agents"), _b("الذاكرة", "scr:mem")], [_b("المهام", "scr:jobs"), _b("الأوامر", "scr:cmds")], [_b("المحادثات", "scr:chats"), _b("الإعدادات", "scr:settings")]])
    if name == "agents":
        names = {a["id"]: a["name"] for a in agent_runner.agents()}
        s = agent_metrics.stats(24, {a["id"]: a["installed"] for a in agent_runner.agents()}, list(names))
        lab = {"ok": "يعمل", "slow": "بطيء", "down": "متوقف", "idle": "لم يُجرَّب"}
        lines = [f"{names.get(a['id'], a['id'])}: {lab[a['status']]}" + (f" — وسيط {a['median']} ثانية" if a["median"] else "") + (f" ({a['why']})" if a["status"] == "down" else "") for a in s["agents"]]
        kb = [[_b(names.get(a["id"], a["id"]), "ping:" + a["id"])] for a in s["agents"]]
        return "حال الوكلاء (اضغط اسمًا لفحصه):\n" + "\n".join(lines), kb + back
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
            ] + back
    return ("أنا نفس المساعد الذي في زاجل. اكتب لي بكلامك العادي، أو سجّل رسالة صوتية، وسأفهم وأنفّذ.\n"
            "أمثلة: «ما حال الوكلاء؟» · «انسخ صور هاتفي إلى القرص الأزرق» · «ابحث عن ملف العقد».\n"
            "العمليات الحمراء (نسخ ونقل وحذف) تصلك ببطاقة موافقة. الأزرار أسفل الشاشة للتنقل السريع."), None
