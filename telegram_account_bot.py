"""شاشات البوت التي تعتمد على حساب المستخدم: البحث، الوارد، المراقب، التنزيلات، نسخ المحادثات.
المنطق كله في telegram_account؛ هنا العرض والأزرار فقط. العمليات هنا خضراء (عرض وبحث وتنزيل إلى الماك) أو صفراء (نسخ ليلي يدوي)؛ لا حذف."""
import threading
import time

import telegram_account as A
import telegram_link as TL

RES = {}                 # محادثة ← {"q","items","counts"}
AWAIT = {}               # محادثة ← "search" ينتظر نص البحث
RECENT = ["زاد المستقنع", "المغني", "الموافقات"]
ICON = {"book": "📘", "video": "🎬", "audio": "🎧", "link": "🔗", "photo": "🖼", "file": "📄"}


def _b(t, d, style=None):
    return TL._b(t, d, style)


HOME = [_b("الرئيسية", "scr:home")]


def linked():
    return A.linked()


def home_line():
    return f"الوارد: {A.new_inbox()} جديد · التنزيلات: {A.active_downloads()} جارية"


def _bar(p, w=10):
    f = max(0, min(w, round(w * p / 100)))
    return "▓" * f + "░" * (w - f)


# ================= الشاشات =================
def screen(name):
    return {"search": screen_search, "inbox": screen_inbox, "watchwords": screen_watch, "dls": screen_dls, "backup": screen_backup}[name]()


def screen_search():
    AWAIT_PROMPT = "اكتب اسم الكتاب أو الدرس أو الفيلم في رسالة، أو اختر بحثًا سابقًا:"
    on = A.pick_libs("all")
    head = f"البحث في تيليجرام ({len(on)} قائمة مفعّلة)\n{AWAIT_PROMPT}"
    kb = [[_b(q, "ta:q:" + q) for q in RECENT[:2]], [_b(q, "ta:q:" + q) for q in RECENT[2:4]]]
    kb = [r for r in kb if r]
    return head, kb + [[_b("مكتباتي", "ta:libs", None)], HOME]


def screen_results(chat, type_="all"):
    r = RES.get(chat)
    if not r:
        return screen_search()
    items = [i for i in r["items"] if type_ == "all" or i["t"] == type_]
    top = items[:6]
    lines = [f"{n}. {ICON.get(i['t'], '📄')} {i['title'][:70]} · {i['size_h']}" for n, i in enumerate(top, 1)]
    head = f"{len(items)} نتيجة لـ «{r['q']}»" + ("" if type_ == "all" else f" ({A.TYPES.get(type_)})")
    dl = [[_b(f"⬇ {n}", "ta:g:" + i["ref"], "success") for n, i in enumerate(top[:4], 1) if i["t"] != "link"]]
    dl = [x for x in dl if x]
    types = [_b(f"{A.TYPES[k]} {r['counts'].get(k, 0)}", "ta:ty:" + k) for k in ("book", "audio", "video")]
    kb = dl + [[_b("حمّل الكل", "ta:ga", "success")] if len(top) > 1 else [], types, HOME]
    return head + "\n" + ("\n".join(lines) if lines else "لا نتائج. جرّب كلمة أخرى أو فعّل قنوات أكثر."), [r for r in kb if r]


def screen_inbox():
    items = A.inbox_items()[:8]
    lines = [f"{'•' if i['state'] == 'new' else '✓'} {i['title'][:60]} ← {i['to']}" for i in items]
    new = A.new_inbox()
    kb = ([[_b(f"رتّب الكل كما اقتُرح ({new})", "ta:ib", "success")]] if new else []) + [[_b("حدّث", "ta:ibp", "primary")], HOME]
    return "الوارد من رسائلك المحفوظة\n" + ("\n".join(lines) or "لا شيء جديدًا. أرسل ما تريد إلى «الرسائل المحفوظة» فيصل هنا."), kb


