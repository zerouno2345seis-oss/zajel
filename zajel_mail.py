"""ربط أكثر من بريد إلكتروني (IMAP) للبحث في الرسائل الواردة والصادرة وقراءتها، للقراءة فقط.

كلمات المرور (يُنصح بـ«كلمة مرور التطبيق» لا كلمة الحساب) تُحفظ في سلسلة مفاتيح macOS (Keychain) لا في ملف.
لا يُرسل هذا الملف ولا يحذف ولا ينقل أي رسالة: كل الفتح بوضع القراءة (readonly) وجلب الرسائل بـ BODY.PEEK فلا تتغير علامة «مقروء».
"""
from __future__ import annotations

import email
import email.header
import email.utils
import imaplib
import json
import re
import socket
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = Path(".")
LOCK = threading.Lock()
SERVICE = "zajel-mail"
TIMEOUT = 25

PRESETS = {
    "gmail.com": ("imap.gmail.com", "جيميل: يلزم تفعيل التحقق بخطوتين ثم إنشاء «كلمة مرور تطبيق» من حساب Google"),
    "googlemail.com": ("imap.gmail.com", ""),
    "outlook.com": ("outlook.office365.com", "أوتلوك: قد يلزم تفعيل IMAP وكلمة مرور تطبيق"),
    "hotmail.com": ("outlook.office365.com", ""),
    "live.com": ("outlook.office365.com", ""),
    "icloud.com": ("imap.mail.me.com", "آي كلاود: أنشئ «كلمة مرور خاصة بالتطبيق» من appleid.apple.com"),
    "me.com": ("imap.mail.me.com", ""),
    "yahoo.com": ("imap.mail.yahoo.com", "ياهو: يلزم إنشاء كلمة مرور تطبيق"),
}


def init(data_dir):
    global DATA
    DATA = Path(data_dir)


def _file():
    return DATA / "mail_accounts.json"


def _load():
    try:
        return json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(rows):
    _file().write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def _kc_get(addr):
    r = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", SERVICE, "-a", addr, "-w"], capture_output=True, text=True, timeout=10)
    return r.stdout.rstrip("\n") if r.returncode == 0 else ""


