"""حساب المستخدم الشخصي في تيليجرام (غير البوت) — المرحلة ٢ من «زاجل في تيليجرام».
- الاتصال بمكتبة telethon. تسجيل الدخول أول مرة يفعله المستخدم بنفسه من شاشة في زاجل: رقما التطبيق، ثم الرمز الذي يصل إلى هاتفه.
- الأسرار (رقما التطبيق، وجلسة الحساب) تُحفظ في سلسلة مفاتيح الماك فقط، ولا تُكتب في أي ملف ولا في السجلات.
- حماية الحساب من الحظر: طلبات بإيقاع بشري (فاصل متغيّر بين الطلبات) واحترام أوامر الانتظار FloodWait التي يرسلها تيليجرام.
- ما يقرؤه المنطق هنا: البحث، التحميل، الوارد، المراقب، نسخ المحادثات. الشاشات في البوت في telegram_account_bot."""
import asyncio
import html
import json
import random
import re
import subprocess
import threading
import time
from pathlib import Path

DATA = None
LOCK = threading.RLock()
SERVICE_API = "zajel-telegram-account-api"
SERVICE_SESSION = "zajel-telegram-account-session"
STATE = {"login": "none", "error": "", "me": "", "flood_until": 0.0, "phone": ""}
MAX_DOWNLOAD = 2 * 1024 ** 3          # ٢ غيغابايت
MAX_BACKUP_MEDIA = 50 * 1024 * 1024
LISTS = {"fiqh": "كتب شرعية", "lessons": "دروس صوتية", "docs": "وثائقيات", "mine": "قنواتي"}
TYPES = {"all": "الكل", "book": "كتب", "video": "فيديو", "audio": "صوت", "link": "روابط"}
TYPEDIR = {"book": "كتب", "video": "فيديو", "audio": "صوت", "photo": "صور", "link": "روابط", "file": "ملفات"}
BOOK_EXT = {"pdf", "epub", "mobi", "azw3", "azw", "djvu", "doc", "docx", "txt", "rtf", "chm", "zip", "rar"}
DEFAULTS = {"libs": [], "lists": {}, "watch": [], "backups": [], "inbox": {"last_id": 0, "items": []}, "hits": [], "backup_hour": 3, "backup_day": "", "dismissed": []}


def init(data_dir):
    global DATA
    DATA = Path(data_dir)
    if linked():
        threading.Thread(target=_start_background, daemon=True).start()


