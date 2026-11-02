"""كيندل الحديث بالكابل عبر «لغة المشغّلات» (MTP) بأدوات libmtp من Homebrew.
لا تُستدعى الأدوات إلا إذا وُجد جهاز من صنع أمازون على USB، حتى لا تقترب من الهاتف."""
from __future__ import annotations

import os
import posixpath
import re
import shutil
import subprocess
import threading
import time

BIN = "/opt/homebrew/bin"
AMAZON_VENDOR = 0x1949
ENV = {**os.environ, "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}
LOCK = threading.Lock()  # جهاز MTP لا يقبل إلا جلسة واحدة في الوقت نفسه
_cache = {"t": 0.0, "v": None, "tree": None, "tt": 0.0}


def _tool(name):
    return shutil.which(name) or os.path.join(BIN, name)


def available():
    return os.path.exists(_tool("mtp-files"))


def present():
    """هل كيندل (أمازون) موصول بـUSB؟ — فحص خفيف من سجل USB في النظام دون فتح الجهاز."""
    if time.time() - _cache["t"] < 4:
        return _cache["v"]
    v = None
    try:
        out = subprocess.run(["ioreg", "-p", "IOUSB", "-l", "-w0"], capture_output=True, text=True, timeout=8).stdout
        for block in out.split("+-o ")[1:]:
            if re.search(r'"idVendor" = %d\b' % AMAZON_VENDOR, block):
                name = re.search(r'"USB Product Name" = "([^"]*)"', block)
                v = {"name": (name.group(1) if name else "Kindle"), "mtp": available()}
                break
    except Exception:
        pass
    _cache.update(t=time.time(), v=v)
    return v


def _run(args, timeout=120):
    if not present():
        raise ValueError("وصّل الكيندل بالكابل وافتح قفل شاشته.")
    with LOCK:
        r = subprocess.run([_tool(args[0]), *args[1:]], capture_output=True, text=True, timeout=timeout, env=ENV)
    out = (r.stdout or "") + (r.stderr or "")
    if "No Devices" in out or "No devices" in out or "no devices" in out:
        raise ValueError("الكيندل موصول لكنه لا يستجيب؛ افتح قفل شاشته ثم أعد المحاولة.")
    return r.stdout or ""


def _tree(force=False):
    """{id: (name, parent_id, is_dir, size)} للمجلدات والملفات (مع ذاكرة 20 ثانية)."""
    if not force and _cache["tree"] and time.time() - _cache["tt"] < 20:
        return _cache["tree"]
    nodes = {}
    stack = []  # (level, id)
    for line in _run(["mtp-folders"]).splitlines():
        m = re.match(r"^(\d+)\t( *)(.*)$", line)
        if not m:
            continue
        fid, level, name = int(m.group(1)), len(m.group(2)) // 2, m.group(3)
        while stack and stack[-1][0] >= level:
            stack.pop()
        nodes[fid] = (name, stack[-1][1] if stack else 0, True, None)
        stack.append((level, fid))
    cur = {}
    for line in _run(["mtp-files"], 300).splitlines() + ["File ID: 0"]:
        line = line.strip()
        if line.startswith("File ID:"):
            if cur.get("id") and cur.get("name"):
                nodes[cur["id"]] = (cur["name"], cur.get("parent", 0), False, cur.get("size", 0))
            cur = {"id": int(line.split(":", 1)[1])}
        elif line.startswith("Filename:"):
            cur["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("File size"):
            m = re.match(r"File size (\d+)", line)
            cur["size"] = int(m.group(1)) if m else 0
        elif line.startswith("Parent ID:"):
            cur["parent"] = int(line.split(":", 1)[1])
    _cache.update(tree=nodes, tt=time.time())
    return nodes


def _path_of(nodes, fid):
    parts = []
    while fid and fid in nodes and len(parts) < 40:
        parts.append(nodes[fid][0])
        fid = nodes[fid][1]
    return "/" + "/".join(reversed(parts))


def _find(path, nodes=None):
    nodes = nodes or _tree()
    path = "/" + (path or "").strip("/")
    if path == "/":
        return 0
    for fid in nodes:
        if _path_of(nodes, fid) == path:
            return fid
    raise ValueError("غير موجود في الكيندل.")


def browse(path):
    nodes = _tree()
    pid = _find(path, nodes)
    out = [{"name": n, "path": _path_of(nodes, fid), "is_dir": d, "size": None if d else s, "mod": 0, "chg": 0, "is_archive": False}
           for fid, (n, p, d, s) in nodes.items() if p == pid]
    out.sort(key=lambda e: (not e["is_dir"], e["name"].casefold()))
    return {"path": "/" + (path or "").strip("/"), "entries": out}


def stat(path):
    nodes = _tree()
    fid = _find(path, nodes)
    if not fid:
        return {"is_dir": True, "size": 0}
    n = nodes[fid]
    return {"is_dir": n[2], "size": n[3] or 0}


def pull(path, dest):
    nodes = _tree()
    fid = _find(path, nodes)
    if nodes[fid][2]:  # مجلد: كل ما تحته
        os.makedirs(dest, exist_ok=True)
        for e in browse(path)["entries"]:
            pull(e["path"], os.path.join(dest, e["name"]))
        return dest
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    _run(["mtp-getfile", str(fid), dest], 3600)
    if not os.path.exists(dest):
        raise ValueError("تعذّر الجلب من الكيندل.")
    return dest


def push(local, dest_dir, name=None):
    """يضع ملفًا في مجلد داخل الكيندل (مثل /documents)."""
    name = name or os.path.basename(local)
    remote = "/" + "/".join(x for x in (dest_dir.strip("/"), name) if x)
    _run(["mtp-sendfile", str(local), remote], 3600)
    _tree(force=True)
    try:
        _find(remote)
    except ValueError:
        raise ValueError("لم يقبل الكيندل الملف.")
    return name


def delete(path):
    fid = _find(path)
    _run(["mtp-delfile", "-n", str(fid)], 60)
    _tree(force=True)
