"""أوامر تيليجرام لميزات زاجل الحديثة: مجلس الوكلاء، الطرفية، المزامنة، التحديث، واتساب.
- المجلس: اختيار المفوَّضين والمحكّم والعمق، إرسال سؤال، متابعة التقدم، وصول الحكم، ثم إرساله إلى تيليجرام مباشرة أو إلى موقع (رابط يضبطه المستخدم).
- الطرفية: عرض الجلسات وشاشاتها وتشغيلها؛ أي نص يُرسل إليها أو إيقاف جلسة يمر بتأكيد برمز (الطرفية تحكم كامل بالجهاز).
- لا شيء هنا يعدّل الملفات بنفسه: المجلس للقراءة والبحث فقط."""
import ipaddress
import json
import random
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import telegram_link as TL

NAMES = ("council", "term", "sync", "update", "wa", "mail", "auth", "disks", "clean", "talk")
DEFAULTS = {"ids": ["claude", "hermes"], "main": "claude", "depth": "bal", "blind": True, "review": False, "verify": True, "webhook": "", "auto_web": False}
DEPTH_LABEL = {"fast": "سريع", "bal": "متوازن", "deep": "عميق"}
KEYS = {"Enter": "Enter", "Esc": "Escape", "Ctrl-C": "C-c", "Up": "Up", "Down": "Down", "Tab": "Tab"}
LOCK = threading.RLock()
CONFIRM = {}          # مفتاح ← {chat, kind, agent, text, code, until}
WAITING = {}          # chat ← معرّف وكيل ينتظر نصًّا يُرسل إلى طرفيته
WATCH = {}            # معرّف الجولة ← خيط المتابعة


def _file():
    return Path(TL.DATA) / "telegram_extras.json"


def _cfg():
    try:
        d = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {**DEFAULTS, **(d if isinstance(d, dict) else {})}


def _save(patch):
    with LOCK:
        c = {**_cfg(), **patch}
        _file().write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        return c


def _b(t, d):
    return {"text": t, "callback_data": d}


def _host_of(url):
    try:
        return urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return ""


def valid_url(url):
    """https لأي موقع؛ و http للجهاز نفسه أو الشبكة المحلية فقط (حتى لا تسافر النتيجة مكشوفة عبر الإنترنت)."""
    try:
        u = urllib.parse.urlparse(str(url).strip())
    except ValueError:
        return False
    if not u.hostname or u.username or u.password:
        return False
    if u.scheme == "https":
        return True
    if u.scheme != "http":
        return False
    h = u.hostname
    if h == "localhost" or h.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


# ================= المجلس =================
def _agents():
    import terminal
    return [a for a in terminal.council_agents()["agents"] if a.get("direct")]


def _sections(text):
    out, cur = {}, "_"
    for line in str(text or "").splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1)
            out[cur] = []
        else:
            out.setdefault(cur, []).append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def _view(rid=""):
    import terminal
    return terminal.council_view(rid).get("round")


def _screen_council():
    c = _cfg()
    ags = _agents()
    names = {a["id"]: a["name"] for a in ags}
    ids = [i for i in c["ids"] if i in names]
    main = c["main"] if c["main"] in names else (ids[0] if ids else "")
    opts = [x for x, on in (("مُعمّى", c["blind"]), ("نقد متبادل", c["review"]), ("تحقق", c["verify"])) if on]
    txt = ("مجلس الوكلاء\n"
           f"المفوَّضون: {'، '.join(names[i] for i in ids) or 'لم تختر'}\n"
           f"المحكّم: {names.get(main, 'لم تختر')}\n"
           f"العمق: {DEPTH_LABEL[c['depth']]}\n"
           f"الخيارات: {'، '.join(opts) or 'بلا'}\n"
           f"الموقع الخارجي: {_host_of(c['webhook']) or 'غير مضبوط'}" + (" (إرسال تلقائي)" if c["webhook"] and c["auto_web"] else "") + "\n\n"
           "اكتب: /council ثم سؤالك، فيُرسل للمفوَّضين ويصلك الحكم هنا.\n"
           "/cweb رابط — يضبط الموقع الذي تُرسل إليه النتيجة · /cweb off يمحوه.")
    kb = [[_b(("✓ " if a["id"] in ids else "") + a["name"], "cg:t:" + a["id"]) for a in ags[i:i + 3]] for i in range(0, len(ags), 3)]
    kb.append([_b(("⚖ " if a["id"] == main else "") + a["name"], "cg:m:" + a["id"]) for a in ags[:3]])
    if len(ags) > 3:
        kb.append([_b(("⚖ " if a["id"] == main else "") + a["name"], "cg:m:" + a["id"]) for a in ags[3:6]])
    kb.append([_b(("● " if c["depth"] == k else "") + v, "cg:d:" + k) for k, v in DEPTH_LABEL.items()])
    kb.append([_b(("✓ " if c["blind"] else "") + "تعمية", "cg:o:blind"), _b(("✓ " if c["review"] else "") + "نقد", "cg:o:review"), _b(("✓ " if c["verify"] else "") + "تحقق", "cg:o:verify")])
    row = [_b("فحص الجاهزية", "cg:chk"), _b("آخر نتيجة", "cg:last")]
    if c["webhook"]:
        row.append(_b(("✓ " if c["auto_web"] else "") + "إرسال تلقائي للموقع", "cg:o:auto_web"))
    kb.append(row)
    kb.append([_b("رجوع", "scr:home")])
    return txt + "\n(المحكّم هو اسم بعد ⚖)", kb


