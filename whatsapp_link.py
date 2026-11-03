"""الوصل مع واتساب: جسر MCP محلي (whatsapp-mcp) يعمل على هذا الجهاز وحده.
- لا يُعرَض للمساعد إلا ما في القائمة البيضاء أدناه؛ الحذف والحظر وإدارة المجموعات والخصوصية لا يصلها المساعد أبدًا.
- القراءة تُنفَّذ مباشرة، والإرسال أحمر ينتظر موافقتك في زاجل (انظر agent_tools)."""
import json
import os
import urllib.error
import urllib.request

URL = os.environ.get("PB_WA_URL", "http://127.0.0.1:8765/mcp")
ALLOWED = {"get_status", "list_chats", "list_messages", "search_contacts", "list_groups", "send_message", "send_reply"}
MAX_CHARS = 12000
_HEAD = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def _post(body, sid=""):
    h = dict(_HEAD)
    if sid:
        h["Mcp-Session-Id"] = sid
    req = urllib.request.Request(URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
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


def call(name, args=None):
    if name not in ALLOWED:
        raise ValueError("هذه الأداة غير متاحة للمساعد.")
    try:
        sid, _ = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "zajel", "version": "1"}}})
        _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
        _, raw = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}, sid)
    except (urllib.error.URLError, OSError) as exc:
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