def _kc_set(addr, pw):
    r = subprocess.run(["/usr/bin/security", "add-generic-password", "-U", "-s", SERVICE, "-a", addr, "-w", pw], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise ValueError("تعذر حفظ كلمة المرور في سلسلة المفاتيح.")


def _kc_del(addr):
    subprocess.run(["/usr/bin/security", "delete-generic-password", "-s", SERVICE, "-a", addr], capture_output=True, timeout=10)


def public(a):
    return {"email": a["email"], "host": a["host"], "label": a.get("label", ""), "gmail": a["host"] == "imap.gmail.com"}


def accounts():
    return [public(a) for a in _load()]


def hint_for(addr):
    dom = addr.split("@")[-1].lower()
    h = PRESETS.get(dom)
    return {"host": h[0] if h else "", "hint": h[1] if h else "بريد آخر: اكتب عنوان خادم IMAP (مثل imap.example.com)."}


def _connect(a):
    socket.setdefaulttimeout(TIMEOUT)
    pw = _kc_get(a["email"])
    if not pw:
        raise ValueError("لا توجد كلمة مرور محفوظة لهذا الحساب؛ أعد ربطه.")
    M = imaplib.IMAP4_SSL(a["host"], 993)
    try:
        M.login(a["email"], pw)
    except imaplib.IMAP4.error as e:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass
        raise ValueError("رفض الخادم الدخول (تحقق من كلمة مرور التطبيق وتفعيل IMAP): " + str(e)[:120])
    return M


def add(addr, password, host="", label=""):
    addr = (addr or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr):
        raise ValueError("عنوان بريد غير صالح.")
    host = (host or hint_for(addr)["host"]).strip()
    if not re.match(r"^[A-Za-z0-9.-]+$", host):
        raise ValueError("اكتب خادم IMAP صحيحًا.")
    if not password:
        raise ValueError("أدخل كلمة مرور التطبيق.")
    a = {"email": addr, "host": host, "label": (label or "").strip()[:40]}
    M = _connect_with(a, password)       # يختبر الدخول قبل الحفظ
    try:
        M.logout()
    except Exception:  # noqa: BLE001
        pass
    _kc_set(addr, password)
    with LOCK:
        rows = [r for r in _load() if r["email"] != addr] + [a]
        _save(rows)
    return accounts()


def _connect_with(a, pw):
    socket.setdefaulttimeout(TIMEOUT)
    M = imaplib.IMAP4_SSL(a["host"], 993)
    try:
        M.login(a["email"], pw)
    except imaplib.IMAP4.error as e:
        raise ValueError("رفض الخادم الدخول (تحقق من كلمة مرور التطبيق وتفعيل IMAP): " + str(e)[:120])
    return M


def remove(addr):
    addr = (addr or "").strip().lower()
    with LOCK:
        _save([r for r in _load() if r["email"] != addr])
    _kc_del(addr)
    return accounts()


def _dec(v):
    if not v:
        return ""
    out = []
    for part, enc in email.header.decode_header(v):
        out.append(part.decode(enc or "utf-8", "replace") if isinstance(part, bytes) else part)
    return " ".join(out).strip()


def _folders(M):
    """يعيد {'inbox': 'INBOX', 'sent': '...'}؛ المجلد المرسل يُعرف بعلامة \\Sent أو باسمه."""
    sent = ""
    typ, data = M.list()
    for raw in data or []:
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        m = re.match(r'\((.*?)\) "(.*)" (.+)$', line)
        if not m:
            continue
        flags, name = m.group(1), m.group(3).strip().strip('"')
        if "\\Sent" in flags or re.search(r"(^|/)(sent|sent items|sent mail|المرسل|البريد المرسل)$", name, re.I):
            sent = name
            if "\\Sent" in flags:
                break
    return {"inbox": "INBOX", "sent": sent}


def _search_one(a, query, where, days, limit):
    out, errors = [], ""
    try:
        M = _connect(a)
    except Exception as e:  # noqa: BLE001
        return [], f"{a['email']}: {e}"
    try:
        fol = _folders(M)
        targets = []
        if where in ("all", "inbox"):
            targets.append(("inbox", fol["inbox"]))
        if where in ("all", "sent") and fol["sent"]:
            targets.append(("sent", fol["sent"]))
        gmail = a["host"] == "imap.gmail.com"
        for kind, name in targets:
            typ, _ = M.select(f'"{name}"', readonly=True)
            if typ != "OK":
                continue
            q = query.strip()
            if gmail and q:
                crit = ["X-GM-RAW", q.encode("utf-8")] + (["SINCE", _since(days)] if days else [])
                typ, data = M.uid("SEARCH", "CHARSET", "UTF-8", *crit)
            else:
                crit = (["TEXT", q.encode("utf-8")] if q else ["ALL"]) + (["SINCE", _since(days)] if days else [])
                typ, data = M.uid("SEARCH", "CHARSET", "UTF-8", *crit)
            if typ != "OK" or not data or not data[0]:
                continue
            uids = data[0].split()[-limit:][::-1]
            for u in uids:
                typ, msg = M.uid("FETCH", u, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
                if typ != "OK" or not msg or not isinstance(msg[0], tuple):
                    continue
                h = email.message_from_bytes(msg[0][1])
                d = email.utils.parsedate_to_datetime(h["Date"]) if h["Date"] else None
                out.append({"account": a["email"], "folder": kind, "folder_name": name, "uid": u.decode(), "from": _dec(h["From"]), "to": _dec(h["To"]),
                            "subject": _dec(h["Subject"]) or "(بلا عنوان)", "ts": int(d.timestamp()) if d else 0})
    except Exception as e:  # noqa: BLE001
        errors = f"{a['email']}: {e}"
    finally:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass
    return out, errors


def _since(days):
    import datetime as dt
    d = dt.date.today() - dt.timedelta(days=int(days))
    return d.strftime("%d-%b-%Y")


def search(query, account="", where="all", days=0, limit=30):
    where = where if where in ("all", "inbox", "sent") else "all"
    limit = max(1, min(100, int(limit or 30)))
    rows = [a for a in _load() if not account or a["email"] == account]
    if not rows:
        raise ValueError("لم تربط أي بريد بعد.")
    results, errs = [], []
    with ThreadPoolExecutor(max_workers=min(4, len(rows))) as pool:
        for items, err in pool.map(lambda a: _search_one(a, query or "", where, days, limit), rows):
            results += items
            if err:
                errs.append(err)
    results.sort(key=lambda r: -r["ts"])
    return {"results": results[:limit * 2], "errors": errs}


def read(account, folder_name, uid, max_chars=20000):
    a = next((r for r in _load() if r["email"] == account), None)
    if not a:
        raise ValueError("حساب غير معروف.")
    M = _connect(a)
    try:
        typ, _ = M.select(f'"{folder_name}"', readonly=True)
        if typ != "OK":
            raise ValueError("تعذر فتح المجلد.")
        typ, msg = M.uid("FETCH", str(uid), "(BODY.PEEK[])")
        if typ != "OK" or not msg or not isinstance(msg[0], tuple):
            raise ValueError("الرسالة غير موجودة.")
        m = email.message_from_bytes(msg[0][1])
        text, atts = "", []
        for part in m.walk():
            if part.get_content_maintype() == "multipart":
                continue
            fn = part.get_filename()
            if fn:
                atts.append(_dec(fn))
            elif part.get_content_type() == "text/plain" and not text:
                text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
            elif part.get_content_type() == "text/html" and not text:
                html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html)))
        return {"from": _dec(m["From"]), "to": _dec(m["To"]), "subject": _dec(m["Subject"]), "date": m["Date"] or "", "text": text.strip()[:max_chars], "attachments": atts}
    finally:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass
