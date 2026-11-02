"""اتصال الهاتف اللاسلكي الدائم لزاجل (يكمّل حارس الواي فاي الموجود).
- الربط بالرمز مرة واحدة (التصحيح اللاسلكي في أندرويد ١١+) فلا حاجة للكابل بعدها.
- إعادة اتصال تلقائية حتى لو تغيّر عنوان الهاتف: خدمات الشبكة (mDNS) ثم مسح الشبكة المحلية بحثًا عن الهاتف نفسه (بالرقم التسلسلي).
لا يمسّ الساعة (يُستثنى كل جهاز is_watch)."""
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ADDR_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}(:\d{2,5})?$")
CODE_RE = re.compile(r"^\d{6}$")
STATE = {"last_try": 0.0, "last_scan": 0.0, "last_note": "", "last_ok": 0.0}
LOCK = threading.Lock()


def _devices(M):
    rows = [l.split() for l in M.adb("devices").stdout.splitlines()[1:] if l.strip()]
    return [r[0] for r in rows if len(r) > 1 and r[1] == "device"]


def _serial_of(M, addr):
    return M.shell("getprop ro.serialno", addr, 8).stdout.strip()


def _local_subnet():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip.rsplit(".", 1)[0]
    except OSError:
        return ""


def mdns_connect_services(M):
    """خدمات الاتصال اللاسلكي المعلنة على الشبكة: [(الاسم, ip:port)]"""
    out = M.adb("mdns", "services", timeout=10).stdout
    res = []
    for ln in out.splitlines():
        m = re.search(r"(\S+)\s+_adb-tls-connect\._tcp\.?\s+((?:\d{1,3}\.){3}\d{1,3}:\d+)", ln)
        if m:
            res.append((m.group(1), m.group(2)))
    return res


def scan_subnet(M, port=5555):
    base = _local_subnet()
    if not base:
        return []

    def probe(i):
        s = socket.socket()
        s.settimeout(0.4)
        try:
            return f"{base}.{i}" if s.connect_ex((f"{base}.{i}", port)) == 0 else None
        finally:
            s.close()
    with ThreadPoolExecutor(max_workers=120) as ex:
        return [h for h in ex.map(probe, range(1, 255)) if h]


PORT_NAMES = {5555: "ADB", 22: "SSH", 80: "ويب", 443: "ويب آمن", 445: "مشاركة ملفات (SMB)", 548: "مشاركة ماك (AFP)", 8080: "ويب بديل",
              62078: "آيفون/آيباد (مزامنة)", 7000: "AirPlay", 9100: "طابعة", 8008: "Chromecast", 5353: "اكتشاف (mDNS)"}


MDNS_SERVICES = ["_airplay._tcp", "_companion-link._tcp", "_smb._tcp", "_ssh._tcp", "_http._tcp", "_ipp._tcp", "_googlecast._tcp", "_raop._tcp", "_homekit._tcp", "_hap._tcp", "_afpovertcp._tcp"]
SVC_AR = {"_airplay": "AirPlay", "_companion-link": "أجهزة آبل", "_smb": "مشاركة ملفات", "_ssh": "SSH", "_http": "ويب", "_ipp": "طابعة", "_googlecast": "Chromecast",
          "_raop": "صوت AirPlay", "_homekit": "المنزل الذكي", "_hap": "المنزل الذكي", "_afpovertcp": "مشاركة ماك"}


def mdns_names(seconds=3.0):
    """أسماء الأجهزة كما تعلنها بنفسها (Bonjour): {ip: {"name":..., "services": [...], "model": ...}}"""
    import subprocess
    procs = []
    for svc in MDNS_SERVICES:
        try:
            procs.append((svc, subprocess.Popen(["dns-sd", "-Z", svc, "local."], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)))
        except OSError:
            return {}
    time.sleep(seconds)
    found = {}
    for svc, p in procs:
        try:
            p.kill()
            out = p.stdout.read()
        except Exception:
            continue
        txt = {}
        for ln in out.splitlines():
            ln = ln.replace("\u200f", "").replace("\u2068", "").replace("\u2069", "")
            m = re.match(r"^(.+?)\._[a-z0-9-]+\._tcp\s+TXT\s+(.*)$", ln)
            if m:
                mm = re.search(r'"model=([^"]+)"', m.group(2))
                if mm:
                    txt[m.group(1)] = mm.group(1)
        for ln in out.splitlines():
            ln = ln.replace("\u200f", "").replace("\u2068", "").replace("\u2069", "")
            m = re.match(r"^(.+?)\._[a-z0-9-]+\._tcp\s+SRV\s+\d+ \d+ \d+ (\S+?)\.?\s*;", ln)
            if not m:
                continue
            inst, host = m.group(1).replace("\\032", " "), m.group(2).rstrip(".")
            try:
                ip = socket.gethostbyname(host)
            except OSError:
                continue
            d = found.setdefault(ip, {"name": inst, "services": [], "model": ""})
            lab = SVC_AR.get(svc.split(".")[0], svc)
            if lab not in d["services"]:
                d["services"].append(lab)
            if txt.get(m.group(1)) and not d["model"]:
                d["model"] = txt[m.group(1)]
    return found


