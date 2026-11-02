"""iPhone وiPad عبر libimobiledevice (مثبّتة بـHomebrew): كشف الجهاز، المساحة، والصور والفيديو (DCIM عبر AFC).
آبل لا تسمح بأكثر من ذلك بلا كسر حماية؛ ولا يعمل الوصول إلا والجهاز مفتوح القفل ومُوثَّق."""
from __future__ import annotations

import json
import os
import posixpath
import re
import shutil
import subprocess
import time

BIN = "/opt/homebrew/bin"
_cache = {"t": 0.0, "v": []}
MODE = {}  # udid -> "usb" | "wifi"


APPS = "/@apps"  # جذر وهمي: ملفات التطبيقات التي تسمح بالمشاركة (Documents لكل تطبيق)
_apps_cache = {}


def _net(udid):
    return ["-n"] if MODE.get(udid) == "wifi" else []


def _split(path):
    """/@apps/<bundle>/<sub> ← (bundle, /Documents/<sub>)؛ وما عداه ← (None, path)."""
    if path == APPS or path.startswith(APPS + "/"):
        rest = path[len(APPS):].strip("/")
        if not rest:
            return "", "/"
        b, _, sub = rest.partition("/")
        return b, "/Documents" + ("/" + sub if sub else "")
    return None, path


def apps(udid):
    """[{id, name}] للتطبيقات التي تسمح بمشاركة الملفات — مع ذاكرة دقيقة."""
    c = _apps_cache.get(udid)
    if c and time.time() - c[0] < 60:
        return c[1]
    import plistlib
    r = subprocess.run([_tool("ideviceinstaller"), *_net(udid), "-u", udid, "list", "--xml", "-a", "CFBundleIdentifier", "-a", "CFBundleDisplayName",
                        "-a", "CFBundleName", "-a", "UIFileSharingEnabled"], capture_output=True, timeout=30)
    try:
        items = plistlib.loads(r.stdout)
    except Exception:
        raise ValueError("تعذّر قراءة قائمة التطبيقات؛ افتح قفل الجهاز.")
    out = sorted(({"id": a["CFBundleIdentifier"], "name": a.get("CFBundleDisplayName") or a.get("CFBundleName") or a["CFBundleIdentifier"]}
                  for a in items if a.get("UIFileSharingEnabled") and a.get("CFBundleIdentifier")), key=lambda a: a["name"].casefold())
    _apps_cache[udid] = (time.time(), out)
    return out


def _tool(name):
    return shutil.which(name) or os.path.join(BIN, name)


def _run(args, timeout=20, inp=None):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, input=inp)


def available():
    return os.path.exists(_tool("idevice_id"))


KEEP_SECS = 6 * 3600  # كم يبقى الجهاز الغائب ظاهرًا بعد آخر مرة رُئي فيها
_MEMO = {"v": None}


def _memo_path():
    return os.path.join(os.environ.get("PB_DATA", os.path.expanduser("~/Library/Application Support/Phone Backup")), ".ios_known.json")


def _memo():
    if _MEMO["v"] is None:
        try:
            _MEMO["v"] = json.load(open(_memo_path(), encoding="utf-8"))
        except Exception:
            _MEMO["v"] = {}
    return _MEMO["v"]