# ================= الأسرار =================
def _secret_get(service):
    r = subprocess.run(["security", "find-generic-password", "-a", "zajel", "-s", service, "-w"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return r.stdout.strip() if r.returncode == 0 else ""


def _secret_set(service, value):
    subprocess.run(["security", "add-generic-password", "-a", "zajel", "-s", service, "-w", value, "-U"], capture_output=True, stdin=subprocess.DEVNULL, check=True)


def _secret_del(service):
    subprocess.run(["security", "delete-generic-password", "-a", "zajel", "-s", service], capture_output=True, stdin=subprocess.DEVNULL)


def linked():
    try:
        return bool(_secret_get(SERVICE_SESSION)) and bool(_secret_get(SERVICE_API))
    except Exception:
        return False


# ================= الإعدادات =================
def _cfg():
    try:
        d = json.loads((DATA / "telegram_account.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        d = {}
    return {**json.loads(json.dumps(DEFAULTS)), **d}


def _save(patch):
    with LOCK:
        c = {**_cfg(), **patch}
        (DATA / "telegram_account.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        return c


# ================= الإيقاع البشري وأوامر الانتظار =================
class Pacer:
    """فاصل متغيّر بين الطلبات (لا إيقاع آلي ثابت)، وانتظار ما يأمر به تيليجرام."""

    def __init__(self, base=1.0, jitter=1.2, sleep=time.sleep, clock=time.time):
        self.base, self.jitter, self.sleep, self.clock = base, jitter, sleep, clock
        self.last = 0.0
        self.blocked_until = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = self.clock()
            gap = self.base + random.uniform(0, self.jitter)
            due = max(self.last + gap, self.blocked_until)
            if due > now:
                self.sleep(due - now)
            self.last = self.clock()

    def flood(self, seconds):
        """تيليجرام أمر بالانتظار: لا طلب قبل انقضائه (مع هامش بشري صغير)."""
        self.blocked_until = self.clock() + seconds + random.uniform(1, 3)
        STATE["flood_until"] = self.blocked_until


PACER = Pacer()
MAX_AUTO_WAIT = 120          # أمر انتظار أطول من دقيقتين لا ننتظره بصمت: نُبلغ المستخدم


def flood_message():
    left = int(STATE["flood_until"] - time.time())
    return f"تيليجرام يطلب الانتظار {left} ثانية لحماية الحساب. سيُستأنف العمل تلقائيًا." if left > 0 else ""


# ================= حلقة الأحداث والعميل =================
_loop = None
_loop_thread = None
_client = None
_pending_login = {}


def _ensure_loop():
    global _loop, _loop_thread
    with LOCK:
        if _loop and _loop.is_running():
            return _loop
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
        _loop_thread.start()
        return _loop


def run(coro, timeout=120):
    """ينفّذ مهمة غير متزامنة من أي خيط. يحوّل أوامر الانتظار والأخطاء إلى رسائل عربية."""
    fut = asyncio.run_coroutine_threadsafe(coro, _ensure_loop())
    try:
        return fut.result(timeout)
    except Exception as e:
        raise _friendly(e)


def _friendly(e):
    name = type(e).__name__
    if name in ("FloodWaitError", "SlowModeWaitError"):
        sec = int(getattr(e, "seconds", 60))
        PACER.flood(sec)
        return ValueError(f"تيليجرام يطلب الانتظار {sec} ثانية لحماية الحساب؛ أعد المحاولة بعدها.")
    if name in ("AuthKeyUnregisteredError", "SessionRevokedError", "UserDeactivatedError"):
        STATE["login"] = "none"
        return ValueError("انتهت جلسة حسابك في تيليجرام؛ سجّل الدخول من جديد من زاجل.")
    if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
        return ValueError("انتهت مهلة الطلب إلى تيليجرام.")
    if isinstance(e, ValueError):
        return e
    return ValueError("تعذّر الطلب إلى تيليجرام: " + (str(e) or name)[:120])


def _api_pair():
    v = _secret_get(SERVICE_API)
    i, _, h = v.partition(":")
    if not (i.isdigit() and h):
        raise ValueError("لم تُحفظ رقما التطبيق بعد.")
    return int(i), h


def _make_client(session=""):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    api_id, api_hash = _api_pair()
    return TelegramClient(StringSession(session), api_id, api_hash, flood_sleep_threshold=0, device_model="Zajel", system_version="macOS", app_version="2.16")


async def client():
    """العميل المتصل (يُنشأ مرة واحدة). يرمي ValueError إن لم يكن الحساب مربوطًا."""
    global _client
    if _client is None:
        sess = _secret_get(SERVICE_SESSION)
        if not sess:
            raise ValueError("حسابك في تيليجرام غير مربوط. اربطه من زاجل ← الإعدادات ← تيليجرام.")
        _client = _make_client(sess)
    if not _client.is_connected():
        await _client.connect()
    if not await _client.is_user_authorized():
        STATE["login"] = "none"
        raise ValueError("انتهت جلسة حسابك في تيليجرام؛ سجّل الدخول من جديد.")
    return _client


async def call(coro_factory, *, retry=True):
    """يمرّ بالإيقاع البشري، وعند أمر انتظار قصير ينتظره مرة واحدة ثم يعيد المحاولة."""
    while True:
        await asyncio.get_event_loop().run_in_executor(None, PACER.wait)
        try:
            return await coro_factory()
        except Exception as e:
            if type(e).__name__ in ("FloodWaitError", "SlowModeWaitError") and retry:
                sec = int(getattr(e, "seconds", 60))
                PACER.flood(sec)
                if sec > MAX_AUTO_WAIT:
                    raise
                retry = False
                continue
            raise


# ================= تسجيل الدخول (يفعله المستخدم بنفسه) =================
def login_status():
    return {"linked": linked(), "step": STATE["login"], "me": STATE["me"], "error": STATE["error"], "flood": flood_message()}


def login_start(api_id, api_hash, phone):
    """الخطوة ١: رقما التطبيق من my.telegram.org ورقم الهاتف ← يصل الرمز إلى هاتف المستخدم."""
    api_id, api_hash, phone = str(api_id).strip(), str(api_hash).strip(), str(phone).strip()
    if not api_id.isdigit() or not re.fullmatch(r"[0-9a-f]{32}", api_hash):
        raise ValueError("رقما التطبيق غير صحيحين: الأول أرقام، والثاني ٣٢ حرفًا وأرقامًا.")
    if not re.fullmatch(r"\+\d{7,15}", phone):
        raise ValueError("اكتب رقم الهاتف بصيغة دولية، مثل +9665xxxxxxxx.")
    _secret_set(SERVICE_API, f"{api_id}:{api_hash}")

    async def go():
        c = _make_client("")
        await c.connect()
        sent = await c.send_code_request(phone)
        _pending_login.update(client=c, phone=phone, hash=sent.phone_code_hash)

    run(go(), 60)
    STATE.update(login="code", error="", phone=phone)
    return login_status()


def login_code(code):
    """الخطوة ٢: الرمز الذي وصل إلى هاتفه."""
    c = _pending_login.get("client")
    if not c:
        raise ValueError("ابدأ تسجيل الدخول من الأول.")

    async def go():
        try:
            await c.sign_in(_pending_login["phone"], str(code).strip(), phone_code_hash=_pending_login["hash"])
        except Exception as e:
            if type(e).__name__ == "SessionPasswordNeededError":
                return "password"
            if type(e).__name__ in ("PhoneCodeInvalidError", "PhoneCodeExpiredError"):
                raise ValueError("الرمز غير صحيح أو انتهت صلاحيته.")
            raise
        return "ready"

    step = run(go(), 60)
    if step == "password":
        STATE["login"] = "password"
    else:
        _finish_login()
    return login_status()


def login_password(pw):
    """الخطوة ٣ (إن كان حسابه محميًا بكلمة مرور ثنائية)."""
    c = _pending_login.get("client")
    if not c:
        raise ValueError("ابدأ تسجيل الدخول من الأول.")

    async def go():
        try:
            await c.sign_in(password=pw)
        except Exception as e:
            if type(e).__name__ == "PasswordHashInvalidError":
                raise ValueError("كلمة المرور غير صحيحة.")
            raise

    run(go(), 60)
    _finish_login()
    return login_status()


def _finish_login():
    global _client
    c = _pending_login.pop("client")
    me = run(c.get_me(), 30)
    _secret_set(SERVICE_SESSION, c.session.save())
    _client = c
    _pending_login.clear()
    STATE.update(login="ready", me=getattr(me, "first_name", "") or "", error="")
    threading.Thread(target=_start_background, daemon=True).start()


def logout():
    global _client
    try:
        if _client:
            run(_client.log_out(), 20)
    except Exception:
        pass
    _client = None
    _secret_del(SERVICE_SESSION)
    _secret_del(SERVICE_API)
    STATE.update(login="none", me="", error="")
    return login_status()


# ================= منطق نقي: التصنيف والتطبيع =================
def norm(s):
    s = re.sub(r"[ً-ْـ]", "", str(s or ""))
    return s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي").strip().lower()


def all_lists():
    d = dict(LISTS)
    d.update(_cfg().get("lists") or {})
    return d


def list_name(k):
    return all_lists().get(k, k)


TMP_LIBS = {}     # قنوات مكتشفة لم تُحفظ بعد: لتبقى أزرار التنزيل تعمل على نتائجها


def parse_scoped(q):
    """«أفلام: اسم الفيلم» ← ("أفلام", "اسم الفيلم"). يعيد None إن لم تكن بهذه الصيغة."""
    q = str(q or "").strip()
    m = re.match(r"^([^:：/\n]{2,24}?)\s*[:：]\s*(\S.*)$", q)
    if not m or "http" in m.group(1).lower():
        return None
    return m.group(1).strip(), m.group(2).strip()


def find_list(topic):
    t = fz_norm(topic)
    for k, name in all_lists().items():
        n = fz_norm(name)
        if t == n or t == k or (len(t) >= 3 and t in n.split()):
            return k
    return None


def classify(msg):
    """نوع الرسالة: book/video/audio/photo/link/file/text. يعمل على أي كائن فيه صفات الرسالة (للاختبار بلا شبكة)."""
    f = getattr(msg, "file", None)
    ext = (getattr(f, "ext", "") or "").lower().lstrip(".")
    mime = (getattr(f, "mime_type", "") or "").lower()
    if getattr(msg, "voice", None) or getattr(msg, "audio", None) or mime.startswith("audio/") or ext in ("mp3", "m4a", "ogg", "opus", "wav", "flac", "aac"):
        return "audio"
    if getattr(msg, "video", None) or mime.startswith("video/") or ext in ("mp4", "mkv", "mov", "avi", "webm"):
        return "video"
    if getattr(msg, "photo", None) and not f or mime.startswith("image/"):
        return "photo"
    if f and (ext in BOOK_EXT or mime in ("application/pdf", "application/epub+zip")):
        return "book"
    if f:
        return "file"
    text = getattr(msg, "message", "") or getattr(msg, "text", "") or ""
    if getattr(msg, "web_preview", None) or re.search(r"https?://\S+", text):
        return "link"
    return "text"


def title_of(msg):
    f = getattr(msg, "file", None)
    name = getattr(f, "name", "") if f else ""
    text = (getattr(msg, "message", "") or getattr(msg, "text", "") or "").strip()
    first = text.splitlines()[0] if text else ""
    return (name or first or "بلا عنوان")[:140]


def human_size(n):
    n = float(n or 0)
    if n <= 0:
        return "—"
    for u, d in (("غ.ب", 1024 ** 3), ("م.ب", 1024 ** 2), ("ك.ب", 1024)):
        if n >= d:
            return f"{n / d:.1f} {u}"
    return f"{int(n)} بايت"


def meta_of(msg, t):
    f = getattr(msg, "file", None)
    ext = (getattr(f, "ext", "") or "").lstrip(".").upper() if f else ""
    dur = getattr(f, "duration", None) if f else None
    bits = [{"book": ext or "كتاب", "video": "فيديو", "audio": "صوت", "link": "رابط"}.get(t, ext or "ملف")]
    if dur:
        bits.append(f"{int(dur) // 60} دقيقة")
    return " · ".join(bits)


def match_watch(text, words):
    """الكلمات المراقبة التي تظهر في النص (تطبيع عربي، وكل كلمات العبارة يجب أن تظهر)."""
    t = norm(text)
    hits = []
    for w in words:
        if not w.get("on", True):
            continue
        parts = norm(w.get("word", "")).split()
        if parts and all(p in t for p in parts):
            hits.append(w)
    return hits


def suggest_place(t, is_voice=False):
    """مكان مقترح للعنصر الوارد في «الرسائل المحفوظة»."""
    if t == "audio" and is_voice:
        return "تفريغ"
    return {"book": "كتب", "video": "فيديو", "audio": "صوت", "photo": "صور", "link": "روابط"}.get(t, "ملفات")


def safe_name(name, fallback="ملف"):
    n = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", str(name or "")).strip(" .")
    return (n or fallback)[:120]


def unique_path(folder, name):
    p = Path(folder) / safe_name(name)
    n = 1
    while p.exists():
        p = Path(folder) / f"{p.stem.rsplit(' (', 1)[0]} ({n}){p.suffix}"
        n += 1
    return p


def root_dir():
    return Path.home() / "زاجل" / "تيليجرام"


def link_of(lib, mid):
    u = lib.get("username")
    return f"https://t.me/{u}/{mid}" if u else (f"https://t.me/c/{lib.get('id')}/{mid}" if lib.get("id") else "")


# ================= المكتبات =================
def libs():
    return _cfg()["libs"]


def lib_set(lid, on):
    c = _cfg()
    for l in c["libs"]:
        if str(l["id"]) == str(lid):
            l["on"] = bool(on)
    _save({"libs": c["libs"]})
    return c["libs"]


def parse_channel_ref(ref):
    ref = str(ref or "").strip()
    m = re.match(r"^(?:https?://)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]{4,})/?(?:\d+)?$", ref) or re.match(r"^@?([A-Za-z][A-Za-z0-9_]{3,})$", ref)
    if not m:
        raise ValueError("اكتب رابط القناة (t.me/…) أو اسمها المبدوء بـ @.")
    return m.group(1)


def lib_add(ref, lst="fiqh"):
    """يضيف قناة عامة (ولو لم يشترك فيها) إلى قائمة."""
    if lst not in all_lists():
        raise ValueError("قائمة غير معروفة.")
    uname = parse_channel_ref(ref)

    async def go():
        c = await client()
        return await call(lambda: c.get_entity(uname))

    ent = run(go(), 40)
    entry = {"id": ent.id, "name": getattr(ent, "title", None) or uname, "username": getattr(ent, "username", None) or uname, "list": lst, "on": True, "public": True}
    return _lib_upsert(entry)


def _lib_upsert(entry):
    c = _cfg()
    if any(l["id"] == entry["id"] and l["list"] == entry["list"] for l in c["libs"]):
        return c["libs"]
    c["libs"].append(entry)
    _save({"libs": c["libs"]})
    return c["libs"]


def libs_sync_mine():
    """يستورد قنواتك ومجموعاتك إلى قائمة «قنواتي» (مطفأة حتى تفعّلها، حتى لا يبحث في كل شيء)."""
    async def go():
        c = await client()
        out = []
        async for d in c.iter_dialogs(limit=300):
            if d.is_channel or d.is_group:
                out.append({"id": d.entity.id, "name": d.name, "username": getattr(d.entity, "username", None), "list": "mine", "on": False, "public": False})
                await asyncio.get_event_loop().run_in_executor(None, PACER.wait) if len(out) % 50 == 0 else None
        return out

    for e in run(go(), 120):
        _lib_upsert(e)
    return _cfg()["libs"]


def suggestions(q):
    """قنوات عامة مقترحة من البحث العام في تيليجرام، لم تُضَف بعد."""
    async def go():
        from telethon import functions
        c = await client()
        out, seen = [], set()
        # بحث تيليجرام العام لا يعيد شيئًا غالبًا لكلمة واحدة قصيرة، فنجرّب صيغًا قريبة حتى تتوفر نتائج
        for qq in (q, "كتب " + q, q + " قناة"):
            r = await call(lambda qq=qq: c(functions.contacts.SearchRequest(q=qq, limit=12)))
            for ch in r.chats:
                if ch.id in seen or not (getattr(ch, "broadcast", False) or getattr(ch, "megagroup", False)):
                    continue
                seen.add(ch.id)
                out.append({"id": ch.id, "name": ch.title, "username": getattr(ch, "username", None), "who": f"{getattr(ch, 'participants_count', 0) or 0} مشترك"})
            if len(out) >= 6:
                break
        return out

    have = {l["id"] for l in libs()} | set(_cfg()["dismissed"])
    return [s for s in run(go(), 90) if s["id"] not in have and s["username"]]


# ================= البحث التقريبي =================
STOP = {"de", "la", "el", "los", "las", "of", "the", "and", "al", "في", "من", "على", "عن", "ال", "و", "pdf", "mp3", "mp4"}


def fz_norm(s):
    """تطبيع للمقارنة التقريبية: يزيل التشكيل والحركات اللاتينية (é→e) ويوحّد الهمزات والتاء المربوطة وحالة الأحرف."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return norm(s)


def fuzzy_terms(q):
    """الكلمات المهمة في الاستعلام (٣ أحرف فأكثر وليست أدوات ربط)، الأطول أولًا."""
    ws = [w for w in re.findall(r"\w+", fz_norm(q)) if len(w) >= 3 and w not in STOP]
    return sorted(dict.fromkeys(ws), key=lambda w: -len(w))


def _word_score(term, words):
    import difflib
    best = 0.0
    for w in words:
        if term == w:
            return 1.0
        if len(term) >= 4 and (term in w or w in term) and min(len(term), len(w)) >= 4:
            best = max(best, 0.9)
        best = max(best, difflib.SequenceMatcher(None, term, w).ratio())
    return best


def fuzzy_score(item, q):
    terms = fuzzy_terms(q)
    if not terms:
        return 1.0
    words = re.findall(r"\w+", fz_norm(str(item.get("title", "")) + " " + str(item.get("meta", ""))))
    scores = [_word_score(t, words) for t in terms]
    return sum(s if s >= 0.75 else 0.0 for s in scores) / len(scores)


def fuzzy_rank(items, q, min_score=0.5):
    """يرتّب النتائج بالتشابه ويستبعد الضعيف جدًا. الاستعلام بلا كلمات مهمة يُبقى كما هو."""
    if not fuzzy_terms(q):
        return items
    scored = [(fuzzy_score(i, q), i) for i in items]
    scored = [x for x in scored if x[0] >= min_score]
    scored.sort(key=lambda x: (-round(x[0], 1), -int(x[1].get("views", 0) or 0)))
    return [i for _, i in scored]


# ================= البحث بالموضوع (دون اشتراك) =================
def discover(topic, n=25, query="", exclude=()):
    """قنوات عامة عن موضوع، الأكبر مشتركين أولًا، وتتقدّمها القنوات التي يطابق اسمُها ما تبحث عنه. لا اشتراك ولا انضمام."""
    topic, query = str(topic or "").strip(), str(query or "").strip()
    skip = set(exclude)

    async def go():
        from telethon import functions
        c = await client()
        out, seen = [], set(skip)
        # بحث تيليجرام العام يعيد قليلًا لكل صيغة (نحو ٧)، فنجرّب صيغًا متنوعة حتى نبلغ العدد المطلوب
        ws = [w for w in re.findall(r"\w+", topic) if len(w) >= 3]
        variants = [(topic, False)] + ([(query, True)] if query else []) + [(topic + x, False) for x in (" قناة", " pdf", " books", " gratis", " descargar", " free", " library")] \
            + [("قنوات " + topic, False)] + [(w, False) for w in ws] + [(t, True) for t in fuzzy_terms(query)[:2]]
        for qq, by_query in variants:
            if len(out) >= n * 2:
                break
            r = await call(lambda qq=qq: c(functions.contacts.SearchRequest(q=qq, limit=20)))
            for ch in r.chats:
                if ch.id in seen or not getattr(ch, "broadcast", False) or not getattr(ch, "username", None):
                    continue
                seen.add(ch.id)
                out.append({"id": ch.id, "name": ch.title, "username": ch.username, "count": getattr(ch, "participants_count", 0) or 0, "q": by_query})
        return out

    res = run(go(), 240)
    res.sort(key=lambda x: (not x["q"], -x["count"]))
    return res[:n]


def search_scoped(topic, query, type_="all", n=25, progress=None, exclude=()):
    """«أفلام: اسم الفيلم»: إن كان «أفلام» قائمة موجودة بحثنا فيها، وإلا اكتشفنا أكبر القنوات العامة عنه وبحثنا فيها دون اشتراك."""
    k = find_list(topic)
    if k:
        chosen = [l for l in pick_libs(k) if l["id"] not in set(exclude)]
        if not chosen:
            raise ValueError(f"قائمة «{list_name(k)}» ليس فيها قنوات مفعّلة.")
    else:
        found = discover(topic, n, query, exclude)
        if not found:
            raise ValueError(f"لم أجد قنوات عامة أخرى عن «{topic}». جرّب نوعًا أو كلمة أخرى.")
        chosen = [{"id": x["id"], "name": x["name"], "username": x["username"], "list": "tmp", "on": True, "count": x["count"]} for x in found]
        for l in chosen:
            TMP_LIBS[l["id"]] = l
    r = search(query, type_=type_, per_lib=15, libs_override=chosen, progress=progress)   # ٢٥ قناة × (عبارة + كلمتان) ≈ حتى ٧٥ طلبًا بفواصل بشرية
    r.update(topic=topic, libs=chosen, discovered=k is None)
    return r


def save_list(topic, chans):
    """يحفظ القنوات المكتشفة في قائمة باسم الموضوع (مفعّلة) لتُستعمل لاحقًا بلا اكتشاف."""
    import hashlib
    key = "t_" + hashlib.md5(topic.encode("utf-8")).hexdigest()[:6]
    c = _cfg()
    lists = dict(c.get("lists") or {})
    lists[key] = topic
    _save({"lists": lists})
    for ch in chans:
        _lib_upsert({"id": ch["id"], "name": ch["name"], "username": ch["username"], "list": key, "on": True})
    return key


# ================= البحث =================
def _filter_for(t):
    from telethon import types as tt
    return {"book": tt.InputMessagesFilterDocument, "video": tt.InputMessagesFilterVideo, "audio": tt.InputMessagesFilterMusic, "link": tt.InputMessagesFilterUrl}.get(t)


def pick_libs(scope="all", all_libs=None):
    ls = [l for l in (all_libs if all_libs is not None else libs()) if l.get("on")]
    return ls if scope == "all" else [l for l in ls if l["list"] == scope]


def to_item(msg, lib):
    t = classify(msg)
    f = getattr(msg, "file", None)
    return {"ref": f"{lib['id']}:{msg.id}", "t": t if t in ("book", "video", "audio", "photo", "link") else "file", "title": title_of(msg), "lib": lib["id"], "lib_name": lib["name"],
            "size": getattr(f, "size", 0) or 0, "size_h": human_size(getattr(f, "size", 0)), "meta": meta_of(msg, t), "date": str(getattr(msg, "date", ""))[:10],
            "link": link_of(lib, msg.id), "views": getattr(msg, "views", 0) or 0}


def search(q, scope="all", type_="all", per_lib=25, libs_override=None, progress=None, expand=True):
    """يبحث في المكتبات المفعّلة. يعيد {items, counts}: counts عدد النتائج لكل نوع قبل التصفية بالنوع."""
    q = str(q or "").strip()
    if not q:
        raise ValueError("اكتب ما تبحث عنه.")
    chosen = libs_override if libs_override is not None else pick_libs(scope)
    if not chosen:
        raise ValueError("لا قوائم مفعّلة للبحث. فعّل قناة من «مكتباتي».")

    async def go():
        c = await client()
        items, seen = [], set()

        async def one(lib, text):
            try:
                ent = await call(lambda: c.get_entity(lib["username"] or lib["id"]))
                flt = _filter_for(type_) if type_ != "all" else None
                kw = {"search": text, "limit": per_lib}
                if flt:
                    kw["filter"] = flt()

                async def grab():
                    return [m async for m in c.iter_messages(ent, **kw)]
                for m in await call(grab):
                    if classify(m) in ("text",):
                        continue
                    it = to_item(m, lib)
                    if it["ref"] not in seen:
                        seen.add(it["ref"])
                        items.append(it)
            except ValueError:
                raise
            except Exception as e:
                if type(e).__name__ in ("FloodWaitError", "SlowModeWaitError"):
                    raise
                # قناة محظورة أو محذوفة: لا نوقف البحث كله

        for n, lib in enumerate(chosen, 1):
            await one(lib, q)
            if progress:
                try:
                    progress(n, len(chosen), lib["name"])
                except Exception:
                    pass
        # تقريبي: إن قلّت النتائج الحرفية نبحث بكل كلمة مهمة على حدة (يصلح مع الأخطاء الإملائية والترتيب المختلف) ثم نرتّب بالتشابه
        if expand and len(items) < 8:
            for t in fuzzy_terms(q)[: (2 if len(chosen) > 8 else 3)]:
                if t == fz_norm(q):
                    continue
                for lib in chosen:
                    await one(lib, t)
        return items

    items = fuzzy_rank(run(go(), 900), q)
    counts = {k: sum(1 for i in items if i["t"] == k) for k in TYPES if k not in ("all",)}
    counts["all"] = len(items)
    if type_ != "all":
        items = [i for i in items if i["t"] == type_]
    return {"items": items, "counts": counts}


# ================= التحميل إلى الماك =================
DLS = {}
DL_LOCK = threading.Lock()


def get_message(ref):
    lid, _, mid = str(ref).partition(":")
    lib = next((l for l in libs() if str(l["id"]) == lid), None) or next((l for k, l in TMP_LIBS.items() if str(k) == lid), None)
    if not lib or not mid.isdigit():
        raise ValueError("عنصر غير معروف.")
    return lib, int(mid)


def download(ref, then="", notify=None):
    """يبدأ تنزيل ملف إلى الماك في خيط. then: transcribe | kindle. يعيد رقم التنزيل."""
    lib, mid = get_message(ref)
    did = "d%d" % int(time.time() * 1000)
    DLS[did] = {"id": did, "ref": ref, "title": "…", "t": "file", "p": 0.0, "state": "starting", "to": "", "error": "", "then": then, "cancel": False}
    threading.Thread(target=_do_download, args=(did, lib, mid, notify), daemon=True).start()
    return did


def _do_download(did, lib, mid, notify):
    d = DLS[did]

    async def go():
        c = await client()
        ent = await call(lambda: c.get_entity(lib["username"] or lib["id"]))
        msg = await call(lambda: c.get_messages(ent, ids=mid))
        if not msg or not getattr(msg, "file", None):
            raise ValueError("لا ملف في هذه الرسالة.")
        size = getattr(msg.file, "size", 0) or 0
        if size > MAX_DOWNLOAD:
            raise ValueError("الملف أكبر من ٢ غيغابايت.")
        t = classify(msg)
        t = t if t in TYPEDIR else "file"
        folder = root_dir() / TYPEDIR[t]
        folder.mkdir(parents=True, exist_ok=True)
        dest = unique_path(folder, getattr(msg.file, "name", None) or f"{lib['name']}-{mid}{getattr(msg.file, 'ext', '') or ''}")
        d.update(title=title_of(msg), t=t, to="زاجل/تيليجرام/" + TYPEDIR[t], state="running")

        def prog(cur, total):
            if d["cancel"]:
                raise ValueError("أُوقف التنزيل.")
            d["p"] = (cur / total * 100) if total else 0

        await call(lambda: c.download_media(msg, file=str(dest), progress_callback=prog))
        return dest

    try:
        dest = run(go(), 3600 * 3)
        d.update(p=100.0, state="done", path=str(dest))
        _after_download(d, dest)
        if notify:
            notify(f"اكتمل التنزيل: «{d['title']}» في {d['to']}.", d)
    except Exception as e:
        d.update(state="error", error=str(e)[:160])
        if notify:
            notify(f"تعذّر التنزيل: {d['error']}", d)


def _after_download(d, dest):
    try:
        if d["then"] == "transcribe":
            import media
            r = media.transcribe(str(dest), lang="ar", model="small", wait_seconds=0)
            d["job"] = (r or {}).get("id") or (r or {}).get("job")
        elif d["then"] == "kindle":
            d["kindle"] = send_to_kindle(dest)
    except Exception as e:
        d["after_error"] = str(e)[:120]


def send_to_kindle(path):
    """يحوّل الكتاب إن لزم ويضعه في كيندل الموصول بالماك (المنطق الموجود في ebook وkindle_src)."""
    import ebook
    import kindle_src
    if not kindle_src.present():
        raise ValueError("كيندل غير موصول بالماك.")
    p = Path(path)
    if ebook.needs_convert(p):
        out = ebook.convert(p, p.parent)
        p = Path(out)
    kindle_src.push(str(p), "/documents")
    return p.name


def dl_list():
    return [{k: v for k, v in d.items() if k != "cancel"} for d in sorted(DLS.values(), key=lambda x: x["id"], reverse=True)]


def dl_cancel(did):
    if did in DLS:
        DLS[did]["cancel"] = True
        if DLS[did]["state"] in ("starting", "running"):
            DLS[did]["state"] = "cancelled"
    return dl_list()


def active_downloads():
    return sum(1 for d in DLS.values() if d["state"] in ("starting", "running"))


# ================= الوارد: «الرسائل المحفوظة» =================
def inbox_poll():
    """يجلب الجديد من الرسائل المحفوظة ويقترح مكان كل عنصر. لا ينقل شيئًا قبل موافقة المستخدم."""
    cfg = _cfg()
    ib = cfg["inbox"]

    async def go():
        c = await client()

        async def grab():
            return [m async for m in c.iter_messages("me", min_id=ib["last_id"], limit=50)]
        return await call(grab)

    new = []
    for m in run(go(), 60):
        t = classify(m)
        if t == "text":
            continue
        new.append({"id": m.id, "t": t, "title": title_of(m), "from": "رسائلك المحفوظة", "to": suggest_place(t, bool(getattr(m, "voice", None))), "state": "new",
                    "voice": bool(getattr(m, "voice", None))})
    if new:
        ib["items"] = (sorted(new, key=lambda x: x["id"], reverse=True) + ib["items"])[:100]
    top = max([ib["last_id"]] + [i["id"] for i in new])
    ib["last_id"] = top
    _save({"inbox": ib})
    return ib["items"]


def inbox_items():
    return _cfg()["inbox"]["items"]


def new_inbox():
    return sum(1 for i in inbox_items() if i["state"] == "new")


def inbox_apply(ids=None):
    """ينفّذ الترتيب الذي وافق عليه المستخدم: ينزّل العنصر إلى مجلد نوعه، والصوت المقترح للتفريغ يُفرَّغ."""
    cfg = _cfg()
    ib = cfg["inbox"]
    done = 0
    for it in ib["items"]:
        if it["state"] != "new" or (ids is not None and it["id"] not in ids):
            continue
        if it["t"] == "link":
            folder = root_dir() / TYPEDIR["link"]
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / "روابط.md", "a", encoding="utf-8") as f:
                f.write(f"- {it['title']}\n")
        else:
            did = download_saved(it["id"], "transcribe" if it["to"] == "تفريغ" else "")
            it["download"] = did
        it["state"] = "done"
        done += 1
    _save({"inbox": ib})
    return done


def download_saved(mid, then=""):
    did = "d%d" % int(time.time() * 1000)
    DLS[did] = {"id": did, "ref": f"me:{mid}", "title": "…", "t": "file", "p": 0.0, "state": "starting", "to": "", "error": "", "then": then, "cancel": False}

    def work():
        d = DLS[did]

        async def go():
            c = await client()
            msg = await call(lambda: c.get_messages("me", ids=mid))
            t = classify(msg)
            t = t if t in TYPEDIR else "file"
            folder = root_dir() / TYPEDIR[t]
            folder.mkdir(parents=True, exist_ok=True)
            dest = unique_path(folder, getattr(msg.file, "name", None) or f"saved-{mid}{getattr(msg.file, 'ext', '') or ''}")
            d.update(title=title_of(msg), t=t, to="زاجل/تيليجرام/" + TYPEDIR[t], state="running")
            await call(lambda: c.download_media(msg, file=str(dest), progress_callback=lambda a, b: d.__setitem__("p", a / b * 100 if b else 0)))
            return dest
        try:
            dest = run(go(), 3600)
            d.update(p=100.0, state="done", path=str(dest))
            _after_download(d, dest)
        except Exception as e:
            d.update(state="error", error=str(e)[:160])
    threading.Thread(target=work, daemon=True).start()
    return did


# ================= المراقب =================
def watch_words():
    return _cfg()["watch"]


def watch_add(word, where="all"):
    word = str(word or "").strip()
    if len(word) < 2:
        raise ValueError("اكتب كلمة من حرفين فأكثر.")
    c = _cfg()
    if any(norm(w["word"]) == norm(word) for w in c["watch"]):
        return c["watch"]
    c["watch"].insert(0, {"id": "w%d" % int(time.time() * 1000), "word": word, "where": where, "on": True, "hits": 0})
    _save({"watch": c["watch"]})
    return c["watch"]


def watch_toggle(wid):
    c = _cfg()
    for w in c["watch"]:
        if w["id"] == wid:
            w["on"] = not w["on"]
    _save({"watch": c["watch"]})
    return c["watch"]


def watch_remove(wid):
    c = _cfg()
    _save({"watch": [w for w in c["watch"] if w["id"] != wid]})
    return _cfg()["watch"]


def hits():
    return _cfg()["hits"]


HIT_NOTIFY = None          # تُركَّب من البوت: دالة (نص، أزرار) ← ترسل تنبيهًا


def on_new_message(lib, msg):
    """يُستدعى لكل رسالة جديدة في المكتبات المراقبة؛ يسجّل ويُنبّه بلا تكرار."""
    text = (getattr(msg, "message", "") or getattr(msg, "text", "") or "") + " " + title_of(msg)
    found = match_watch(text, watch_words())
    if not found:
        return []
    c = _cfg()
    seen = {(h["w"], h.get("ref")) for h in c["hits"]}
    out = []
    for w in found:
        ref = f"{lib['id']}:{msg.id}"
        if (w["word"], ref) in seen:
            continue
        hit = {"w": w["word"], "ch": lib["name"], "text": title_of(msg)[:200], "when": time.strftime("%Y-%m-%d %H:%M"), "ref": ref, "link": link_of(lib, msg.id)}
        c["hits"].insert(0, hit)
        for x in c["watch"]:
            if x["id"] == w["id"]:
                x["hits"] = x.get("hits", 0) + 1
        out.append(hit)
    c["hits"] = c["hits"][:60]
    _save({"hits": c["hits"], "watch": c["watch"]})
    if HIT_NOTIFY:
        for h in out:
            try:
                HIT_NOTIFY(h)
            except Exception:
                pass
    return out


# ================= نسخ المحادثات =================
def backups():
    return _cfg()["backups"]


def backup_candidates():
    async def go():
        c = await client()
        out = []
        async for d in c.iter_dialogs(limit=100):
            out.append({"id": d.entity.id, "name": d.name})
        return out
    return run(go(), 60)


def backup_set(cid, name, on):
    c = _cfg()
    for b in c["backups"]:
        if str(b["id"]) == str(cid):
            b["on"] = bool(on)
            break
    else:
        c["backups"].append({"id": int(cid), "name": name, "on": bool(on), "last_id": 0, "count": 0, "last": "لم يُنسخ"})
    _save({"backups": c["backups"]})
    return c["backups"]


def backup_dir():
    return Path.home() / "زاجل" / "نسخ تيليجرام"


def render_html(title, rows):
    """صفحة تُفتح في المتصفح: رسائل المحادثة من اليمين إلى اليسار، مع روابط المرفقات."""
    out = ['<!doctype html><html dir="rtl" lang="ar"><meta charset="utf-8"><title>' + html.escape(title) + '</title>',
           '<style>body{font-family:system-ui,"Geeza Pro",sans-serif;max-width:760px;margin:24px auto;padding:0 12px;background:#f1f4f7;color:#16202a}',
           '.m{background:#fff;border-radius:12px;padding:8px 12px;margin:8px 0}.w{font-size:12px;color:#5a6877}.t{white-space:pre-wrap}a{color:#2f8be6}</style>',
           '<h1>' + html.escape(title) + '</h1>']
    for r in rows:
        att = f'<div><a href="{html.escape(r["file"], quote=True)}">📎 {html.escape(Path(r["file"]).name)}</a></div>' if r.get("file") else ""
        out.append(f'<div class="m"><div class="w">{html.escape(str(r.get("from", "")))} · {html.escape(str(r.get("date", "")))}</div><div class="t">{html.escape(str(r.get("text", "")))}</div>{att}</div>')
    return "\n".join(out)


def backup_run(only=None, media_too=True):
    """ينسخ الجديد من المحادثات المختارة (بالتدريج بعد آخر رسالة نُسخت). يعيد عدد الرسائل الجديدة."""
    c = _cfg()
    total = 0
    for b in c["backups"]:
        if not b["on"] or (only and str(b["id"]) != str(only)):
            continue
        folder = backup_dir() / safe_name(b["name"])
        (folder / "media").mkdir(parents=True, exist_ok=True)
        jl = folder / "messages.jsonl"

        async def go():
            cl = await client()
            ent = await call(lambda: cl.get_entity(b["id"]))

            async def grab():
                return [m async for m in cl.iter_messages(ent, min_id=b["last_id"], reverse=True, limit=2000)]
            msgs = await call(grab)
            rows = []
            for m in msgs:
                row = {"id": m.id, "date": str(m.date)[:16], "from": str(getattr(m.sender, "first_name", "") or getattr(m, "sender_id", "") or ""), "text": getattr(m, "message", "") or ""}
                if media_too and getattr(m, "file", None) and (m.file.size or 0) <= MAX_BACKUP_MEDIA:
                    dest = unique_path(folder / "media", f"{m.id}-{getattr(m.file, 'name', None) or 'file' + (m.file.ext or '')}")
                    try:
                        await call(lambda: cl.download_media(m, file=str(dest)))
                        row["file"] = "media/" + dest.name
                    except Exception as e:
                        if type(e).__name__ in ("FloodWaitError",):
                            raise
                rows.append(row)
            return rows

        rows = run(go(), 3600)
        if rows:
            with open(jl, "a", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            b["last_id"] = max(r["id"] for r in rows)
            b["count"] = b.get("count", 0) + len(rows)
        allrows = [json.loads(x) for x in jl.read_text(encoding="utf-8").splitlines() if x.strip()] if jl.exists() else []
        (folder / "index.html").write_text(render_html(b["name"], allrows), encoding="utf-8")
        b["last"] = time.strftime("%Y-%m-%d %H:%M")
        total += len(rows)
    _save({"backups": c["backups"]})
    return total


def backup_stats():
    d = backup_dir()
    size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.exists() else 0
    return {"size": size, "size_h": human_size(size), "hour": _cfg()["backup_hour"]}


# ================= الخلفية: المراقب والوارد والنسخ الليلي =================
_bg_started = False


def _start_background():
    global _bg_started
    with LOCK:
        if _bg_started:
            return
        _bg_started = True
    try:
        run(_attach_handlers(), 60)
    except Exception as e:
        STATE["error"] = str(e)[:120]
    while True:
        try:
            cfg = _cfg()
            if cfg["backup_day"] != time.strftime("%Y-%m-%d") and time.localtime().tm_hour >= int(cfg["backup_hour"]) and any(b["on"] for b in cfg["backups"]):
                _save({"backup_day": time.strftime("%Y-%m-%d")})
                backup_run()
            if time.time() > STATE["flood_until"]:
                inbox_poll()
        except Exception as e:
            STATE["error"] = str(e)[:120]
        time.sleep(300)


async def _attach_handlers():
    from telethon import events
    c = await client()

    @c.on(events.NewMessage())
    async def handler(ev):
        try:
            cid = ev.chat_id
            for lib in libs():
                if lib.get("on") and (lib["id"] == cid or -1000000000000 - lib["id"] == cid):
                    on_new_message(lib, ev.message)
        except Exception:
            pass