def scan_network(M):
    """يتعرّف على كل جهاز على الشبكة المحلية: العنوان وMAC والاسم والمنافذ المفتوحة، ويضيف أجهزة ADB اللاسلكية المعلنة (الهاتف والساعة وغيرهما)."""
    import subprocess
    from concurrent.futures import ThreadPoolExecutor as TPE
    base = _local_subnet()
    if not base:
        raise ValueError("لا شبكة محلية متصلة.")
    ports = sorted(PORT_NAMES)

    def probe(i):
        host = f"{base}.{i}"
        open_p = []
        for pt in ports:
            s = socket.socket()
            s.settimeout(0.25)
            try:
                if s.connect_ex((host, pt)) == 0:
                    open_p.append(pt)
            finally:
                s.close()
        return host, open_p

    names_box = {}
    th = threading.Thread(target=lambda: names_box.update(mdns_names()), daemon=True)
    th.start()
    with TPE(max_workers=100) as ex:
        probed = dict(ex.map(probe, range(1, 255)))
    th.join(8)
    mdns = dict(names_box)
    arp = {}
    try:
        for ln in subprocess.run(["arp", "-an"], capture_output=True, text=True, timeout=10).stdout.splitlines():
            m = re.search(r"\(([\d.]+)\) at ([0-9a-f:]+)", ln)
            if m and ":" in m.group(2) and m.group(2) != "ff:ff:ff:ff:ff:ff" and m.group(1).startswith(base + ".") and not m.group(1).endswith(".255"):
                arp[m.group(1)] = ":".join(x.zfill(2) for x in m.group(2).split(":"))
    except Exception:
        pass
    adb_known = {}
    for name, addr in mdns_connect_services(M):
        adb_known[addr.split(":")[0]] = (name, addr)
    live = {}
    for d in _devices(M):
        if ":" in d:
            live[d.split(":")[0]] = d
    out = []
    for host in sorted((set(arp) | {h for h, p in probed.items() if p} | set(adb_known) | {h for h in mdns if h.startswith(base + ".")}), key=lambda h: tuple(int(x) for x in h.split("."))):
        try:
            name = socket.gethostbyaddr(host)[0]
        except Exception:
            name = ""
        ps = probed.get(host, [])
        row = {"ip": host, "mac": arp.get(host, ""), "name": name, "ports": [PORT_NAMES[x] for x in ps]}
        if host in mdns:
            row["name"] = mdns[host]["name"]
            row["services"] = mdns[host]["services"]
            if mdns[host]["model"]:
                row["model"] = mdns[host]["model"]
        mac = row["mac"]
        if mac and int(mac.split(":")[0], 16) & 2:
            row["private_mac"] = True   # عنوان MAC عشوائي (ميزة خصوصية في الآيفون/أندرويد): لا يكشف الشركة
        if host in adb_known:
            row["adb"] = adb_known[host][1]
        if host in live:
            row["adb_connected"] = live[host]
            try:
                row["model"] = M.shell("getprop ro.product.model", live[host], 6).stdout.strip()
                row["is_watch"] = bool(M.is_watch(live[host]))
            except Exception:
                pass
        if 62078 in ps:
            row["kind"] = "آيفون/آيباد"
        elif host in live or host in adb_known or 5555 in ps:
            row["kind"] = "جهاز أندرويد (ADB)"
        out.append(row)
    return {"subnet": base + ".0/24", "count": len(out), "devices": out[:80]}


def connect_any(M, addr):
    """يصل أي جهاز يعلن ADB لاسلكيًا (هاتف أو ساعة أو لوحي) ويعرّفه."""
    if not ADDR_RE.match(addr or ""):
        raise ValueError("عنوان غير صالح؛ اكتب مثل 192.168.1.20:5555")
    if ":" not in addr:
        addr += ":5555"
    if not M.try_connect(addr):
        raise ValueError("تعذّر الاتصال بهذا الجهاز؛ تأكد أن «التصحيح اللاسلكي» مفعّل فيه وأنه على الشبكة نفسها (وربط مرة بالرمز إن طُلب).")
    model = M.shell("getprop ro.product.model", addr, 8).stdout.strip()
    return {"connected": addr, "model": model, "is_watch": bool(M.is_watch(addr))}


def status(M):
    live = [d for d in _devices(M) if not M.is_watch(d)]
    cfg = M.phone_cfg()
    wireless = [d for d in live if ":" in d or "_adb-tls" in d]
    return {"connected": bool(live), "wireless": wireless[0] if wireless else None, "usb": [d for d in live if d not in wireless][:1],
            "saved_serial": cfg.get("serial") or "", "saved_ip": cfg.get("ip") or "", "last_note": STATE["last_note"], "last_ok": STATE["last_ok"]}


def _accept(M, addr):
    """يتأكد أن الجهاز المتصل هو هاتفنا (الرقم التسلسلي) وليس ساعة أو جهازًا آخر، ويحفظ عنوانه."""
    if M.is_watch(addr):
        M.adb("disconnect", addr, timeout=8)
        return False
    ser = _serial_of(M, addr)
    saved = M.phone_cfg().get("serial")
    if saved and ser and ser != saved:
        M.adb("disconnect", addr, timeout=8)
        return False
    M.phone_save(serial=ser or saved or "", ip=addr.split(":")[0])
    STATE["last_ok"] = time.time()
    return True


def pair(M, hostport, code):
    if not ADDR_RE.match(hostport or "") or ":" not in hostport:
        raise ValueError("اكتب عنوان الربط كما يظهر في الهاتف، مثل 192.168.1.20:37099")
    if not CODE_RE.match(str(code or "")):
        raise ValueError("رمز الربط ستة أرقام كما يظهر في الهاتف.")
    r = M.adb("pair", hostport, str(code), timeout=25)
    text = (r.stdout + r.stderr).lower()
    if "successfully paired" not in text:
        raise ValueError("فشل الربط؛ تأكد من الرمز والعنوان (يتغيران كل مرة تفتح فيها نافذة الربط).")
    return True


def connect(M, ip="", port="", pair_addr="", pair_code=""):
    """يصل الهاتف الآن. بلا معطيات: يجرّب كل الطرق التلقائية. مع رمز ربط: يربط أولًا ثم يتصل."""
    with LOCK:
        if pair_addr or pair_code:
            pair(M, pair_addr, pair_code)
            time.sleep(2)
        if ip:
            addr = f"{ip}:{port}" if port else ip
            if not ADDR_RE.match(addr):
                raise ValueError("عنوان غير صالح.")
            if M.try_connect(addr if ":" in addr else addr + ":5555") and _accept(M, addr if ":" in addr else addr + ":5555"):
                return {"connected": addr}
        got = reconnect(M, force=True)
        if got:
            return {"connected": got}
    raise ValueError("لم أجد الهاتف على الشبكة. تأكد أنه على نفس الواي فاي وشاشته مضاءة وأن «التصحيح اللاسلكي» مفعّل؛ "
                     "وإن لم يكن مربوطًا من قبل فأعطني عنوان الربط والرمز من شاشة «الاقتران برمز».")


def fix_port(M):
    """يثبّت منفذ الاتصال اللاسلكي على 5555 (يلزم الهاتف موصولًا بالكابل مرة واحدة). يبقى ثابتًا حتى إعادة تشغيل الهاتف."""
    usb = [d for d in _devices(M) if ":" not in d and not M.is_watch(d)]
    if not usb:
        raise ValueError("وصّل الهاتف بالكابل أولًا (وافق على «السماح بالتصحيح» في شاشته) ثم أعد الطلب.")
    serial = usb[0]
    ip_out = M.shell("ip -f inet addr show wlan0", serial, 8).stdout
    m = re.search(r"inet (\d{1,3}(?:\.\d{1,3}){3})/", ip_out)
    if not m:
        raise ValueError("الهاتف غير موصول بالواي فاي؛ شغّله ثم أعد المحاولة.")
    ip = m.group(1)
    r = M.adb("-s", serial, "tcpip", "5555", timeout=15)
    if r.returncode:
        raise ValueError("رفض الهاتف تفعيل المنفذ الثابت: " + (r.stderr or r.stdout).strip()[:120])
    time.sleep(2)
    if not (M.try_connect(f"{ip}:5555") and _accept(M, f"{ip}:5555")):
        raise ValueError("فُعّل المنفذ الثابت لكن الاتصال لم ينجح بعد؛ افصل الكابل وأعد المحاولة بعد لحظات.")
    STATE["last_note"] = "ثُبّت المنفذ 5555"
    return {"connected": f"{ip}:5555", "port": 5555}


def reconnect(M, force=False):
    live = [d for d in _devices(M) if not M.is_watch(d)]
    if live:
        return live[0]
    cfg = M.phone_cfg()
    ip = cfg.get("ip")
    # ١) العنوان المحفوظ على المنفذ المعتاد
    if ip and M.try_connect(f"{ip}:5555") and _accept(M, f"{ip}:5555"):
        STATE["last_note"] = "اتصل على العنوان المحفوظ"
        return f"{ip}:5555"
    # ٢) خدمات الشبكة المعلنة (التصحيح اللاسلكي المربوط): العنوان والمنفذ يتغيران ولا يهم
    for name, addr in mdns_connect_services(M):
        if M.try_connect(addr) and _accept(M, addr):
            STATE["last_note"] = "اتصل عبر اكتشاف الشبكة"
            return addr
    # ٣) مسح الشبكة المحلية (تغيّر العنوان مع بقاء منفذ 5555 مفتوحًا) — لا أكثر من مرة كل ٣ دقائق إلا بطلب
    if force or time.time() - STATE["last_scan"] > 180:
        STATE["last_scan"] = time.time()
        for host in scan_subnet(M):
            if host != ip and M.try_connect(f"{host}:5555") and _accept(M, f"{host}:5555"):
                STATE["last_note"] = f"وجده بمسح الشبكة ({host})"
                return f"{host}:5555"
    STATE["last_note"] = "لم يُوجد الهاتف على الشبكة"
    return None


def keeper(M):
    """يعمل مع زاجل: كل ٢٠ ثانية إن لم يكن هناك هاتف متصل وكان لنا هاتف محفوظ يحاول وصله."""
    while True:
        time.sleep(20)
        try:
            STATE["keeper_ticks"] = STATE.get("keeper_ticks", 0) + 1
            if M.backup_running or not M.phone_cfg().get("serial"):
                continue
            if [d for d in _devices(M) if not M.is_watch(d)]:
                continue
            for line in M.adb("devices").stdout.splitlines()[1:]:     # إدخالات offline العالقة: نفصلها ليبدأ اتصال نظيف
                row = line.split()
                if len(row) > 1 and row[1] in ("offline", "connecting") and ":" in row[0]:
                    M.adb("disconnect", row[0], timeout=8)
            reconnect(M)
        except Exception:
            pass


def details(M):
    """بطاقة قسم «الجوال»: الطراز والإصدار والبطارية والمساحة للجهاز المتصل، وحالة الاتصال."""
    st = status(M)
    out = dict(st)
    live = [d for d in _devices(M) if not M.is_watch(d)]
    if not live:
        return out | {"device": None}
    serial = live[0]
    sh = lambda c, t=8: M.shell(c, serial, t).stdout.strip()
    batt = {}
    for ln in sh("dumpsys battery").splitlines():
        k, _, v = ln.strip().partition(":")
        batt[k.strip()] = v.strip()
    try:
        level, temp = int(batt.get("level", "-1")), int(batt.get("temperature", "0")) / 10
    except ValueError:
        level, temp = -1, 0
    charging = batt.get("status") in ("2", "5") or batt.get("AC powered") == "true" or batt.get("USB powered") == "true" or batt.get("Wireless powered") == "true"
    out["device"] = {"serial": serial, "model": sh("getprop ro.product.model") or "Android", "brand": sh("getprop ro.product.manufacturer"), "android": sh("getprop ro.build.version.release"),
                     "battery": level, "charging": charging, "temp_c": temp, "storage": M.storage_info(serial)}
    return out


