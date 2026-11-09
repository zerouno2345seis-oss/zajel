"""أوامر تيليجرام لميزات زاجل الحديثة: الطرفية، المزامنة، التحديث، واتساب.
- الطرفية: عرض الجلسات وشاشاتها وتشغيلها؛ أي نص يُرسل إليها أو إيقاف جلسة يمر بتأكيد برمز (الطرفية تحكم كامل بالجهاز).
- لا شيء هنا يعدّل الملفات بنفسه."""
import json
import random
import re
import threading
import time
from pathlib import Path

import telegram_link as TL

NAMES = ("term", "sync", "update", "wa", "mail", "auth", "disks", "clean", "talk")
KEYS = {"Enter": "Enter", "Esc": "Escape", "Ctrl-C": "C-c", "Up": "Up", "Down": "Down", "Tab": "Tab"}
LOCK = threading.RLock()
CONFIRM = {}          # مفتاح ← {chat, kind, agent, text, code, until}
WAITING = {}          # chat ← معرّف وكيل ينتظر نصًّا يُرسل إلى طرفيته


def _b(t, d):
    return {"text": t, "callback_data": d}


# ================= الطرفية =================
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")


def _term_ok():
    import terminal
    if not terminal.available():
        raise ValueError("tmux غير مثبت على هذا الجهاز.")
    return terminal


def _screen_term():
    try:
        T = _term_ok()
    except ValueError as e:
        return str(e), [[_b("رجوع", "scr:home")]]
    rows = T.listing()["agents"]
    lines = [f"{a['name']}: {a['label']}" + ("" if a["installed"] else " (غير مثبت)") for a in rows]
    kb = []
    for a in rows:
        if a["state"] == "stopped":
            if a["installed"]:
                kb.append([_b("▶ شغّل " + a["name"], "tm:go:" + a["id"])])
        else:
            kb.append([_b("📺 " + a["name"], "tm:s:" + a["id"]), _b("⏹", "tm:x:" + a["id"])])
    kb.append([_b("🗣 حديث مباشر مع وكيل", "scr:talk")])
    kb.append([_b("تحديث", "scr:term"), _b("رجوع", "scr:home")])
    return "الطرفية (جلسات الوكلاء):\n" + "\n".join(lines) + "\n\nالإدخال إلى أي جلسة يحتاج تأكيدًا برمز: /tsend وكيل نص", kb


