"""شاشات البوت لأقسام «المزيد» وما يتبعها (٢.١٦).
- لا منطق جديد هنا: كل شاشة تستدعي ما في agent_server (الأدوات الحارسة) والوحدات الموجودة، وتعرض النتيجة بأزرار ملوّنة.
- مستويات الخطورة تُفرض هنا في الخادم لا في الأزرار:
  أخضر: يُنفَّذ فورًا. أصفر: ملخص ثم تأكيد (يُسجَّل التأكيد المنتظر في الخادم فلا ينفع زر قديم أو مزوَّر).
  أحمر: رمز من أربعة أرقام يظهر على شاشة الماك وينتهي بعد ٥ دقائق (TL.ask_code)، أو بطاقة الموافقة المعلّقة في agent_server."""
import threading
import time
from pathlib import Path

import telegram_link as TL

GREEN, YELLOW, RED = "success", None, "danger"      # لون الزر في تيليجرام؛ الأصفر لا لون له فنُميّزه بالأيقونة
PRI = "primary"

GROUPS = [("الأجهزة والملفات", ["phone", "watch", "cloud", "disks", "archives"]),
          ("الصيانة", ["clean", "monitor", "servers", "update"]),
          ("التواصل", ["mail", "wa", "term"]),
          ("المعرفة", ["books", "transcribe", "memory"]),
          ("الوكلاء والأتمتة", ["agents", "cmds", "devices", "settings"])]
TITLES = {"phone": "الجوال", "watch": "الساعة", "cloud": "السحابة والمزامنة", "disks": "الأقراص", "archives": "الأرشيف والضغط",
          "clean": "التنظيف", "monitor": "المراقبة", "servers": "الخوادم", "update": "التحديث", "mail": "البريد", "wa": "واتساب",
          "term": "الطرفية", "books": "الكتب", "transcribe": "التفريغ", "memory": "الذاكرة", "agents": "الوكلاء",
          "cmds": "الأوامر الجاهزة", "devices": "الأجهزة", "settings": "الإعدادات"}
ALIAS = {"cloud": "sync", "devices": "pc", "memory": "mem"}      # أسماء شاشات موجودة من قبل في telegram_link
NAMES = ("more", "phone", "watch", "archives", "monitor", "servers", "books", "transcribe", "files", "search", "inbox", "watchwords", "dls", "backup", "assistant")
ACCOUNT_SCREENS = ("search", "inbox", "watchwords", "dls", "backup")


def _b(t, d, style=None):
    return TL._b(t, d, style)


BACK = [_b("‹ كل الأقسام", "scr:more"), _b("الرئيسية", "scr:home")]


def _call(name, args=None):
    import agent_server
    r = agent_server.call(name, args or {}, agent="telegram")
    if r.get("error") or r.get("refused"):
        raise ValueError(r.get("error"))
    return r


def _kv(d, keys=None, limit=12):
    out = []
    for k, v in (d or {}).items():
        if keys and k not in keys:
            continue
        if isinstance(v, (str, int, float, bool)) and v not in ("", None):
            out.append(f"{k}: {'نعم' if v is True else 'لا' if v is False else v}")
    return out[:limit]


def _gb(n):
    n = float(n or 0)
    return f"{n / 1e9:.1f} غ.ب" if n >= 1e9 else f"{n / 1e6:.0f} م.ب"


# ================= القائمة =================
def screen_more():
    rows = []
    row = []
    for _, keys in GROUPS:
        for k in keys:
            row.append(_b(TITLES[k], "scr:" + k))
            if len(row) == 3:
                rows.append(row)
                row = []
    if row:
        rows.append(row)
    names = "\n".join(f"• {g}: " + "، ".join(TITLES[k] for k in keys) for g, keys in GROUPS)
    return "كل الأقسام:\n" + names + "\n\nاختر قسمًا:", rows + [[_b("الرئيسية", "scr:home")]]