def screen_watch():
    ws = A.watch_words()
    lines = [f"{'✓' if w['on'] else '—'} «{w['word']}» · {w.get('hits', 0)} مرات" for w in ws]
    kb = [[_b(("أوقف " if w["on"] else "شغّل ") + w["word"][:20], "ta:wt:" + w["id"]), _b("احذف", "ta:wd:" + w["id"])] for w in ws[:6]]
    return "المراقب\n" + ("\n".join(lines) or "لا كلمات بعد.") + "\n\nلإضافة كلمة اكتب: /watch الكلمة", kb + [[_b("آخر ما وُجد", "ta:hits", "primary")], HOME]


def screen_hits():
    hs = A.hits()[:6]
    return "آخر ما وجده المراقب\n" + ("\n".join(f"«{h['w']}» · {h['ch']}\n   {h['text'][:80]} ({h['when']})" for h in hs) or "لم يجد شيئًا بعد."), [[_b("‹ المراقب", "scr:watchwords")]]


def screen_dls():
    ds = A.dl_list()[:6]
    lines = []
    for d in ds:
        st = {"done": "✓", "error": "⚠", "cancelled": "—"}.get(d["state"], f"⏳ {int(d['p'])}٪ {_bar(d['p'])}")
        lines.append(f"{st} {d['title'][:60]}" + (f"\n   {d['error']}" if d["error"] else ""))
    kb = [[_b("أوقف " + d["title"][:22], "ta:dc:" + d["id"], "danger")] for d in ds if d["state"] in ("starting", "running")]
    return "التنزيلات (تنزل إلى الماك مباشرة)\n" + ("\n".join(lines) or "لا تنزيلات بعد."), kb + [[_b("حدّث", "scr:dls", "primary"), HOME[0]]]


def screen_backup():
    bs = A.backups()
    st = A.backup_stats()
    lines = [f"{'✓' if b['on'] else '—'} {b['name'][:40]} · {b.get('last', '')}" for b in bs]
    kb = [[_b(("أوقف " if b["on"] else "شغّل ") + b["name"][:22], "ta:bt:" + str(b["id"]))] for b in bs[:6]]
    return (f"نسخ المحادثات (كل ليلة {st['hour']}:٠٠)\nالمحفوظ على الماك: {st['size_h']}\n" + ("\n".join(lines) or "لا محادثات مختارة. أضفها من زاجل ← تيليجرام ← نسخ المحادثات.")), \
        kb + [[_b("🟡 انسخ الآن", "ta:bn")], HOME]


# ================= الأوامر والنصوص =================
def _notify_to(chat):
    def n(text, d):
        kb = None
        if d.get("state") == "done":
            row = []
            if d.get("t") == "audio" and not d.get("then"):
                row.append(_b("فرّغه", "ta:tr:" + d["id"], "success"))
            if d.get("t") == "book" and not d.get("then"):
                row.append(_b("أرسله إلى كيندل", "ta:kd:" + d["id"], "success"))
            kb = [row] if row else None
        TL.send(text, chat, kb=kb)
    return n


def do_search(chat, q):
    note = TL.send(f"أبحث عن «{q}» في قوائمك…", chat)

    def run():
        try:
            r = A.search(q)
            RES[chat] = {"q": q, "items": r["items"], "counts": r["counts"]}
            if q not in RECENT:
                RECENT.insert(0, q)
                del RECENT[6:]
            TL.edit(chat, note, *screen_results(chat))
        except ValueError as e:
            TL.edit(chat, note, str(e), [HOME])
    threading.Thread(target=run, daemon=True).start()


def on_command(chat, name, arg):
    if name == "search":
        AWAIT.pop(chat, None)
        do_search(chat, arg)
        return True
    if name == "watchwords":
        try:
            A.watch_add(arg)
            TL.send(f"أضفت «{arg}» إلى المراقب. سأنبّهك حين تظهر.", chat)
        except ValueError as e:
            TL.send(str(e), chat)
        return True
    return False


def pending_text(chat, text):
    if AWAIT.pop(chat, None) == "search":
        do_search(chat, text)
        return True
    return False


