"""قسم «الخوادم»: كل ما يستمع الآن على منافذ TCP في هذا الحاسوب (عبر lsof)، مع إيقافه وتشغيله.
- الإيقاف لعمليات المستخدم نفسه فقط، ويُرفض لزاجل نفسه ولخدمات النظام ولما لا يخصه؛ يبدأ بإنهاء لطيف (SIGTERM) ثم قسري عند الطلب.
- أمر كل خادم يُوقَف يُحفظ تلقائيًا (الأمر والمجلد) ليُعاد تشغيله بنقرة؛ وتشغيل أمر جديد يضيفه المستخدم بنفسه من الواجهة فقط.
- حاسوب واحد (هذا الجهاز)."""
import json
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path

DATA = None
LOCK = threading.RLock()
PORT_SELF = 0
PROTECTED_NAMES = {"launchd", "rapportd", "sharingd", "controlcenter", "windowserver", "mdnsresponder", "identityservicesd", "airplayxpchelper", "systemuiserver",
                   "loginwindow", "coreaudiod", "bluetoothd", "configd", "distnoted", "cfprefsd", "usermanagerd", "sshd", "screensharingd", "remoted", "trustd",
                   "airportd", "wifivelocityd", "nsurlsessiond", "networkserviceproxy", "assistantd", "universalaccessd", "knowledge-agent"}
SAFE_PREFIX = ("/System/", "/usr/libexec/", "/usr/sbin/", "/sbin/", "/Library/Apple/")


def init(data_dir, port=0):
    global DATA, PORT_SELF
    DATA = Path(data_dir)
    PORT_SELF = int(port or 0)
    (DATA / "server_logs").mkdir(parents=True, exist_ok=True)


def _run(cmd, timeout=12):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors="replace").stdout
    except Exception:
        return ""