def _check_text(ids):
    import terminal
    res = terminal.council_check(ids, True)["agents"]
    lab = {"ready": "جاهز", "slow": "بطيء", "off": "معطّل"}
    return "فحص الجاهزية:\n" + "\n".join(f"{terminal.BY_ID[i]['name']}: {lab.get(v['state'], v['state'])}" + (f" — {v['note']}" if v["state"] == "off" else "") for i, v in res.items())


def council_ask(chat, q, parent=""):
    import terminal
    q = re.sub(r"^/council(@\w+)?\s*", "", q.strip()).strip()
    if not q:
        raise ValueError("اكتب سؤالك بعد الأمر: /council ما حكم كذا؟")
    c = _cfg()
    names = {a["id"] for a in _agents()}
    ids = [i for i in c["ids"] if i in names]
    if not ids:
        raise ValueError("اختر مفوَّضًا واحدًا على الأقل من شاشة /council.")
    main = c["main"] if c["main"] in names else ids[0]
    r = terminal.council_start(ids, q, main, True, [], parent, None, "direct", c["depth"], c["blind"], c["review"], c["verify"])
    rid = r["id"]
    _save({"last": rid})
    mid = TL.send(f"بدأ المجلس: {len(ids)} مفوَّض، المحكّم {terminal.BY_ID[main]['name']}، العمق {DEPTH_LABEL[c['depth']]}.\nأخبرك عند وصول الحكم.", chat, kb=[[_b("قيّم الآن", "cr:ev:" + rid), _b("أوقف", "cr:stop:" + rid)]])
    t = threading.Thread(target=_watch, args=(chat, rid, mid), daemon=True)
    WATCH[rid] = t
    t.start()


PHASE = {"asking": "يجمع الإجابات", "review": "جولة النقد المتبادل", "evaluating": "المحكّم يكتب الحكم", "refining": "يحدّث الحكم"}


def _watch(chat, rid, mid):
    last, t0 = "", time.time()
    try:
        while time.time() - t0 < 3 * 3600 and not TL._stop.is_set():
            r = _view(rid)
            if not r:
                return
            if r["phase"] in ("done", "stopped", "error"):
                break
            done = sum(1 for e in r["agents"].values() if e.get("state") in ("done", "done_raw", "error", "timeout", "stopped"))
            line = f"{PHASE.get(r['phase'], r['phase'])} ({done} من {len(r['agents'])})"
            acts = [e.get("activity") for e in r["agents"].values() if e.get("activity")]
            if acts:
                line += "\n" + acts[-1][:90]
            if line != last and mid:
                TL.edit(chat, mid, "المجلس: " + line, [[_b("قيّم الآن", "cr:ev:" + rid), _b("أوقف", "cr:stop:" + rid)]])
                last = line
            time.sleep(5)
        if mid:
            TL._quiet("deleteMessage", {"chat_id": chat, "message_id": mid})
        deliver_message(chat, rid)
        c = _cfg()
        if c["webhook"] and c["auto_web"]:
            try:
                post_web(rid)
                TL.send("أُرسلت النتيجة إلى " + _host_of(c["webhook"]) + " ✅", chat)
            except ValueError as e:
                TL.send("تعذّر الإرسال إلى الموقع: " + str(e), chat)
    except Exception as e:
        TL.send("تعذّرت متابعة المجلس: " + str(e)[:120], chat)
    finally:
        WATCH.pop(rid, None)