# ---------- شاشة الهاتف في نافذة قابلة للتحكم (scrcpy) ----------
SCREEN = {"proc": None, "serial": "", "started": 0.0}


def _scrcpy():
    for c in ("/opt/homebrew/bin/scrcpy", "/usr/local/bin/scrcpy", shutil.which("scrcpy") or ""):
        if c and os.path.exists(c):
            return c
    return None


def screen_status():
    pr = SCREEN["proc"]
    running = bool(pr and pr.poll() is None)
    return {"running": running, "serial": SCREEN["serial"] if running else "", "installed": bool(_scrcpy())}


def screen_stop():
    pr = SCREEN["proc"]
    if pr and pr.poll() is None:
        pr.terminate()
        try:
            pr.wait(timeout=4)
        except Exception:
            pr.kill()
    SCREEN["proc"] = None
    return {"running": False, "note": "أُغلقت نافذة شاشة الهاتف."}


def screen_start(M, opts=None):
    """يفتح شاشة الهاتف في نافذة تتحكم بها بالفأرة ولوحة المفاتيح. لا يمس الساعة."""
    opts = opts or {}
    exe = _scrcpy()
    if not exe:
        raise ValueError("أداة عرض الشاشة (scrcpy) غير مثبّتة على هذا الحاسوب؛ ثبّتها بـ brew install scrcpy.")
    if screen_status()["running"]:
        return {"running": True, "serial": SCREEN["serial"], "note": "نافذة شاشة الهاتف مفتوحة أصلًا."}
    live = [d for d in _devices(M) if not M.is_watch(d)]
    if not live:
        raise ValueError("الهاتف غير متصل الآن؛ اتصل به أولًا (phone_connect) ثم أعد المحاولة.")
    serial = live[0]
    cmd = [exe, "-s", serial, "--window-title", "شاشة الهاتف — زاجل", "--no-audio", "--stay-awake", "--max-size", str(int(opts.get("max_size") or 1280))]
    if opts.get("screen_off"):
        cmd.append("--turn-screen-off")
    if opts.get("on_top", True):
        cmd.append("--always-on-top")
    env = dict(os.environ)
    env["ADB"] = M.ADB
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "/usr/bin:/bin")
    pr = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(2.5)
    if pr.poll() is not None:
        err = (pr.stderr.read() or b"").decode("utf-8", errors="replace").strip().splitlines()[-1:] or ["فشل غير معروف"]
        raise ValueError("تعذّر فتح شاشة الهاتف: " + err[0][:200])
    SCREEN.update({"proc": pr, "serial": serial, "started": time.time()})
    return {"running": True, "serial": serial, "note": "فُتحت نافذة شاشة الهاتف؛ اضغط وتنقّل بالفأرة واكتب بلوحة المفاتيح."}


# ---------- أزرار التحكم بالهاتف (قائمة بيضاء؛ لا أوامر حرة) ----------
KEYS = {"home": 3, "back": 4, "recents": 187, "power": 26, "vol_up": 24, "vol_down": 25, "mute": 164, "wake": 224,
        "sleep": 223, "play_pause": 85, "next": 87, "prev": 88, "camera": 27, "menu": 82}
CONTROL_AR = {"screenshot": "التقاط الشاشة", "record_start": "بدء تسجيل الشاشة", "record_stop": "إيقاف التسجيل وحفظه", "key": "زر", "notifications": "الإشعارات",
              "quick_settings": "الإعدادات السريعة", "collapse": "إغلاق اللوحات", "rotate": "تدوير الشاشة", "text": "كتابة نص", "keep_awake": "إبقاء الشاشة مضاءة"}
REC = {"proc": None, "serial": "", "remote": "/sdcard/zajel_screenrec.mp4", "started": 0.0}


def _out_dir():
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    os.makedirs(d, exist_ok=True)
    return d


def _stamp():
    return time.strftime("%Y%m%d-%H%M%S")


def _live_serial(M):
    live = [d for d in _devices(M) if not M.is_watch(d)]
    if not live:
        raise ValueError("الهاتف غير متصل الآن؛ اتصل به أولًا.")
    return live[0]


