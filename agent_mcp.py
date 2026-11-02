#!/usr/bin/env python3
"""
خادم MCP صغير لبرنامج «زاجل» عبر بروتوكول stdio و JSON-RPC 2.0.
يغلّف أدوات زاجل لتمكين الوكيل الذكي من استكشاف الأدوات واستدعائها
باستخدام مكتبة بايثون 3.9 القياسية فقط وبلا أي مكتبات خارجية.
"""

import sys
import os
import json
import urllib.request
import urllib.error


def log_diag(msg: str):
    """طباعة رسائل التشخيص إلى stderr فقط."""
    sys.stderr.write(f"[zajel-mcp] {msg}\n")
    sys.stderr.flush()


def send_response(response: dict):
    """إرسال رد JSON-RPC سطرًا بسطر عبر stdout مع تفريغ فوري."""
    line = json.dumps(response, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def send_result(req_id, result):
    """إرسال رد بنتيجة ناجحة."""
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result
    })


def send_error(req_id, code: int, message: str, data=None):
    """إرسال رد خطأ بتنسيق JSON-RPC 2.0."""
    err = {
        "code": code,
        "message": message
    }
    if data is not None:
        err["data"] = data
    send_response({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": err
    })


def get_zajel_credentials():
    """
    قراءة مفتاح العميل ورقم المنفذ مباشرة من مجلد البيانات في كل استدعاء،
    دون تخزينهما في الذاكرة لتفادي عدم تطابقهما عند إعادة تشغيل زاجل.
    """
    data_dir = os.environ.get("PB_DATA")
    if not data_dir:
        data_dir = os.path.expanduser("~/Library/Application Support/Phone Backup")

    key_file = os.path.join(data_dir, ".agent_key")
    port_file = os.path.join(data_dir, ".zajel_port")

    if not os.path.exists(key_file):
        raise FileNotFoundError(f"ملف المفتاح السري .agent_key غير موجود في: {data_dir}")
    if not os.path.exists(port_file):
        raise FileNotFoundError(f"ملف المنفذ .zajel_port غير موجود في: {data_dir}")

    with open(key_file, "r", encoding="utf-8") as f:
        key = f.read().strip()
    with open(port_file, "r", encoding="utf-8") as f:
        port = f.read().strip()

    if not key:
        raise ValueError("ملف المفتاح السري .agent_key فارغ.")
    if not port:
        raise ValueError("ملف المنفذ .zajel_port فارغ.")

    return key, port


def extract_http_error(err: urllib.error.HTTPError) -> str:
    """استخراج رسالة الخطأ من جسم رد HTTP إذا كان بتنسيق JSON."""
    try:
        body = err.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        if isinstance(data, dict) and "error" in data:
            return str(data["error"])
        return body if body else str(err)
    except Exception:
        return str(err)


def handle_initialize(params: dict) -> dict:
    """معالجة استدعاء التهيئة initialize."""
    protocol_version = None
    if isinstance(params, dict):
        protocol_version = params.get("protocolVersion")
    if not protocol_version:
        protocol_version = "2024-11-05"

    return {
        "protocolVersion": protocol_version,
        "capabilities": {
            "tools": {}
        },
        "serverInfo": {
            "name": "zajel",
            "version": "1.0"
        }
    }