def _defs():
    try:
        return json.loads((DATA / "servers.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_defs(d):
    p = DATA / "servers.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d[-40:], ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _kind(name, cmd, port):
    n = (name + " " + cmd).lower()
    if any(k in n for k in ("postgres", "mysqld", "mariadb", "redis", "mongod", "sqlite", "memcached", "elasticsearch")):
        return "قاعدة بيانات"
    if any(k in n for k in ("node", "npm", "vite", "next", "webpack", "uvicorn", "flask", "django", "python", "ruby", "rails", "php", "http.server", "gunicorn", "deno", "bun")):
        return "تطوير/ويب"
    if any(k in n for k in ("nginx", "httpd", "apache", "caddy")):
        return "خادم ويب"
    if any(k in n for k in ("ollama", "lm studio", "lmstudio", "llama")):
        return "ذكاء اصطناعي"
    return "برنامج"


def listing():
    out = _run(["/usr/sbin/lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-F", "pcLun"])
    procs, cur = {}, None
    for ln in out.splitlines():
        if not ln:
            continue
        t, v = ln[0], ln[1:]
        if t == "p":
            cur = procs.setdefault(int(v), {"pid": int(v), "name": "", "user": "", "uid": -1, "ports": []})
        elif cur is None:
            continue
        elif t == "c":
            cur["name"] = v
        elif t == "L":
            cur["user"] = v
        elif t == "u":
            cur["uid"] = int(v)
        elif t == "n":
            m = re.match(r"^(.*):(\d+)$", v)
            if m:
                port = int(m.group(2))
                local = m.group(1) in ("127.0.0.1", "[::1]", "localhost")
                if not any(x["port"] == port for x in cur["ports"]):
                    cur["ports"].append({"port": port, "local_only": local, "addr": m.group(1)})
    if not procs:
        return []
    ps = _run(["/bin/ps", "-o", "pid=,etime=,%cpu=,rss=,args=", "-p", ",".join(map(str, procs))])
    for ln in ps.splitlines():
        m = re.match(r"\s*(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(.*)$", ln)
        if m and int(m.group(1)) in procs:
            p = procs[int(m.group(1))]
            p["etime"], p["cpu"], p["rss_mb"], p["cmd"] = m.group(2), float(m.group(3)), round(int(m.group(4)) / 1024), m.group(5)
    me = os.getuid()
    rows = []
    for p in procs.values():
        cmd = p.get("cmd", "")
        name = p["name"].replace("\\x20", " ")
        prot = ""
        if p["pid"] == os.getpid() or os.getppid() == p["pid"] or any(x["port"] == PORT_SELF for x in p["ports"]):
            prot = "هذا زاجل نفسه"
        elif p["uid"] != me:
            prot = "تخص النظام أو مستخدمًا آخر"
        elif name.lower() in PROTECTED_NAMES or cmd.startswith(SAFE_PREFIX):
            prot = "خدمة نظام"
        p["name"], p["protected"], p["kind"] = name, prot, _kind(name, cmd, p["ports"][0]["port"] if p["ports"] else 0)
        p["ports"].sort(key=lambda x: x["port"])
        p.setdefault("cmd", "")
        rows.append(p)
    rows.sort(key=lambda x: (bool(x["protected"]), x["ports"][0]["port"] if x["ports"] else 0))
    return rows


def definitions():
    ports_now = {x["port"] for p in listing() for x in p["ports"]}
    return [d | {"running": bool(d.get("port") and d["port"] in ports_now)} for d in _defs()]


def _cwd_of(pid):
    for ln in _run(["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"]).splitlines():
        if ln.startswith("n"):
            return ln[1:]
    return str(Path.home())


def stop(pid, force=False):
    pid = int(pid)
    row = next((p for p in listing() if p["pid"] == pid), None)
    if not row:
        raise ValueError("هذه العملية لم تعد تستمع على منفذ (ربما توقفت).")
    if row["protected"]:
        raise ValueError("لا يمكن إيقافها: " + row["protected"] + ".")
    cwd = _cwd_of(pid)
    with LOCK:
        d = _defs()
        if row["cmd"] and not any(x["cmd"] == row["cmd"] and x["cwd"] == cwd for x in d):
            d.append({"id": uuid.uuid4().hex[:8], "name": f"{row['name']}" + (f" :{row['ports'][0]['port']}" if row["ports"] else ""), "cmd": row["cmd"], "cwd": cwd,
                      "port": row["ports"][0]["port"] if row["ports"] else 0, "saved_from": "stop", "t": time.time()})
            _save_defs(d)
    try:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        return {"stopped": True, "pid": pid}
    for _ in range(30):
        time.sleep(0.2)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return {"stopped": True, "pid": pid, "name": row["name"], "saved_for_restart": True}
    return {"stopped": False, "pid": pid, "note": "لم تُنهِ نفسها بعد؛ اضغط «إيقاف قسري» إن لزم."}


def define(name, cmd, cwd, port=0):
    name, cmd = " ".join(str(name or "").split())[:60], str(cmd or "").strip()
    if not name or not cmd or len(cmd) > 600:
        raise ValueError("اكتب اسمًا وأمر تشغيل.")
    cwd = str(Path(cwd or Path.home()).expanduser())
    if not Path(cwd).is_dir():
        raise ValueError("المجلد غير موجود.")
    with LOCK:
        d = _defs()
        d.append({"id": uuid.uuid4().hex[:8], "name": name, "cmd": cmd, "cwd": cwd, "port": int(port or 0), "saved_from": "user", "t": time.time()})
        _save_defs(d)
    return d[-1]


def forget(sid):
    with LOCK:
        _save_defs([x for x in _defs() if x["id"] != sid])


def start(sid):
    d = next((x for x in _defs() if x["id"] == sid), None)
    if not d:
        raise ValueError("التعريف غير موجود.")
    if d.get("port") and any(x["port"] == d["port"] for p in listing() for x in p["ports"]):
        raise ValueError(f"المنفذ {d['port']} مشغول بعملية تعمل الآن.")
    log = DATA / "server_logs" / f"{sid}.log"
    with open(log, "ab") as fh:
        fh.write(f"\n--- {time.strftime('%F %T')} تشغيل: {d['cmd']}\n".encode())
        p = subprocess.Popen(["/bin/zsh", "-lc", d["cmd"]], cwd=d["cwd"], stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    time.sleep(1.8)
    alive = p.poll() is None
    listening = bool(d.get("port")) and any(x["port"] == d["port"] for pr in listing() for x in pr["ports"])
    if not alive and p.returncode != 0:
        try:
            tail = log.read_text(encoding="utf-8", errors="replace")[-400:]
        except OSError:
            tail = ""
        raise ValueError(f"توقف فور تشغيله (رمز {p.returncode}). {tail}")
    return {"started": True, "pid": p.pid, "listening": listening, "log": str(log)}