# ================= الأقسام =================
def _guard(fn):
    def run(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:
            return f"تعذّر قراءة القسم: {str(e)[:150]}", [BACK]
    return run


@_guard
def screen_phone():
    import agent_server, phone_link
    s = phone_link.status(agent_server.M)
    lines = _kv(s, ("connected", "model", "wifi", "battery", "message", "serial"))
    on = bool(s.get("connected"))
    kb = [[_b("تحديث", "scr:phone", PRI)]]
    if not on:
        kb.append([_b("🟡 صِل الجوال لاسلكيًا", "ay:phone_connect")])
    return "الجوال:\n" + ("\n".join(lines) or ("موصول" if on else "غير موصول")), kb + [BACK]


@_guard
def screen_watch():
    r = _call("watch_status").get("result") or {}
    txt = ("الساعة: " + ("متصلة " + str(r.get("addr")) if r.get("connected") else "غير متصلة")) + (("\n" + r["note"]) if r.get("note") else "")
    return txt, [[_b("تحديث", "scr:watch", PRI)], BACK]


@_guard
def screen_archives():
    from archives import is_archive_name
    found = []
    for d in (Path.home() / "Downloads", Path.home() / "Documents"):
        if d.exists():
            for p in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if p.is_file() and is_archive_name(p.name):
                    found.append(p)
    lines = [f"• {p.name} — {_gb(p.stat().st_size)} ({p.parent.name})" for p in found[:8]]
    return ("الملفات المضغوطة في التنزيلات والمستندات:\n" + "\n".join(lines) + "\n\nلفكّ ضغط ملف اكتب للمساعد: «فكّ ضغط …».") if lines else "لا ملفات مضغوطة في التنزيلات والمستندات.", [BACK]


@_guard
def screen_monitor():
    import health
    rep = health.scan()
    mark = {"ok": "🟢", "warn": "🟠", "bad": "🔴", "info": "🔵"}
    lines = [f"{mark.get(c.get('status'), '•')} {c['title']}: {str(c.get('summary'))[:90]}" for c in rep.get("cards", [])]
    return "المراقبة (حال هذا الجهاز):\n" + "\n".join(lines), [[_b("تحديث", "scr:monitor", PRI)], BACK]


@_guard
def screen_servers():
    r = _call("list_servers").get("result") or {}
    run = r.get("running") or []
    lines = [f"{'🔒' if s['protected'] else '🟢'} {s['name']} — المنفذ {', '.join(map(str, s['ports'])) or '—'}" for s in run]
    kb = [[_b("🔴 أوقف " + s["name"][:24], f"sv:x:{s['pid']}", RED)] for s in run if not s["protected"]][:6]
    return ("الخوادم العاملة:\n" + "\n".join(lines)) if lines else "لا خوادم عاملة.", kb + [[_b("تحديث", "scr:servers", PRI)], BACK]


@_guard
def screen_books():
    import ebook, kindle_src
    lines = [f"أدوات التحويل: {'متاحة' if ebook.available() else 'غير مثبتة'}", f"كيندل: {'موصول' if kindle_src.present() else 'غير موصول'}"]
    return "الكتب:\n" + "\n".join(lines) + "\n\nأرسل لي ملف كتاب أو اطلب من المساعد: «حوّل هذا الكتاب وأرسله إلى كيندل».", [[_b("تحديث", "scr:books", PRI)], BACK]


@_guard
def screen_transcribe():
    import media
    jobs = getattr(media, "JOBS", None) or getattr(media, "TRANSCRIBE", None) or {}
    n = sum(1 for j in jobs.values() if isinstance(j, dict) and j.get("state") in ("running", "queued")) if isinstance(jobs, dict) else 0
    return f"التفريغ: {n} قيد العمل.\nأرسل رسالة صوتية فتُفرَّغ ويُجاب عنها، أو اطلب من المساعد تفريغ ملف على الماك.", [[_b("تحديث", "scr:transcribe", PRI)], BACK]


def screen_files():
    try:
        r = _call("places").get("result")
        items = r.get("places") if isinstance(r, dict) else r
        lines = [f"• {p.get('label') or p.get('name') or p.get('id')}" for p in (items or [])[:10]]
    except Exception as e:
        lines = ["تعذّر قراءة الأماكن: " + str(e)[:100]]
    return "الملفات:\n" + "\n".join(lines) + "\n\nللبحث عن ملف: /find كلمة. ولإرسال ملف إليك اطلب من المساعد: «أرسل لي …».", [[_b("🔎 كيف أبحث؟", "scr:findhelp")], [_b("الرئيسية", "scr:home")]]


def screen_assistant():
    return screen_help_text(), [[_b("الرئيسية", "scr:home", PRI)]]


def screen_help_text():
    return ("أنا نفس المساعد الذي في زاجل. اكتب لي بكلامك العادي أو سجّل رسالة صوتية.\n"
            "أمثلة: «ما حال الوكلاء؟» · «لخّص بريدي غير المقروء» · «ابحث عن ملف العقد».\n"
            "الأقسام في الشريط: كل جهاز له قسمه (ماك المكتب، ماك البيت).\n"
            "الأزرار: 🟢 فوري · 🟡 ملخص ثم تأكيد · 🔴 رمز يظهر على شاشة الماك.")


# ================= شاشات تحتاج ربط الحساب (المرحلة ٢) =================
def _account():
    try:
        import telegram_account
        return telegram_account
    except ImportError:
        return None


def screen_account(name):
    acc = _account()
    if acc is None or not acc.linked():
        return ("هذا القسم يحتاج ربط حسابك الشخصي في تيليجرام (غير البوت).\nافتح زاجل ← الإعدادات ← تيليجرام ← «اربط حسابي»، وتسجّل الدخول بنفسك مرة واحدة.",
                [[_b("الرئيسية", "scr:home", PRI)]])
    return acc.screen(name)


def screen(name):
    if name == "more":
        return screen_more()
    if name in ACCOUNT_SCREENS:
        return screen_account(name)
    fn = {"phone": screen_phone, "watch": screen_watch, "archives": screen_archives, "monitor": screen_monitor, "servers": screen_servers,
          "books": screen_books, "transcribe": screen_transcribe, "files": screen_files, "assistant": screen_assistant}.get(name)
    return fn() if fn else None


# ================= أزرار الإجراءات (أصفر/أحمر) =================
YELLOW_ACTIONS = {
    "phone_connect": ("صِل الجوال لاسلكيًا", "يجرّب العنوان المحفوظ ثم اكتشاف الشبكة. لا يغيّر شيئًا في الجوال.", "phone"),
    "sync_run": ("زامن الآن", "يزامن هذا الجهاز مع المستودع الخاص. يستغرق دقيقة تقريبًا.", "sync"),
}
PENDING_Y = {}          # (chat, aid) ← حتى متى يصلح التأكيد


def _run_yellow(aid, chat):
    if aid == "phone_connect":
        r = _call("phone_connect").get("result")
        TL.send("نتيجة الاتصال:\n" + "\n".join(_kv(r if isinstance(r, dict) else {"النتيجة": str(r)})) , chat)
    elif aid == "sync_run":
        import app_update
        r = app_update.sync_run()
        TL.send("اكتملت المزامنة ✅\n" + "\n".join(_kv(r)[:10]), chat)


def on_callback(chat, mid, kind, rest):
    if kind == "ay":                      # أصفر: الملخص أولًا
        if rest not in YELLOW_ACTIONS:
            return
        label, summary, back = YELLOW_ACTIONS[rest]
        PENDING_Y[(chat, rest)] = time.time() + 300
        TL.edit(chat, mid, f"🟡 {label}\n{summary}\nأكّد للتنفيذ.", [[_b("نفّذ", "ay2:" + rest, GREEN), _b("إلغاء", "scr:" + back)]])
    elif kind == "ay2":                   # التأكيد لا يُقبل إلا إن سبقه الملخص في الخادم
        if rest not in YELLOW_ACTIONS:
            return
        if PENDING_Y.pop((chat, rest), 0) < time.time():
            TL.edit(chat, mid, "انتهت صلاحية التأكيد؛ ابدأ من القسم من جديد.", [[_b("الرئيسية", "scr:home")]])
            return
        TL.edit(chat, mid, "🟢 بدأ التنفيذ…", [])
        threading.Thread(target=lambda: _safe(chat, _run_yellow, rest, chat), daemon=True).start()
    elif kind == "sv":                    # أحمر: إيقاف خادم ← بطاقة موافقة معلّقة في agent_server (لا ينفّذ شيئًا قبل الرمز)
        act, _, pid = rest.partition(":")
        if act == "x":
            r = _call("stop_server", {"pid": int(pid)})
            if not r.get("pending"):
                TL.send("تم.", chat)


def _safe(chat, fn, *a):
    try:
        fn(*a)
    except Exception as e:
        TL.send("تعذّر التنفيذ: " + str(e)[:150], chat)