def handle_tools_list() -> dict:
    """معالجة استدعاء قائمة الأدوات tools/list."""
    key, port = get_zajel_credentials()
    url = f"http://127.0.0.1:{port}/api/agent/tools"

    req = urllib.request.Request(
        url,
        headers={"X-Zajel-Key": key},
        method="GET"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw_body = resp.read().decode("utf-8")
            data = json.loads(raw_body)
    except urllib.error.HTTPError as e:
        err_msg = extract_http_error(e)
        raise RuntimeError(f"خطأ HTTP من زاجل ({e.code}): {err_msg}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"تعذر الاتصال بزاجل على المنفذ {port}: {e.reason}")

    raw_tools = data.get("tools", [])
    cleaned_tools = []
    for t in raw_tools:
        if isinstance(t, dict):
            cleaned_tools.append({
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "inputSchema": t.get("inputSchema", {})
            })

    return {"tools": cleaned_tools}


def handle_tools_call(params: dict) -> dict:
    """معالجة استدعاء أداة tools/call."""
    if not isinstance(params, dict):
        return {
            "content": [{"type": "text", "text": "خطأ: المعاملات المرسلة ليست كائن JSON صالح."}],
            "isError": True
        }

    tool_name = params.get("name")
    tool_args = params.get("arguments", {})

    if not tool_name:
        return {
            "content": [{"type": "text", "text": "خطأ: لم يتم تحديد اسم الأداة المراد استدعاؤها."}],
            "isError": True
        }

    try:
        key, port = get_zajel_credentials()
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"تعذر قراءة بيانات اتصال زاجل: {e}"}],
            "isError": True
        }

    url = f"http://127.0.0.1:{port}/api/agent/call"
    payload = json.dumps({"tool": tool_name, "args": tool_args}).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-Zajel-Key": key
    }

    zajel_agent = os.environ.get("ZAJEL_AGENT")
    if zajel_agent:
        headers["X-Zajel-Agent"] = zajel_agent

    zajel_job = os.environ.get("ZAJEL_JOB")
    if zajel_job:
        headers["X-Zajel-Job"] = zajel_job

    req = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw_body = resp.read().decode("utf-8")
            resp_json = json.loads(raw_body)
    except urllib.error.HTTPError as e:
        err_msg = extract_http_error(e)
        return {
            "content": [{"type": "text", "text": f"خطأ من خادم زاجل ({e.code}): {err_msg}"}],
            "isError": True
        }
    except urllib.error.URLError as e:
        return {
            "content": [{"type": "text", "text": f"تعذر الاتصال بخادم زاجل: {e.reason}"}],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"حدث خطأ أثناء الاتصال بزاجل: {e}"}],
            "isError": True
        }

    formatted_text = json.dumps(resp_json, ensure_ascii=False, separators=(",", ":"))
    is_error = False
    if isinstance(resp_json, dict):
        if "error" in resp_json or "refused" in resp_json:
            is_error = True

    return {
        "content": [
            {
                "type": "text",
                "text": formatted_text
            }
        ],
        "isError": is_error
    }


def process_message(line: str):
    """تحليل رسالة JSON-RPC واردة وتوجيهها للدالة المناسبة."""
    try:
        msg = json.loads(line)
    except Exception as e:
        log_diag(f"خطأ في تحليل JSON: {e}")
        send_error(None, -32700, f"خطأ في تحليل صيغة JSON: {e}")
        return

    if not isinstance(msg, dict):
        return

    method = msg.get("method")
    has_id = "id" in msg
    req_id = msg.get("id")

    # notifications/* أو أي إشعار بدون id يتم تجاهله بلا رد
    if method and method.startswith("notifications/"):
        return

    if not has_id:
        return

    params = msg.get("params") or {}

    if method == "initialize":
        result = handle_initialize(params)
        send_result(req_id, result)
    elif method == "ping":
        send_result(req_id, {})
    elif method == "tools/list":
        try:
            result = handle_tools_list()
            send_result(req_id, result)
        except Exception as e:
            log_diag(f"خطأ tools/list: {e}")
            send_error(req_id, -32000, f"تعذر جلب قائمة الأدوات من زاجل: {e}")
    elif method == "tools/call":
        result = handle_tools_call(params)
        send_result(req_id, result)
    else:
        send_error(req_id, -32601, f"الطريقة غير موجودة: {method}")


def main():
    """حلقة قراءة الرسائل من stdin ومعالجتها سطرًا بسطر."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            process_message(line)
        except Exception as e:
            log_diag(f"خطأ غير متوقع في المعالجة: {e}")


if __name__ == "__main__":
    main()