def _screen_of(i):
    T = _term_ok()
    s = T.screen(i, hist=0)
    if not s.get("alive"):
        return "الجلسة غير شغّالة.", [[_b("رجوع", "scr:term")]]
    txt = ANSI.sub("", s.get("text", ""))
    lines = [ln.rstrip() for ln in txt.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    body = "\n".join(lines[-35:])[-3400:] or "(شاشة فارغة)"
    name = T.BY_ID[i]["name"]
    kb = [[_b("تحديث", "tm:s:" + i), _b("أرسل نصًّا", "tm:t:" + i)],
          [_b(k, f"tm:k:{i}:{k}") for k in ("Enter", "Esc", "Ctrl-C")], [_b(k, f"tm:k:{i}:{k}") for k in ("Up", "Down", "Tab")],
          [_b("رجوع", "scr:term")]]
    return f"{name}:\n{body}", kb


def _do_send(chat, agent, text):
    import terminal
    terminal.send(agent, text, ["Enter"], paste=len(text) > 300)
    time.sleep(1)
    txt, kb = _screen_of(agent)
    TL.send(txt, chat, kb=kb)


def _confirm(chat, kind, agent, text=""):
    """الطرفية تحكم كامل بالجهاز: عملية حمراء ← رمز يظهر على شاشة الماك لا في تيليجرام."""
    T = _term_ok()
    name = T.BY_ID[agent]["name"]
    if kind == "send":
        TL.ask_code(chat, f"إرسال إلى طرفية {name} ثم Enter: «{text[:300]}»", lambda: _do_send(chat, agent, text))
    else:
        TL.ask_code(chat, f"إغلاق جلسة {name} وما فيها", lambda: T.stop(agent))


def term_send_command(chat, text):
    """/tsend وكيل نص"""
    T = _term_ok()
    m = re.match(r"^/tsend(@\w+)?\s+(\S+)\s+(.+)$", text.strip(), flags=re.S)
    if not m or m.group(2) not in T.BY_ID:
        raise ValueError("الصيغة: /tsend معرّف_الوكيل النص — مثل: /tsend claude تابع. المعرّفات: " + "، ".join(T.BY_ID))
    _confirm(chat, "send", m.group(2), m.group(3).strip())


def pending_text(chat, text):
    """نص ينتظره أمر «أرسل نصًّا»؛ يعيد True إن استهلكه."""
    i = WAITING.pop(chat, None)
    if not i:
        return False
    if text.strip().lower() in ("الغاء", "إلغاء", "cancel"):
        TL.send("أُلغي.", chat)
        return True
    _confirm(chat, "send", i, text.strip())
    return True


# ================= أخرى =================
def _screen_sync():
    try:
        import app_update
        st = app_update.sync_status()
    except Exception as e:
        return "تعذّر قراءة حال المزامنة: " + str(e)[:120], [[_b("رجوع", "scr:home")]]
    lines = [f"{k}: {v}" for k, v in st.items() if isinstance(v, (str, int, float, bool)) and v not in ("", None)][:10]
    return "المزامنة بين الجهازين:\n" + ("\n".join(lines) or "لا معلومات."), [[_b("🟡 زامن الآن", "ay:sync_run")], [_b("رجوع", "scr:home")]]


def _screen_update():
    import app_update
    try:
        info = app_update.check()
    except Exception as e:
        return "تعذّر فحص التحديث: " + str(e)[:120], [[_b("رجوع", "scr:home")]]
    if info.get("error"):
        return info["error"], [[_b("رجوع", "scr:home")]]
    txt = f"الإصدار الحالي على {TL.HOST}: {info['current']}\nالأحدث على GitHub: {info['latest']}"
    kb = [[{"text": "ثبّت التحديث (يعيد تشغيل زاجل)", "callback_data": "up:ask", "style": "danger"}]] if info["available"] else []
    return txt + ("" if info["available"] else "\nأنت على آخر إصدار."), kb + [[_b("رجوع", "scr:home")]]


def _screen_wa():
    try:
        import whatsapp_watch as W
        s = W.status()
    except Exception as e:
        return "واتساب غير متاح: " + str(e)[:120], [[_b("رجوع", "scr:home")]]
    br = s.get("bridge") or {}
    ok = br.get("ok") if isinstance(br, dict) else br
    txt = ("واتساب:\nالمراقبة: " + ("مفعّلة" if s["enabled"] else "مغلقة") + "\nالجسر: " + ("يعمل" if ok else "غير متصل بهذا الجهاز") +
           f"\nالتقرير الصباحي: {'مفعّل ' + s['digest_hour'].__str__() + ':' + str(s['digest_minute']).zfill(2) if s['digest'] else 'مغلق'}" +
           f"\nتنبيهات أُرسلت: {s['alerts_sent']}" + (f"\nخطأ: {s['error']}" if s["error"] else ""))
    return txt, [[_b("أرسل الملخص الآن", "wa:digest")], [_b("رجوع", "scr:home")]]


def screen(name):
    if name == "term":
        return _screen_term()
    if name == "sync":
        return _screen_sync()
    if name == "update":
        return _screen_update()
    if name == "wa":
        return _screen_wa()
    if name in ("mail", "auth", "disks", "clean", "talk"):
        import telegram_new
        return telegram_new.screen(name)
    return None


# ================= الأوامر والأزرار =================
def on_command(chat, name, text):
    """يعيد True إن عالج الأمر (الشاشات نفسها يعرضها telegram_link)."""
    if name == "mail":
        arg = re.sub(r"^/mail(@\w+)?\s*", "", text.strip())
        if arg:
            import telegram_new
            telegram_new.mail_search(chat, arg)
            return True
    return False


def on_special(chat, word, text):
    """أوامر ذات وسيط: tsend"""
    if word == "tsend":
        term_send_command(chat, text)
        return True
    return False


def on_callback(chat, mid, kind, rest):
    if kind in ("ml", "au", "fc", "tk"):
        import telegram_new
        return telegram_new.on_callback(chat, mid, kind, rest)
    import terminal
    if kind == "tm":
        act, _, arg = rest.partition(":")
        try:
            if act == "go":
                terminal.start(arg)
                time.sleep(1)
                txt, kb = _screen_of(arg)
                TL.send("شُغّلت الجلسة.\n" + txt, chat, kb=kb)
            elif act == "s":
                txt, kb = _screen_of(arg)
                TL.edit(chat, mid, txt, kb)
            elif act == "k":
                i, _, k = arg.partition(":")
                if k not in KEYS:
                    return
                terminal.send(i, "", [KEYS[k]])
                time.sleep(0.8)
                txt, kb = _screen_of(i)
                TL.edit(chat, mid, txt, kb)
            elif act == "t":
                WAITING[chat] = arg
                TL.send(f"اكتب النص الذي يُرسل إلى {terminal.BY_ID[arg]['name']} (أو «إلغاء»).", chat)
            elif act == "x":
                _confirm(chat, "stop", arg)
            elif act == "no":
                CONFIRM.pop(arg, None)
                TL.edit(chat, mid, "أُلغي.", [])
        except ValueError as e:
            TL.send(str(e), chat)
    elif kind == "sy":
        TL.edit(chat, mid, "تجري المزامنة…", [])

        def run():
            try:
                import app_update
                r = app_update.sync_run()
                lines = [f"{k}: {v}" for k, v in (r or {}).items() if isinstance(v, (str, int, float, bool)) and v not in ("", None)][:10]
                TL.send("اكتملت المزامنة ✅\n" + "\n".join(lines), chat)
            except Exception as e:
                TL.send("تعذّرت المزامنة: " + str(e)[:150], chat)
        threading.Thread(target=run, daemon=True).start()
    elif kind == "up":
        import app_update
        if rest == "ask":
            TL.edit(chat, mid, "طُلب الرمز: انظر إلى شاشة الماك.", [])
            TL.ask_code(chat, "تنزيل التحديث وإعادة تشغيل زاجل على " + TL.HOST, lambda: TL.send(f"نُزّل الإصدار {app_update.apply()['version']} ويُعاد تشغيل زاجل الآن.", chat))
    elif kind == "wa":
        try:
            import whatsapp_watch as W
            r = W.digest_now()
            if not r.get("sent"):
                TL.send("لم يُرسل الملخص (الجسر غير متصل أو لا رسائل).", chat)
        except Exception as e:
            TL.send("تعذّر: " + str(e)[:150], chat)