def _final_parts(r):
    ev = r["eval"]
    sec = _sections(ev.get("answer", ""))
    conf = next((ln.strip() for ln in sec.get("الخلاصة", "").splitlines() if ln.strip().startswith("الثقة")), "")
    final = sec.get("الحكم النهائي") or ev.get("answer", "")
    return conf, final, sec


def _answers(r):
    out = []
    lt = r.get("letters") or {}
    for i, e in r["agents"].items():
        t = e.get("revised") or e.get("answer") or ""
        out.append((e.get("name", i), lt.get(i, ""), t.strip(), e.get("state")))
    return out


def deliver_message(chat, rid):
    """يرسل النتيجة إلى محادثة تيليجرام مباشرة: الحكم النهائي، وأزرار لبقية الأقسام والملفات والموقع."""
    r = _view(rid)
    if not r:
        raise ValueError("لا توجد هذه الجولة.")
    q = r["question"][:90]
    kb = [[_b("كل أقسام الحكم", "cr:full:" + rid), _b("إجابات الوكلاء", "cr:ans:" + rid)],
          [_b("Word", "cr:docx:" + rid), _b("PDF", "cr:pdf:" + rid), _b("Markdown", "cr:md:" + rid)],
          [_b("أرسل إلى الموقع", "cr:web:" + rid), _b("تابع على هذا الحكم", "cr:fol:" + rid)]]
    ev = r["eval"]
    if ev.get("answer"):
        conf, final, _ = _final_parts(r)
        TL.send(f"⚖ مجلس الوكلاء\nالسؤال: {q}\n" + (conf + "\n" if conf else "") + "\n" + final, chat, kb=kb)
        return
    why = "أُوقف المجلس." if r["phase"] == "stopped" else (ev.get("error") or "لم يُكتب حكم (لم يُحدَّد محكّم أو تعذّر).")
    real = [a for a in _answers(r) if a[2]]
    TL.send(f"⚖ مجلس الوكلاء\nالسؤال: {q}\nبلا حكم: {why}\nوصلت {len(real)} إجابة.", chat, kb=kb)


def send_answers(chat, rid):
    r = _view(rid)
    if not r:
        raise ValueError("لا توجد هذه الجولة.")
    lt = r.get("letters") or {}
    sent = 0
    for i, e in r["agents"].items():
        t = (e.get("revised") or e.get("answer") or "").strip()
        head = "— " + e.get("name", i) + (f" (الإجابة {lt[i]})" if lt.get(i) else "") + (" [جزئية]" if e.get("partial") else "")
        TL.send(head + "\n" + (t or "لا إجابة (" + str(e.get("state")) + ")"), chat)
        sent += 1
    if not sent:
        raise ValueError("لا إجابات.")


def send_full(chat, rid):
    r = _view(rid)
    if not r or not r["eval"].get("answer"):
        raise ValueError("لا حكم بعد.")
    TL.send(r["eval"]["answer"], chat)


def send_export(chat, rid, fmt):
    import council_export as CE
    import terminal
    rd = terminal.COUNCIL.get(rid)
    if not rd or not any(e.get("answer") for e in rd["agents"].values()):
        raise ValueError("لا إجابات للتصدير بعد.")
    path = CE.export(terminal._snap(rd), {k: v["name"] for k, v in terminal.BY_ID.items()}, fmt)
    TL.send_file(path, "مجلس الوكلاء: " + rd["question"][:80])


def post_web(rid):
    """يرسل النتيجة (JSON) إلى الرابط الذي ضبطه المستخدم بنفسه. يعيد رمز الاستجابة."""
    url = _cfg()["webhook"]
    if not url:
        raise ValueError("لم تضبط رابط الموقع بعد. اكتب: /cweb https://…")
    if not valid_url(url):
        raise ValueError("الرابط غير مقبول (https فقط، أو http للشبكة المحلية).")
    r = _view(rid)
    if not r:
        raise ValueError("لا توجد هذه الجولة.")
    conf, final, sec = _final_parts(r) if r["eval"].get("answer") else ("", "", {})
    payload = {"source": "zajel", "host": TL.HOST, "id": r["id"], "question": r["question"], "phase": r["phase"], "confidence": conf, "final": final,
               "verdict": r["eval"].get("answer", ""), "sections": sec,
               "answers": [{"agent": n, "letter": lt, "text": t} for n, lt, t, _ in _answers(r)], "created": r.get("created")}
    req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "zajel"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status
    except Exception as exc:
        raise ValueError(str(exc)[:120])


