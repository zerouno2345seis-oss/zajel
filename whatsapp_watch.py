"""مراقب واتساب في زاجل: ينظر في الرسائل الجديدة كل دقيقة، ويُنبّهك في تيليجرام بما يهمّك، ويرسل تقريرًا صباحيًا مرتّبًا.
- محلي بالكامل بلا ذكاء اصطناعي: الأهمية بقواعد واضحة (أشخاص مهمّون، كلمات، ألفاظ استعجال، سؤال في محادثة فردية).
- لا يرسل شيئًا إلى واتساب أبدًا؛ يقرأ فقط ثم يكتب إلى تيليجرام عندك.
- أول تشغيل يتجاهل ما وصل قبله (خط أساس) فلا يُغرقك بإشعارات قديمة.
- ينتظر ما يصل في ساعات الهدوء إلى التقرير الصباحي، وهو يعمل ما دام زاجل مفتوحًا."""
import datetime as dt
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

import whatsapp_link as WL

DATA = None
LOCK = threading.RLock()
_stop = threading.Event()
_thread = None
STATE = {"last_poll": 0, "error": "", "alerts_sent": 0}
POLL_SECS, MAX_SEEN, MAX_ALERTS_PER_POLL = 60, 3000, 8
DEFAULTS = {"enabled": False, "vip": [], "keywords": [], "alert_groups": False, "quiet_from": 23, "quiet_to": 6,
            "digest": False, "digest_hour": 7, "digest_last": "", "started": "", "seen": [],
            "templates": [{"id": "t1", "name": "استلام", "text": "وصلتني رسالتك، شكرًا لك."},
                          {"id": "t2", "name": "لاحقًا", "text": "سأرد عليك لاحقًا بإذن الله."},
                          {"id": "t3", "name": "جزاك الله", "text": "جزاك الله خيرًا يا {الاسم}."}]}
URGENT = ("عاجل", "ضروري", "مهم", "بسرعة", "الآن", "urgent", "asap", "emergency", "طارئ")


def init(data_dir):
    global DATA
    DATA = Path(data_dir)
    start()


