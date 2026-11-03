"""الوصل مع واتساب: جسر MCP محلي (whatsapp-mcp) يعمل على هذا الجهاز وحده.
- لا يُعرَض للمساعد إلا ما في القائمة البيضاء أدناه؛ الحذف والحظر وإدارة المجموعات والخصوصية لا يصلها المساعد أبدًا.
- القراءة تُنفَّذ مباشرة، والإرسال أحمر ينتظر موافقتك في زاجل (انظر agent_tools)."""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

URL = os.environ.get("PB_WA_URL", "http://127.0.0.1:8765/mcp")
ALLOWED = {"get_status", "list_chats", "list_messages", "search_contacts", "list_groups", "send_message", "send_reply", "send_file", "download_media"}
# المجلد الوحيد الذي يسمح الجسر بإرسال الملفات منه واستقبالها فيه
MEDIA_ROOT = Path(os.environ.get("WHATSAPP_MCP_MEDIA_ROOT") or Path.home() / ".config/opencode/whatsapp-store/uploads")
MAX_CHARS = 12000
_HEAD = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def _post(body, sid="", timeout=60):
    h = dict(_HEAD)
    if sid:
        h["Mcp-Session-Id"] = sid
    req = urllib.request.Request(URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.headers.get("Mcp-Session-Id", ""), r.read().decode("utf-8", errors="replace")


def parse(text):
    """ردّ الجسر قد يكون JSON مباشرًا أو سطر data من SSE."""
    text = (text or "").strip()
    if not text:
        return {}
    for ln in text.splitlines():
        if ln.startswith("data:"):
            text = ln[5:].strip()
            break
    return json.loads(text)


def call(name, args=None, timeout=60):
    if name not in ALLOWED:
        raise ValueError("هذه الأداة غير متاحة للمساعد.")
    try:
        sid, _ = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "zajel", "version": "1"}}}, timeout=timeout)
        _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid, timeout)
        _, raw = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}, sid, timeout)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ValueError("جسر واتساب لا يستجيب على هذا الجهاز. تأكد أن خدمة whatsapp-mcp تعمل ومقترنة بحسابك.") from exc
    msg = parse(raw)
    if "error" in msg:
        raise ValueError(str(msg["error"].get("message", msg["error"]))[:300])
    res = msg.get("result", {})
    text = "\n".join(c.get("text", "") for c in res.get("content", []) if isinstance(c, dict))
    if res.get("isError"):
        raise ValueError(text[:300] or "فشل الأمر في واتساب.")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n… (قُصّ الناتج؛ ضيّق البحث أو قلّل العدد)"
    return text


_LINE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] Chat: (.*?) From: (.*?): (.*)$")


def parse_messages(text):
    """يحوّل ناتج list_messages (أسطر نصية) إلى قائمة رسائل مرتّبة من الأقدم إلى الأحدث.
    كل رسالة: ts, chat, sender, text, kind (text/image/audio/video/document…), mid, jid, me."""
    out = []
    for ln in (text or "").splitlines():
        m = _LINE.match(ln.strip())
        if not m:
            continue
        ts, chat, sender, rest = m.groups()
        mid = re.search(r"Message ID: (\S+)", rest)
        jid = re.search(r"Chat JID: ([^\]\s]+)", rest)
        kind = re.match(r"\[(image|video|audio|document|sticker|contact|location|poll)\b", rest)
        body = re.sub(r"\s*\[(?:[a-z]+ - )?Message ID:[^\]]*\]\s*$", "", rest).strip()
        out.append({"ts": ts, "chat": chat, "sender": sender, "text": body, "kind": kind.group(1) if kind else "text",
                    "mid": mid.group(1) if mid else "", "jid": jid.group(1) if jid else "", "me": sender == "Me"})
    out.sort(key=lambda x: x["ts"])
    return out


def messages_since(date_str, limit=100, query=""):
    """رسائل من تاريخ معيّن (YYYY-MM-DD) فصاعدًا، مرتبة زمنيًا."""
    args = {"limit": limit, "after": date_str}
    if query:
        args["query"] = query
    return parse_messages(call("list_messages", args))