def deliver(rid, target):
    """للواجهة: target = telegram | web."""
    rid = rid or _cfg().get("last", "")
    if target == "telegram":
        chat = TL._cfg()["chat_id"]
        if not chat:
            raise ValueError("تيليجرام غير مقترن على هذا الجهاز.")
        deliver_message(chat, rid)
        return {"ok": True}
    if target == "web":
        return {"ok": True, "status": post_web(rid)}
    raise ValueError("وجهة غير معروفة.")


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


def _confirm(chat, kind, agent, text=""):
    code = "%04d" % random.randint(0, 9999)
    key = "%06x" % random.randint(0, 0xFFFFFF)
    CONFIRM[key] = {"chat": chat, "kind": kind, "agent": agent, "text": text, "code": code, "until": time.time() + 300}
    T = _term_ok()
    name = T.BY_ID[agent]["name"]
    if kind == "send":
        msg = f"سيُرسل إلى طرفية {name} ثم يُضغط Enter:\n«{text[:600]}»"
    else:
        msg = f"سيُغلق جلسة {name} وما فيها."
    TL.send(msg + "\nالطرفية تحكم كامل بالجهاز؛ أكّد برمزها:", chat, kb=[[_b(f"نفّذ ({code})", f"tm:ok:{key}:{code}")], [_b("ألغِ", "tm:no:" + key)]])


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
    return "المزامنة بين الجهازين:\n" + ("\n".join(lines) or "لا معلومات."), [[_b("زامن الآن", "sy:run")], [_b("رجوع", "scr:home")]]


def _screen_update():
    import app_update
    try:
        info = app_update.check()
    except Exception as e:
        return "تعذّر فحص التحديث: " + str(e)[:120], [[_b("رجوع", "scr:home")]]
    if info.get("error"):
        return info["error"], [[_b("رجوع", "scr:home")]]
    txt = f"الإصدار الحالي على {TL.HOST}: {info['current']}\nالأحدث على GitHub: {info['latest']}"
    kb = [[_b("ثبّت التحديث (يعيد تشغيل زاجل)", "up:ask")]] if info["available"] else []
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
    if name == "council":
        return _screen_council()
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
    if name == "council":
        m = re.match(r"^(?:/council(?:@\w+)?|مجلس)\s+(.+)$", text.strip(), flags=re.S)
        if m:
            council_ask(chat, m.group(1))
            return True
    return False


def on_special(chat, word, text):
    """أوامر ذات وسيط: cweb cstop cres cfollow tsend"""
    if word == "cweb":
        arg = re.sub(r"^/cweb(@\w+)?\s*", "", text.strip())
        if arg in ("off", "حذف", "مسح"):
            _save({"webhook": "", "auto_web": False})
            TL.send("مُسح رابط الموقع.", chat)
        elif arg:
            if not valid_url(arg):
                raise ValueError("الرابط غير مقبول: https فقط، أو http للشبكة المحلية.")
            _save({"webhook": arg})
            TL.send("ضُبط الموقع: " + _host_of(arg) + ". من بطاقة النتيجة اضغط «أرسل إلى الموقع»، أو فعّل الإرسال التلقائي من /council.", chat)
        else:
            c = _cfg()
            TL.send("الموقع الحالي: " + (_host_of(c["webhook"]) or "غير مضبوط") + "\nلضبطه: /cweb https://…  ولمحوه: /cweb off")
        return True
    if word == "cstop":
        import terminal
        terminal.council_stop("")
        TL.send("طُلب إيقاف المجلس.", chat)
        return True
    if word == "cres":
        arg = re.sub(r"^/cres(@\w+)?\s*", "", text.strip())
        rid = arg or _cfg().get("last", "")
        if not rid:
            raise ValueError("لا جولة سابقة.")
        deliver_message(chat, rid)
        return True
    if word == "cfollow":
        council_ask(chat, re.sub(r"^/cfollow(@\w+)?\s*", "", text.strip()), parent=_cfg().get("last", ""))
        return True
    if word == "tsend":
        term_send_command(chat, text)
        return True
    return False