def _cfg():
    try:
        d = json.loads((DATA / "whatsapp.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {**DEFAULTS, **d}


def _save(d):
    with LOCK:
        c = {**_cfg(), **d}
        p = DATA / "whatsapp.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, p)
        return c


# ---------- التقييم ----------
def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def score(m, c):
    """يعيد (الدرجة، الأسباب) أو None إن كانت الرسالة لا تُعدّ أصلًا (منّي، حالات، قنوات)."""
    jid = m.get("jid", "")
    if m.get("me") or jid.startswith("status@") or jid.endswith(("@newsletter", "@broadcast")):
        return None
    group = jid.endswith("@g.us")
    who = _norm(m.get("chat", "") + " " + m.get("sender", "") + " " + jid)
    text = _norm(m.get("text", ""))
    pts, why = 0, []
    if any(_norm(v) and _norm(v) in who for v in c["vip"]):
        pts += 5; why.append("شخص مهم")
    if any(_norm(k) and _norm(k) in text for k in c["keywords"]):
        pts += 3; why.append("كلمة مراقبة")
    if not group:
        pts += 2
        if "؟" in text or "?" in text:
            pts += 1; why.append("سؤال")
        if any(u in text for u in URGENT):
            pts += 2; why.append("استعجال")
        if m.get("kind") == "audio":
            pts += 1; why.append("رسالة صوتية")
    else:
        pts -= 1
        if any(u in text for u in URGENT):
            pts += 1; why.append("استعجال")
    return pts, why


def _alertworthy(m, c):
    s = score(m, c)
    if not s:
        return None
    pts, why = s
    group = m.get("jid", "").endswith("@g.us")
    if group and not c["alert_groups"] and "شخص مهم" not in why and "كلمة مراقبة" not in why:
        return None
    return s if ("شخص مهم" in why or "كلمة مراقبة" in why or "استعجال" in why) else None


def _quiet(c, now=None):
    h = (now or dt.datetime.now()).hour
    a, b = int(c["quiet_from"]), int(c["quiet_to"])
    if a == b:
        return False
    return (h >= a or h < b) if a > b else (a <= h < b)


def _short(t, n=220):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    return t if len(t) <= n else t[:n] + "…"


def _line(m):
    body = _short(m["text"]) if m["kind"] == "text" or m["text"] else f"[{m['kind']}]"
    if m["kind"] != "text" and m["text"] and not m["text"].startswith("["):
        body = f"[{m['kind']}] {body}"
    who = m["chat"] if not m["jid"].endswith("@g.us") else f"{m['sender']} في {m['chat']}"
    return who, body


def _tg(text):
    import telegram_link
    c = telegram_link._cfg()
    if c["enabled"] and c["chat_id"]:
        telegram_link.send(text)
        return True
    return False


# ---------- التنبيه ----------
def poll_once(now=None):
    """دورة واحدة. تعيد عدد التنبيهات المرسلة (للاختبار)."""
    c = _cfg()
    if not (c["enabled"] or c["digest"]):
        return 0
    now = now or dt.datetime.now()
    msgs = WL.messages_since((now - dt.timedelta(hours=26)).strftime("%Y-%m-%d"), 150)
    seen = set(c["seen"])
    if not c["started"]:                      # خط الأساس: لا إشعار بما سبق
        _save({"started": now.strftime("%Y-%m-%d %H:%M:%S"), "seen": [m["mid"] for m in msgs if m["mid"]][-MAX_SEEN:]})
        return 0
    fresh = [m for m in msgs if m["mid"] and m["mid"] not in seen and m["ts"] >= c["started"]]
    sent = 0
    if c["enabled"] and not _quiet(c, now):
        hits = [(m, s) for m in fresh for s in [_alertworthy(m, c)] if s]
        for m, (_, why) in hits[:MAX_ALERTS_PER_POLL]:
            who, body = _line(m)
            if _tg(f"📩 واتساب — {who}\n{body}\n({'، '.join(why)})"):
                sent += 1
        if len(hits) > MAX_ALERTS_PER_POLL:
            _tg(f"و{len(hits) - MAX_ALERTS_PER_POLL} رسائل مهمة أخرى. افتح واتساب أو اطلب التقرير.")
    ids = (c["seen"] + [m["mid"] for m in fresh])[-MAX_SEEN:]
    _save({"seen": ids})
    STATE["alerts_sent"] += sent
    return sent


# ---------- التقرير ----------
def build_digest(now=None, hours=24):
    c = _cfg()
    now = now or dt.datetime.now()
    since = (now - dt.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    msgs = [m for m in WL.messages_since((now - dt.timedelta(hours=hours + 2)).strftime("%Y-%m-%d"), 300) if m["ts"] >= since]
    real = [m for m in msgs if score(m, c) is not None]
    if not real:
        return "☀️ تقرير واتساب: لا رسائل جديدة في آخر ٢٤ ساعة."
    chats = {}
    for m in msgs:
        chats.setdefault(m["jid"], []).append(m)
    ranked = sorted(((score(m, c)[0], m) for m in real), key=lambda x: (-x[0], x[1]["ts"]))
    top = [(p, m) for p, m in ranked if p >= 2][:6]
    lines = [f"☀️ تقرير واتساب — {len(real)} رسالة واردة من {len({m['jid'] for m in real})} محادثة (آخر {hours} ساعة)", ""]
    if top:
        lines.append("الأهم:")
        for i, (p, m) in enumerate(top, 1):
            who, body = _line(m)
            lines.append(f"{i}) {who}: {body}")
    pending = []
    for jid, ms in chats.items():
        if jid.endswith(("@g.us", "@newsletter", "@broadcast")) or jid.startswith("status@"):
            continue
        ms.sort(key=lambda x: x["ts"])
        if not ms[-1]["me"]:
            pending.append(ms[-1]["chat"])
    if pending:
        lines += ["", "بلا ردّ منك: " + "، ".join(dict.fromkeys(pending))[:300]]
    busy = sorted(((len([m for m in ms if not m["me"]]), ms[0]["chat"]) for jid, ms in chats.items()
                   if not jid.startswith("status@") and not jid.endswith(("@newsletter", "@broadcast"))), reverse=True)[:3]
    if busy and busy[0][0] > 1:
        lines += ["", "الأنشط: " + "، ".join(f"{n} ({k})" for k, n in busy if k > 1)]
    return "\n".join(lines)


def digest_now():
    text = build_digest()
    return {"sent": _tg(text), "text": text}


def _maybe_digest(now):
    c = _cfg()
    today = now.strftime("%Y-%m-%d")
    if c["digest"] and now.hour >= int(c["digest_hour"]) and c["digest_last"] != today:
        _save({"digest_last": today})
        _tg(build_digest(now))


# ---------- الحلقة ----------
def _loop():
    while not _stop.wait(POLL_SECS):
        try:
            if DATA is None:
                continue
            now = dt.datetime.now()
            poll_once(now)
            _maybe_digest(now)
            STATE.update(last_poll=time.time(), error="")
        except Exception as exc:       # لا تُسقط الحلقة أبدًا (الجسر قد يكون مغلقًا)
            STATE["error"] = str(exc)[:200]


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()


def status():
    c = _cfg()
    return {"enabled": c["enabled"], "digest": c["digest"], "digest_hour": c["digest_hour"], "vip": c["vip"], "keywords": c["keywords"],
            "alert_groups": c["alert_groups"], "quiet": f"{c['quiet_from']}–{c['quiet_to']}", "baseline": bool(c["started"]),
            "last_poll_secs_ago": int(time.time() - STATE["last_poll"]) if STATE["last_poll"] else None, "error": STATE["error"],
            "alerts_sent": STATE["alerts_sent"], "templates": len(c["templates"])}


def configure(b):
    d = {}
    for k in ("enabled", "digest", "alert_groups"):
        if k in b:
            d[k] = bool(b[k])
    for k in ("vip", "keywords"):
        if k in b:
            v = b[k] if isinstance(b[k], list) else re.split(r"[،,\n]", str(b[k]))
            d[k] = [str(x).strip() for x in v if str(x).strip()][:40]
    for k, lo, hi in (("digest_hour", 0, 23), ("quiet_from", 0, 23), ("quiet_to", 0, 23)):
        if k in b:
            d[k] = max(lo, min(int(b[k]), hi))
    if d.get("enabled") or d.get("digest"):
        if not _cfg()["started"]:
            d["started"] = ""       # يُنشأ خط الأساس عند أول دورة
    _save(d)
    return status()


# ---------- الردود الجاهزة ----------
def templates():
    return _cfg()["templates"]


def save_template(name, text):
    name, text = str(name or "").strip()[:40], str(text or "").strip()[:1000]
    if not name or not text:
        raise ValueError("اكتب اسمًا ونصًّا للرد الجاهز.")
    ts = [t for t in templates() if t["name"] != name]
    if len(ts) >= 30:
        raise ValueError("بلغت الحد الأقصى (٣٠ ردًّا جاهزًا).")
    ts.append({"id": uuid.uuid4().hex[:6], "name": name, "text": text})
    _save({"templates": ts})
    return ts


def delete_template(name):
    ts = templates()
    keep = [t for t in ts if t["name"] != str(name).strip() and t["id"] != str(name).strip()]
    if len(keep) == len(ts):
        raise ValueError("لا يوجد رد جاهز بهذا الاسم.")
    _save({"templates": keep})
    return keep


def render_template(name, values=None):
    t = next((x for x in templates() if x["name"] == str(name).strip() or x["id"] == str(name).strip()), None)
    if not t:
        raise ValueError("لا يوجد رد جاهز بهذا الاسم.")
    out = t["text"]
    for k, v in (values or {}).items():
        out = out.replace("{" + str(k) + "}", str(v))
    out = re.sub(r"\s*\{[^}]*\}", "", out)       # متغير بلا قيمة يُحذف بدل أن يُرسل خامًا
    return out.strip()