# ================= الأزرار =================
def on_callback(chat, mid, rest):
    act, _, arg = rest.partition(":")
    try:
        if act == "q":
            do_search(chat, arg)
        elif act == "ty":
            TL.edit(chat, mid, *screen_results(chat, arg))
        elif act == "g":
            A.download(arg, notify=_notify_to(chat))
            TL.send("⬇ بدأ التنزيل على الماك. سأخبرك حين يكتمل.", chat, kb=[[_b("التنزيلات", "scr:dls")]])
        elif act == "ga":
            r = RES.get(chat)
            n = 0
            for i in (r or {}).get("items", [])[:6]:
                if i["t"] != "link":
                    A.download(i["ref"], notify=_notify_to(chat))
                    n += 1
            TL.send(f"⬇ بدأ تنزيل {n} ملفات على الماك.", chat, kb=[[_b("التنزيلات", "scr:dls")]])
        elif act in ("tr", "kd"):
            d = A.DLS.get(arg)
            if d and d.get("path"):
                A._after_download({**d, "then": "transcribe" if act == "tr" else "kindle"}, d["path"])
                TL.send("أُضيف إلى التفريغ." if act == "tr" else "أُرسل إلى كيندل.", chat)
        elif act == "ib":
            n = A.inbox_apply()
            TL.edit(chat, mid, f"رُتّب {n} عنصرًا في مجلداتها على الماك.", [HOME])
        elif act == "ibp":
            A.inbox_poll()
            TL.edit(chat, mid, *screen_inbox())
        elif act == "wt":
            A.watch_toggle(arg)
            TL.edit(chat, mid, *screen_watch())
        elif act == "wd":
            A.watch_remove(arg)
            TL.edit(chat, mid, *screen_watch())
        elif act == "hits":
            TL.edit(chat, mid, *screen_hits())
        elif act == "dc":
            A.dl_cancel(arg)
            TL.edit(chat, mid, *screen_dls())
        elif act == "bt":
            for b in A.backups():
                if str(b["id"]) == arg:
                    A.backup_set(arg, b["name"], not b["on"])
            TL.edit(chat, mid, *screen_backup())
        elif act == "bn":                    # أصفر: ملخص ثم تأكيد
            TL.edit(chat, mid, "🟡 نسخ المحادثات المختارة الآن\nيجلب الجديد منها إلى الماك. يستغرق دقائق وفق الحجم.", [[_b("نفّذ", "ta:bn2", "success"), _b("إلغاء", "scr:backup")]])
            CONFIRM_BK[chat] = time.time() + 300
        elif act == "bn2":
            if CONFIRM_BK.pop(chat, 0) < time.time():
                TL.edit(chat, mid, "انتهت صلاحية التأكيد.", [HOME])
                return
            TL.edit(chat, mid, "🟢 بدأ النسخ على الماك…", [])
            threading.Thread(target=lambda: _bk(chat), daemon=True).start()
        elif act == "libs":
            TL.edit(chat, mid, *screen_libs())
        elif act == "lt":
            for l in A.libs():
                if str(l["id"]) == arg:
                    A.lib_set(arg, not l["on"])
            TL.edit(chat, mid, *screen_libs())
    except ValueError as e:
        TL.send(str(e), chat)


CONFIRM_BK = {}


def _bk(chat):
    try:
        n = A.backup_run()
        TL.send(f"اكتمل النسخ: {n} رسالة جديدة.", chat)
    except ValueError as e:
        TL.send("تعذّر النسخ: " + str(e), chat)


def screen_libs():
    ls = A.libs()
    lines = [f"{'✓' if l['on'] else '—'} {l['name'][:40]} ({A.LISTS.get(l['list'])})" for l in ls]
    kb = [[_b(("أوقف " if l["on"] else "فعّل ") + l["name"][:24], "ta:lt:" + str(l["id"]))] for l in ls[:8]]
    return "مكتباتي\n" + ("\n".join(lines) or "لا قوائم بعد. أضف قنوات من زاجل ← تيليجرام ← مكتباتي."), kb + [[_b("‹ البحث", "scr:search")]]


def hit_notifier(h):
    cfg = TL._cfg()
    chat = cfg.get("chat_id")
    if not chat or (cfg.get("quiet_on") and TL._quiet_now(cfg)):
        return
    kb = [[_b("ابحث عنها", "ta:q:" + h["w"], "primary")] + ([{"text": "افتح الرسالة", "url": h["link"]}] if h.get("link") else [])]
    TL.send(f"🔔 المراقب: «{h['w']}»\n{h['ch']}: {h['text']}", chat, kb=kb)


A.HIT_NOTIFY = hit_notifier