def on_callback(chat, mid, kind, rest):
    if kind in ("ml", "au", "fc", "tk"):
        import telegram_new
        return telegram_new.on_callback(chat, mid, kind, rest)
    import terminal
    if kind == "cg":
        act, _, arg = rest.partition(":")
        c = _cfg()
        if act == "t":
            ids = [i for i in c["ids"] if i != arg] if arg in c["ids"] else c["ids"] + [arg]
            _save({"ids": ids})
        elif act == "m":
            _save({"main": arg})
        elif act == "d" and arg in DEPTH_LABEL:
            _save({"depth": arg, **({"blind": True, "review": False, "verify": False} if arg == "fast" else {"blind": True, "review": False, "verify": True} if arg == "bal" else {"blind": True, "review": True, "verify": True})})
        elif act == "o" and arg in ("blind", "review", "verify", "auto_web"):
            _save({arg: not c[arg]})
        elif act == "chk":
            TL.send(_check_text([a["id"] for a in _agents()]), chat)
            return
        elif act == "last":
            rid = c.get("last")
            if not rid:
                TL.send("لا جولة سابقة.", chat)
            else:
                deliver_message(chat, rid)
            return
        txt, kb = _screen_council()
        TL.edit(chat, mid, txt, kb)
    elif kind == "cr":
        act, _, rid = rest.partition(":")
        try:
            if act == "ev":
                terminal.council_evaluate(rid)
                TL.send("طُلب الحكم بما وصل حتى الآن.", chat)
            elif act == "stop":
                terminal.council_stop(rid)
                TL.send("طُلب إيقاف المجلس.", chat)
            elif act == "full":
                send_full(chat, rid)
            elif act == "ans":
                send_answers(chat, rid)
            elif act in ("docx", "pdf", "md"):
                send_export(chat, rid, act)
            elif act == "web":
                st = post_web(rid)
                TL.send(f"أُرسلت النتيجة إلى {_host_of(_cfg()['webhook'])} (استجابة {st}) ✅", chat)
            elif act == "fol":
                _save({"last": rid})
                TL.send("اكتب: /cfollow ثم سؤالك، فيُبنى على هذا الحكم.", chat)
        except ValueError as e:
            TL.send(str(e), chat)
    elif kind == "tm":
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
            elif act == "ok":
                key, _, code = arg.partition(":")
                p = CONFIRM.get(key)
                if not p or p["chat"] != chat or p["code"] != code or p["until"] < time.time():
                    TL.edit(chat, mid, "الرمز غير صحيح أو انتهت صلاحية الطلب.", [])
                    return
                CONFIRM.pop(key, None)
                if p["kind"] == "send":
                    terminal.send(p["agent"], p["text"], ["Enter"], paste=len(p["text"]) > 300)
                    time.sleep(1)
                    txt, kb = _screen_of(p["agent"])
                    TL.edit(chat, mid, "✅ أُرسل.", [])
                    TL.send(txt, chat, kb=kb)
                else:
                    terminal.stop(p["agent"])
                    TL.edit(chat, mid, "✅ أُغلقت الجلسة.", [])
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
            code = "%04d" % random.randint(0, 9999)
            CONFIRM["up"] = {"chat": chat, "code": code, "until": time.time() + 300}
            TL.edit(chat, mid, "سيُنزَّل التحديث ويُعاد تشغيل زاجل على " + TL.HOST + ". أكّد:", [[_b(f"ثبّت ({code})", "up:go:" + code)], [_b("ألغِ", "scr:update")]])
        elif rest.startswith("go:"):
            p = CONFIRM.get("up")
            if not p or p["chat"] != chat or p["code"] != rest[3:] or p["until"] < time.time():
                TL.edit(chat, mid, "الرمز غير صحيح أو انتهت صلاحيته.", [])
                return
            CONFIRM.pop("up", None)
            try:
                r = app_update.apply()
                TL.edit(chat, mid, f"نُزّل الإصدار {r['version']} ويُعاد تشغيل زاجل الآن.", [])
            except (ValueError, OSError) as e:
                TL.edit(chat, mid, "تعذّر التحديث: " + str(e)[:150], [])
    elif kind == "wa":
        try:
            import whatsapp_watch as W
            r = W.digest_now()
            if not r.get("sent"):
                TL.send("لم يُرسل الملخص (الجسر غير متصل أو لا رسائل).", chat)
        except Exception as e:
            TL.send("تعذّر: " + str(e)[:150], chat)