def control(M, act, arg=None):
    """ينفّذ أمرًا من القائمة البيضاء على الهاتف المتصل، ويعيد {ok, note, path?}."""
    act = str(act or "")
    arg = arg if isinstance(arg, dict) else {}
    serial = _live_serial(M)
    if act == "screenshot":
        res = subprocess.run([M.ADB, "-s", serial, "exec-out", "screencap", "-p"], capture_output=True, timeout=30)
        if res.returncode != 0 or len(res.stdout) < 1000:
            raise ValueError("تعذّر التقاط الشاشة (قد تكون الشاشة مقفلة أو التطبيق يمنع اللقطات).")
        path = os.path.join(_out_dir(), f"لقطة-الهاتف-{_stamp()}.png")
        with open(path, "wb") as fh:
            fh.write(res.stdout)
        return {"ok": True, "path": path, "note": "حُفظت لقطة الشاشة في التنزيلات."}
    if act == "record_start":
        if REC["proc"] and REC["proc"].poll() is None:
            return {"ok": True, "note": "التسجيل يعمل أصلًا."}
        REC["proc"] = subprocess.Popen([M.ADB, "-s", serial, "shell", "screenrecord", "--time-limit", "180", REC["remote"]],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        REC.update({"serial": serial, "started": time.time()})
        return {"ok": True, "note": "بدأ تسجيل الشاشة (أقصى مدة ٣ دقائق بحسب أندرويد). اضغط «أوقف التسجيل» لحفظه."}
    if act == "record_stop":
        pr = REC["proc"]
        if not pr:
            raise ValueError("لا تسجيل جارٍ.")
        subprocess.run([M.ADB, "-s", REC["serial"] or serial, "shell", "pkill", "-2", "screenrecord"], capture_output=True, timeout=10)
        try:
            pr.wait(timeout=8)
        except Exception:
            pr.kill()
        REC["proc"] = None
        time.sleep(1.0)
        path = os.path.join(_out_dir(), f"تسجيل-الهاتف-{_stamp()}.mp4")
        res = subprocess.run([M.ADB, "-s", serial, "pull", REC["remote"], path], capture_output=True, text=True, timeout=300)
        if res.returncode != 0 or not os.path.exists(path):
            raise ValueError("تعذّر سحب التسجيل من الهاتف: " + (res.stderr or "").strip()[-150:])
        subprocess.run([M.ADB, "-s", serial, "shell", "rm", REC["remote"]], capture_output=True, timeout=10)
        return {"ok": True, "path": path, "note": "حُفظ تسجيل الشاشة في التنزيلات."}
    if act == "key":
        name = str(arg.get("name") or "")
        if name not in KEYS:
            raise ValueError("زر غير معروف. المتاح: " + "، ".join(KEYS))
        M.shell(f"input keyevent {KEYS[name]}", serial, 10)
        return {"ok": True, "note": f"ضُغط زر {name}."}
    if act in ("notifications", "quick_settings", "collapse"):
        sub = {"notifications": "expand-notifications", "quick_settings": "expand-settings", "collapse": "collapse"}[act]
        M.shell(f"cmd statusbar {sub}", serial, 10)
        return {"ok": True, "note": "تم."}
    if act == "rotate":
        deg = int(arg.get("rotation", 1))
        if deg not in (0, 1, 2, 3):
            raise ValueError("التدوير من ٠ إلى ٣.")
        M.shell(f"settings put system accelerometer_rotation 0; settings put system user_rotation {deg}", serial, 10)
        return {"ok": True, "note": "دُوّرت الشاشة."}
    if act == "text":
        txt = str(arg.get("text") or "")
        if not txt or not re.fullmatch(r"[A-Za-z0-9 @._,:;!?+=/#%&*()\[\]-]{1,300}", txt):
            raise ValueError("الكتابة عن بعد تدعم الحروف الإنجليزية والأرقام وعلامات شائعة فقط (حتى ٣٠٠ حرف)؛ للعربية اكتب في نافذة الشاشة بلوحة المفاتيح.")
        M.shell("input text '" + txt.replace(" ", "%s").replace("'", "") + "'", serial, 15)
        return {"ok": True, "note": "كُتب النص في الحقل المحدّد على الهاتف."}
    if act == "keep_awake":
        on = bool(arg.get("on", True))
        M.shell("svc power stayon " + ("true" if on else "false"), serial, 10)
        return {"ok": True, "note": "الشاشة ستبقى مضاءة أثناء الشحن." if on else "عاد الإطفاء التلقائي."}
    raise ValueError("إجراء غير معروف.")