def _remember(u, d):
    m = _memo(); new = {k: d.get(k) for k in ("name", "cls", "model", "ios", "total", "free")}
    if {k: m.get(u, {}).get(k) for k in new} == new and time.time() - m[u].get("t", 0) < 300:
        return
    m[u] = dict(new, t=time.time())
    try:
        json.dump(m, open(_memo_path(), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


def devices():
    """[{udid, name, cls, model, ios, total, free, locked, trusted}] — مع ذاكرة 5 ثوانٍ."""
    if time.time() - _cache["t"] < 5:
        return _cache["v"]
    out = []
    if available():
        def ids(flag):
            try:
                return [x.strip() for x in _run([_tool("idevice_id"), flag], 8).stdout.splitlines() if x.strip()]
            except Exception:
                return []
        usb, net = ids("-l"), ids("-n")
        for u in dict.fromkeys(usb + net + [k for k, m in _memo().items() if time.time() - m.get("t", 0) < KEEP_SECS]):
            if u not in usb and u not in net:  # غاب من الشبكة لأن الجهاز نام: يبقى ظاهرًا بآخر معلوماته
                MODE[u] = "wifi"
                d = dict(_memo()[u], udid=u, locked=True, asleep=True, conn="wifi", trusted=True, held=True)
                out.append(d)
                continue
            MODE[u] = "usb" if u in usb else "wifi"
            d = {"udid": u, "name": "iPhone", "cls": "iPhone", "model": "", "ios": "", "total": None, "free": None, "locked": False, "trusted": True, "conn": MODE[u]}
            try:
                info = ""
                for mode in (["usb", "wifi"] if u in usb else ["wifi"]):
                    MODE[u] = mode
                    try:
                        info = _run([_tool("ideviceinfo"), *_net(u), "-u", u], 6).stdout
                    except subprocess.TimeoutExpired:
                        info = ""
                    if info.strip():
                        break
                d["conn"] = MODE[u]
                kv = dict(re.findall(r"^(\w+): (.*)$", info, re.M))
                if not kv:  # مُعلن على الشبكة لكنه لا يجيب: نائم أو مقفل أو خرج من الشبكة
                    d.update({k: v for k, v in _memo().get(u, {}).items() if k != "t"}, locked=True, asleep=True, held=u in _memo())
                    out.append(d)
                    continue
                d.update(name=kv.get("DeviceName", d["name"]).strip().lstrip("‏ "), cls=kv.get("DeviceClass", "iPhone"), model=kv.get("ProductType", ""), ios=kv.get("ProductVersion", ""),
                         locked=False)
                du = dict(re.findall(r"^(\w+): (\d+)$", _run([_tool("ideviceinfo"), *_net(u), "-u", u, "-q", "com.apple.disk_usage"], 10).stdout, re.M))
                if du.get("TotalDiskCapacity"):
                    d["total"] = int(du["TotalDiskCapacity"])
                    d["free"] = int(du.get("AmountDataAvailable", 0))
                elif _memo().get(u, {}).get("total"):  # مقفل لا يجيب عن المساحة: آخر قيمة معروفة
                    d["total"], d["free"] = _memo()[u]["total"], _memo()[u]["free"]
                _remember(u, d)
            except Exception:
                pass
            out.append(d)
    _cache.update(t=time.time(), v=out)
    return out


ANSI = re.compile(r"\x1b\[[0-9;]*m")
PROMPT = re.compile(r"afc:[^\n>]*> ")


def _check(err):
    if "InstallationLookupFailed" in err:
        raise ValueError("هذا التطبيق لا يسمح بالوصول إلى ملفاته.")
    if "Password protected" in err:
        raise ValueError("افتح قفل الجهاز ثم أعد المحاولة.")
    if "Failed to start service" in err or "No device found" in err or "not found!" in err:
        _cache["t"] = 0
        raise ValueError("تعذّر الوصول إلى الجهاز؛ افتح قفله وتأكد من «الوثوق بهذا الكمبيوتر».")


def _afc(udid, commands, timeout=120, app=None):
    """يشغّل أوامر afcclient ([اسم، وسائط…]) ويعيد مخرجات كل أمر بالترتيب.
    الوضع التفاعلي (جلسة واحدة سريعة) يُسقط الحروف غير اللاتينية من المسارات، فما فيه عربية يُشغَّل وسيطًا مباشرًا بالتوازي."""
    if not devices_known(udid):
        devices()
    base = [_tool("afcclient"), *_net(udid), "-u", udid, *(["--documents", app] if app else [])]
    try:
        if all(all(ord(c) < 128 for c in " ".join(cmd)) for cmd in commands):
            r = _run(base, timeout, inp="\n".join(" ".join([cmd[0], *map(_q, cmd[1:])]) for cmd in commands) + "\nexit\n")
            _check((r.stderr or "") + (r.stdout or ""))
            parts = PROMPT.split(ANSI.sub("", r.stdout))
            return [p.strip() for p in parts[1:]]
        from concurrent.futures import ThreadPoolExecutor

        def one(cmd):
            for k in range(4):
                r = _run(base + ["--"] + cmd, timeout)
                try:
                    _check((r.stderr or "") + (r.stdout or ""))
                    break
                except ValueError:
                    if k == 3:
                        raise
                    time.sleep(0.5 * (k + 1))
            return ANSI.sub("", r.stdout).strip()
        with ThreadPoolExecutor(max_workers=3) as pool:
            return list(pool.map(one, commands))
    except subprocess.TimeoutExpired:
        _cache["t"] = 0
        raise ValueError("الجهاز لا يستجيب: ربما قُفل أو نام أو خرج من الشبكة. افتح قفله ثم أعد المحاولة.")


def devices_known(udid):
    return udid in MODE


def _norm(path):
    path = "/" + (path or "").strip("/")
    if ".." in path.split("/"):
        raise ValueError("مسار غير صالح.")
    return path


def _q(p):
    return '"' + p.replace('"', '\\"') + '"'


def browse(udid, path):
    import json
    path = _norm(path)
    if path == "/":
        top = browse_real(udid, "/")
        top["entries"].insert(0, {"name": "ملفات التطبيقات", "path": APPS, "is_dir": True, "size": None, "mod": 0, "chg": 0, "is_archive": False})
        return top
    app, real = _split(path)
    if app == "":
        return {"path": path, "entries": [{"name": a["name"], "path": APPS + "/" + a["id"], "is_dir": True, "size": None, "mod": 0, "chg": 0,
                                           "is_archive": False, "app": a["id"]} for a in apps(udid)]}
    r = browse_real(udid, real, app)
    for e in r["entries"]:
        e["path"] = path.rstrip("/") + "/" + e["name"]
    r["path"] = path
    return r


def browse_real(udid, path, app=None):
    import json
    seg = _afc(udid, [["ls", path]], app=app)
    names = [n.strip() for n in (seg[0] if seg else "").splitlines() if n.strip() and not n.startswith(("ERROR", "Error", "Usage")) and n.strip() not in (".", "..")]
    out = []
    for k in range(0, len(names), 400):
        chunk = names[k:k + 400]
        infos = _afc(udid, [["info", posixpath.join(path, n)] for n in chunk], 300, app)
        for n, txt in zip(chunk, infos + [""] * (len(chunk) - len(infos))):
            try:
                i = json.loads(txt)
            except ValueError:
                i = {}
            isdir = i.get("st_ifmt") == "S_IFDIR"
            mt = int(i.get("st_mtime") or 0)
            mod = mt // 1_000_000 if mt > 10 ** 14 else mt * 1000
            out.append({"name": n, "path": posixpath.join(path, n), "is_dir": isdir, "size": None if isdir else int(i.get("st_size") or 0),
                        "mod": mod, "chg": mod, "is_archive": False})
    out.sort(key=lambda e: (not e["is_dir"], e["name"].casefold()))
    return {"path": path, "entries": out}


def stat(udid, path):
    import json
    app, real = _split(_norm(path))
    if app == "":
        return {"is_dir": True, "size": 0}
    seg = _afc(udid, [["info", real]], app=app)
    try:
        i = json.loads(seg[0])
    except (ValueError, IndexError):
        return None
    return {"is_dir": i.get("st_ifmt") == "S_IFDIR", "size": int(i.get("st_size") or 0)}


def _size(p):
    total = 0
    for root, _, files in os.walk(p) if os.path.isdir(p) else [("", [], [p])]:
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def pull(udid, path, dest, stall=60):
    """يجلب ملفًا أو مجلدًا. إن توقّف النقل «stall» ثانية (قفل الجهاز أو نومه أو انقطاع الشبكة) يُلغى بخطأ واضح
    بدل أن يبقى معلّقًا ويبدو كأنه يعمل."""
    app, real = _split(_norm(path))
    if app == "":
        raise ValueError("اختر تطبيقًا أو ملفات داخله.")
    dest = str(dest)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    if not devices_known(udid):
        devices()
    p = subprocess.Popen([_tool("afcclient"), *_net(udid), "-u", udid, *(["--documents", app] if app else []), "--", "get", "-r", real, dest],
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    last, since = -1, time.time()
    while p.poll() is None:
        time.sleep(2)
        cur = _size(dest) if os.path.exists(dest) else 0
        if cur != last:
            last, since = cur, time.time()
        elif time.time() - since > stall:
            p.kill()
            _cache["t"] = 0
            raise ValueError("توقّف النقل: الجهاز قُفل أو نام أو انقطع الاتصال. افتح قفله وأبقِ شاشته مضاءة ثم أعد المحاولة.")
    _check(ANSI.sub("", p.stdout.read() or ""))
    if not os.path.exists(dest):
        raise ValueError("تعذّر جلب الملف من الجهاز.")
    return dest


def files(udid, path):
    """كل الملفات تحت مسار (للترحيل والبحث): [(size, mtime_sec, path)]."""
    out, stack = [], [_norm(path)]
    while stack:
        cur = stack.pop()
        try:
            entries = browse(udid, cur)["entries"]
        except ValueError:
            continue
        for e in entries:
            if e["is_dir"]:
                stack.append(e["path"])
            else:
                out.append((e["size"] or 0, (e["mod"] or 0) // 1000, e["path"]))
    return out


def push(udid, local, path):
    """يكتب ملفًا داخل ملفات تطبيق (/@apps/…)؛ مجلدات الوسائط للقراءة فقط."""
    app, real = _split(_norm(path))
    if not app:
        raise ValueError("الكتابة مسموحة في ملفات التطبيقات فقط.")
    parts = real.strip("/").split("/")[:-1]
    mk = []
    for i in range(2, len(parts) + 1):
        mk.append(["mkdir", "/" + "/".join(parts[:i])])
    if mk:
        try:
            _afc(udid, mk, 60, app)
        except ValueError:
            pass
    _afc(udid, [["put", "-f", str(local), real]], 7200, app)
    st = stat(udid, path)
    if not st or st["is_dir"]:
        raise ValueError("تعذّر الكتابة في الجهاز.")
    return st


def mtime(udid, path):
    import json
    app, real = _split(_norm(path))
    seg = _afc(udid, [["info", real]], app=app)
    try:
        i = json.loads(seg[0])
        mt = int(i.get("st_mtime") or 0)
        return mt // 1_000_000_000 if mt > 10 ** 14 else mt
    except Exception:
        return 0


def trash(udid, path):
    """ينقل ملفًا داخل ملفات تطبيق إلى ‎.zajel_trash‎ في التطبيق نفسه (لا محو)."""
    app, real = _split(_norm(path))
    if not app:
        raise ValueError("الحذف مسموح في ملفات التطبيقات فقط.")
    dest = "/Documents/.zajel_trash/" + time.strftime("%Y-%m-%d") + "/" + posixpath.basename(real)
    try:
        _afc(udid, [["mkdir", "/Documents/.zajel_trash"], ["mkdir", posixpath.dirname(dest)]], 60, app)
    except ValueError:
        pass
    _afc(udid, [["mv", real, dest]], 60, app)
