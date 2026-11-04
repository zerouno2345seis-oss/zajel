"""أوامر تيليجرام لميزات 2.10: البريد، حالة الوكلاء، مساحات الأقراص، التنظيف الكامل بخطة وموافقة."""
from __future__ import annotations

import random
import threading
import time

import telegram_link as TL

MAILRES: dict = {}
FC: dict = {}          # chat ← {"fid","code","until"}


def _b(t, d):
    return {"text": t, "callback_data": d}


def _H():
    import agent_server
    return agent_server.Helper()


def _gb(n):
    return "—" if not n else (f"{n / 1e12:.1f} TB" if n >= 1e12 else f"{n / 1e9:.1f} GB")


def _bar(used, total, w=10):
    if not total:
        return ""
    f = max(0, min(w, round(w * used / total)))
    return "▓" * f + "░" * (w - f)


# ---------- البريد ----------
def screen_mail():
    import zajel_mail
    acc = zajel_mail.accounts()
    if not acc:
        return "لا بريد مربوطًا بعد.\nاربطه من زاجل: الإعدادات ← البريد الإلكتروني ← «＋ ربط بريد».", [[_b("رجوع", "scr:home")]]
    lines = [("• " + (a["label"] + " · " if a["label"] else "") + a["email"] + (" 🔐" if a.get("oauth") else "")) for a in acc]
    return ("البريد المربوط (للقراءة فقط):\n" + "\n".join(lines) + "\n\nللبحث في الوارد والصادر:\n/mail كلمة\nأو /mail كلمة | الحساب\nأو اكتب طلبك للمساعد: «ابحث في بريدي عن …»"), [[_b("رجوع", "scr:home")]]


def mail_search(chat, arg):
    import zajel_mail
    q, _, acct = arg.partition("|")
    r = zajel_mail.search(q.strip(), acct.strip(), "all", 0, 10)
    res = r.get("results") or []
    MAILRES[chat] = res
    if not res:
        TL.send("لا نتائج." + ("\n⚠️ " + "؛ ".join(r.get("errors") or []) if r.get("errors") else ""), chat)
        return
    lines = [f"{i}. {m.get('date', '')[:10]} · {m.get('from', '')[:30]}\n   {m.get('subject', '')[:70]}  ({m.get('account', '')})" for i, m in enumerate(res, 1)]
    kb = [[_b(f"اقرأ {i}", f"ml:r:{i}") for i in range(j, min(j + 5, len(res) + 1))] for j in range(1, len(res) + 1, 5)]
    TL.send("نتائج البريد:\n" + "\n".join(lines), chat, kb=kb)


def mail_read(chat, i):
    import zajel_mail
    res = MAILRES.get(chat) or []
    if not (1 <= i <= len(res)):
        TL.send("انتهت القائمة؛ أعد البحث.", chat)
        return
    m = res[i - 1]
    d = zajel_mail.read(m["account"], m["folder_name"], m["uid"])
    TL.send((d.get("text") or "(بلا نص)")[:3500] + (("\n\n📎 " + "، ".join(d["attachments"])) if d.get("attachments") else ""), chat)


# ---------- الوكلاء ----------
def screen_auth():
    import agent_auth
    ico = {"in": "🟢", "out": "⚪", "expired": "🟠", "unknown": "❔", "missing": "▫️"}
    rows = [f"{ico.get(a['state'], '❔')} {a['name']}: " + (a.get("who") or a.get("detail") or a["state"]) for a in agent_auth.status(force=True)]
    return "حالة دخول الوكلاء:\n" + "\n".join(rows) + "\n\nالدخول والخروج من زاجل: الإعدادات ← الوكلاء (يفتحان نافذة على الجهاز نفسه).", [[_b("تحديث", "au:r")], [_b("رجوع", "scr:home")]]


# ---------- الأقراص والسحابات ----------
def screen_disks():
    st = _H().http("GET", "/api/status")
    rows = []
    for v in st.get("volumes") or []:
        t, f = v.get("total") or 0, v.get("free") or 0
        rows.append(f"{'🌐' if v.get('network') else '💽'} {v['name']}  {_bar(t - f, t)}\n   حرّ {_gb(f)} من {_gb(t)}" + (f" · {v['fs']}" if v.get("fs") else "") + ("" if v.get("writable", True) else " · قراءة فقط"))
    return "الأقراص:\n" + ("\n".join(rows) or "لا أقراص خارجية."), [[_b("تنظيف كامل", "fc:menu")], [_b("رجوع", "scr:home")]]


# ---------- التنظيف الكامل ----------
def screen_clean():
    st = _H().http("GET", "/api/status")
    kb = [[_b("💻 هذا الكمبيوتر", "fc:go:home")]] + [[_b("💽 " + v["name"], "fc:go:vol:" + v["name"])] for v in (st.get("volumes") or []) if v.get("writable", True)][:6]
    return ("التنظيف الكامل: يفحص ما تختاره، ويقترح خطة بمساعدة الوكيل، ولا ينفّذ شيئًا إلا بموافقتك (النقل إلى السلة فقط).\nاختر ما تريد فحصه:"), kb + [[_b("رجوع", "scr:home")]]


def _fc_watch(chat, fid):
    H = _H()
    last = ""
    while True:
        time.sleep(4)
        try:
            r = H.http("GET", "/api/clean/full/job?id=" + fid)
        except ValueError as e:
            TL.send("انقطع التنظيف الكامل: " + str(e), chat)
            return
        if r["state"] == "scanning" or r["state"] == "planning":
            if r["progress"] != last and int(r["seconds"]) % 60 < 5:
                last = r["progress"]
                TL.send("⏳ " + r["progress"][:150], chat)
            continue
        if r["state"] == "ready":
            _fc_plan(chat, fid, r)
        elif r["state"] == "done":
            rep = r.get("report") or {}
            TL.send(f"✅ اكتمل: نُقل {rep.get('ok', 0)} عنصر إلى السلة، وفشل {rep.get('failed', 0)}، وتحرّر نحو {_gb(rep.get('freed', 0))}.", chat)
        else:
            TL.send("انتهى التنظيف: " + (r.get("error") or r["state"]), chat)
        return


def _fc_plan(chat, fid, r):
    pl = r["plan"]
    lines = [f"{'✔' if i['default_on'] else '◻'} {i['title']} — {i['count']} عنصر، {_gb(i['size'])} ({i['risk']})" for i in pl["items"]]
    TL.send("🧹 خطة التنظيف الكامل\n" + "\n".join(lines) + f"\n\nالموصى به (✔) يحرّر نحو {_gb(pl['recommended_size'])}.\n◻ للمراجعة اليدوية من زاجل.", chat)
    if r.get("ai"):
        TL.send("رؤية الوكيل:\n" + r["ai"][:3500], chat)
    code = "%04d" % random.randint(0, 9999)
    FC[chat] = {"fid": fid, "code": code, "until": time.time() + 1800, "ids": [i["id"] for i in pl["items"] if i["default_on"]]}
    if FC[chat]["ids"]:
        TL.send("هل تنفّذ البنود الموصى بها (✔) فقط؟ تُنقل إلى السلة ويمكن استرجاعها.", chat, kb=[[_b(f"نعم، نفّذ ({code})", f"fc:ok:{code}")], [_b("لا", "fc:no")]])


def on_callback(chat, mid, kind, rest):
    if kind == "ml":
        mail_read(chat, int(rest.split(":")[1]))
    elif kind == "au":
        TL.edit(chat, mid, *screen_auth())
    elif kind == "fc":
        act, _, arg = rest.partition(":")
        if act == "menu":
            TL.edit(chat, mid, *screen_clean())
        elif act == "go":
            r = _H().http("POST", "/api/clean/full/start", {"targets": [{"root": arg, "label": "الكمبيوتر" if arg == "home" else arg.split(":", 1)[-1]}]})
            TL.edit(chat, mid, "بدأ التنظيف الكامل… سأرسل لك التقدم والخطة.", [])
            threading.Thread(target=_fc_watch, args=(chat, r["id"]), daemon=True).start()
        elif act == "ok":
            f = FC.get(chat)
            if not f or f["code"] != arg or time.time() > f["until"]:
                TL.send("انتهت صلاحية الخطة أو الرمز غير صحيح.", chat)
                return
            FC.pop(chat, None)
            _H().http("POST", "/api/clean/full/apply", {"id": f["fid"], "items": f["ids"], "confirm": True})
            TL.edit(chat, mid, "يجري التنفيذ…", [])
            threading.Thread(target=_fc_watch, args=(chat, f["fid"]), daemon=True).start()
        elif act == "no":
            FC.pop(chat, None)
            TL.edit(chat, mid, "أُلغي؛ لم يُنفَّذ شيء.", [])


def screen(name):
    return {"mail": screen_mail, "auth": screen_auth, "disks": screen_disks, "clean": screen_clean}[name]()
