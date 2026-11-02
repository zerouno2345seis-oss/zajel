#!/usr/bin/env python3
"""Local browser UI and ADB bridge for shared-storage backups."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import csv
import glob
import hashlib
import json
import os
import posixpath
import plistlib
import pwd
import stat as statmod
import re
import urllib.error
import socket
import time
from concurrent.futures import ThreadPoolExecutor
import tempfile
import shlex
import mimetypes
import shutil
import subprocess
import threading
import uuid
import webbrowser
import urllib.request
import sys
import ebook
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

def _overlay_boot():
    """إن وُجدت شيفرة أحدث في مجلد بيانات زاجل (من زر التحديث) شغّل منها. ثلاث محاولات فاشلة متتالية تعيد البرنامج إلى شيفرته الأصلية."""
    if os.environ.get("PB_OVERLAY_ACTIVE") == "1":
        return
    here = Path(__file__).resolve().parent
    data = Path(os.environ.get("PB_DATA") or (Path.home() / "Library" / "Application Support" / "Phone Backup"))
    ov = data / "code"
    try:
        if not (ov / "samsung_backup_web.py").exists() or ov.resolve() == here:
            return
        v = lambda p: tuple(int(x) for x in (p / "VERSION").read_text().strip().split("."))
        if v(ov) <= v(here):
            return
        tries = int((ov / ".boots").read_text() or 0) if (ov / ".boots").exists() else 0
        if tries >= 3:
            shutil.rmtree(ov, ignore_errors=True)
            return
        (ov / ".boots").write_text(str(tries + 1))
    except Exception:
        return
    os.environ["PB_OVERLAY_ACTIVE"] = "1"
    os.execv(sys.executable, [sys.executable, str(ov / "samsung_backup_web.py")] + sys.argv[1:])


_overlay_boot()
import cleaner  # noqa: E402
import fileops  # noqa: E402
import archives
import rclone_src  # noqa: E402
import migrate  # noqa: E402
import ios_src  # noqa: E402
import syncer  # noqa: E402
import kindle_src  # noqa: E402
import finder  # noqa: E402
import adbclean  # noqa: E402
import agent_server  # noqa: E402

_STUCK = {}


BOOKJOBS = {}


def book_names_start(body):
    """يقرأ عنوان كل كتاب ومؤلفه (Calibre) ويقترح اسمًا؛ مهمة خلفية تُستطلَع."""
    import ebook
    src, paths = body.get("src") or {}, [p for p in (body.get("paths") or []) if isinstance(p, str)][:500]
    if not paths:
        raise ValueError("حدد كتبًا أولًا.")
    if src.get("type") == "adb":
        src["serial"] = connected_device(src.get("serial"))
    jid = uuid.uuid4().hex[:8]
    job = BOOKJOBS[jid] = {"id": jid, "state": "running", "done": 0, "total": len(paths), "items": []}

    def go():
        tmp = Path(tempfile.mkdtemp(prefix="pbbook-"))
        try:
            for p in paths:
                name = posixpath.basename(p.rstrip("/"))
                it = {"path": p, "name": name}
                try:
                    if os.path.splitext(name)[1].lower() not in ebook.BOOK_EXT:
                        it.update(skip="ليس كتابًا")
                    else:
                        t = src.get("type")
                        if t == "local" and not str(src.get("root", "")).startswith("rc:"):
                            local = str(cloud_resolve(src["root"], p)[1])
                        else:
                            local = str(tmp / ("b" + str(job["done"]) + os.path.splitext(name)[1]))
                            if t == "adb":
                                adb("pull", p, local, serial=src["serial"], timeout=600)
                            elif t == "ios":
                                ios_src.pull(src["udid"], p, local)
                            elif t == "kindle":
                                kindle_src.pull(p, local)
                            else:
                                rclone_src.download(src["root"], p, local)
                        it.update(ebook.suggest(local, name))
                        if local.startswith(str(tmp)):
                            Path(local).unlink(missing_ok=True)
                except Exception as exc:
                    it.update(error=str(exc)[:160])
                job["items"].append(it)
                job["done"] += 1
            job["state"] = "done"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    threading.Thread(target=go, daemon=True).start()
    return job


def safe_usage(p, wait=4):
    """shutil.disk_usage بمهلة: قرص عالق (كيندل مثلًا) يعلّق النداء إلى الأبد ويجمّد الخادم كله."""
    key = str(p)
    if time.time() - _STUCK.get(key, 0) < 60:
        raise OSError("قرص لا يستجيب")
    box = {}

    def go():
        try:
            box["v"] = shutil.disk_usage(p)
        except BaseException as e:
            box["e"] = e
    t = threading.Thread(target=go, daemon=True); t.start(); t.join(wait)
    if "v" in box:
        return box["v"]
    if "e" in box:
        raise box["e"]
    _STUCK[key] = time.time()
    raise OSError("قرص لا يستجيب")


def _find_adb():
    found = shutil.which("adb")
    if found:
        return found
    for c in ("/opt/homebrew/bin/adb", "/usr/local/bin/adb", str(Path.home() / "Library/Android/sdk/platform-tools/adb")):
        if os.path.exists(c):
            return c
    return "adb"


ADB = _find_adb()
PORT = int(os.environ.get("PB_PORT") or 8765)  # النافذة الأصلية تختار بابًا فارغًا إن كان 8765 مشغولًا
ROOT = Path(__file__).resolve().parent
# بيانات المستخدم (المفضلة، المصغّرات، السجلات): بجوار الشيفرة، أو في مجلد البرنامج المحدد بـ PB_DATA
DATA = Path(os.environ.get("PB_DATA") or ROOT)
DATA.mkdir(parents=True, exist_ok=True)
APP_ID = "samsung-backup"
IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp", ".tif", ".tiff", ".avif", ".dng"}
CATEGORIES = {
    "الصور": ["/sdcard/DCIM", "/sdcard/Pictures"],
    "الفيديوهات": ["/sdcard/Movies", "/sdcard/DCIM/Camera"],
    "الصوتيات": ["/sdcard/Music", "/sdcard/Podcasts"],
    "التسجيلات الصوتية": ["/sdcard/Recordings", "/sdcard/Voice Recorder", "/sdcard/Sounds/Recordings"],
    "المستندات والتنزيلات": ["/sdcard/Documents", "/sdcard/Download"],
}
lock = threading.Lock()
backup_running = False
backup_state = {"running": False, "target": "", "completed": [], "errors": [], "total": 0, "current": ""}


def adb(*args, serial=None, timeout=15):
    cmd = [ADB] + (["-s", serial] if serial else []) + list(args)
    return subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)


def shell(command, serial, timeout=15):
    return adb("shell", command, serial=serial, timeout=timeout)


def normalize_path(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise ValueError("مسار الهاتف غير صالح.")
    if ".." in value.split("/"):
        raise ValueError("لا يسمح بالخروج من التخزين المشترك.")
    path = posixpath.normpath(value)
    if path != "/sdcard" and not path.startswith("/sdcard/"):
        raise ValueError("اختر مسارًا ضمن التخزين المشترك للهاتف.")
    return path


def deduplicate(paths):
    unique = sorted({normalize_path(path) for path in paths}, key=lambda p: (p.count("/"), p))
    kept = []
    for path in unique:
        if not any(path.startswith(parent + "/") for parent in kept):
            kept.append(path)
    return kept


def connected_device(requested=None):
    result = adb("devices", "-l")
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "تعذر تشغيل اتصال الهاتف.")
    rows = [line.split() for line in result.stdout.splitlines()[1:] if line.strip()]
    devices = [row[0] for row in rows if len(row) > 1 and row[1] == "device"]
    if requested:
        if requested not in devices:
            raise ValueError("الهاتف المختار غير متصل أو لم يعد موثوقًا.")
        return requested
    usb = [d for d in devices if ":" not in d and "_adb-tls" not in d]
    if not usb:  # لا كابل: الهاتف المحفوظ عبر الواي فاي (لا الساعة)
        pip = phone_cfg().get("ip")
        usb = [d for d in devices if (":" in d or "_adb-tls" in d) and ((pip and d.startswith(pip + ":")) or phone_cfg().get("serial", "~") in d) and not is_watch(d)][:1]
    devices = usb
    if not devices:
        raise ValueError("وصّل الهاتف ووافق على رسالة تصحيح الاتصال.")
    if len(devices) > 1:
        raise ValueError("يوجد أكثر من جهاز متصل؛ أبقِ الهاتف المطلوب فقط موصولًا.")
    return devices[0]


def storage_path(path, serial):
    """Validate canonical location too, so shared-storage symlinks cannot escape."""
    path = normalize_path(path)
    command = "readlink -f /sdcard; readlink -f " + shlex.quote(path)
    result = shell(command, serial)
    lines = result.stdout.splitlines()
    if result.returncode or len(lines) != 2:
        raise ValueError("المسار غير موجود أو لا يمكن قراءته.")
    root, actual = lines
    if actual != root and not actual.startswith(root + "/"):
        raise ValueError("هذا الرابط يشير إلى مسار خارج التخزين المشترك.")
    return path


def snapshot():
    with lock:
        return {"busy": backup_running, "backup": copy.deepcopy(backup_state)}


def status():
    state = snapshot()
    wip = watch_cfg().get("ip")
    waddr = watch_current(wip) if wip else None
    state["watch"] = {"ip": wip, "connected": bool(waddr), "addr": waddr}
    state["volumes"] = [{"name": v["name"], "free": v["free"], "writable": v["writable"], "network": bool(v.get("network"))} for v in volumes()]
    try:
        serial = connected_device()
        model = shell("getprop ro.product.model", serial).stdout.strip()
        paths = {}
        for category, candidates in CATEGORIES.items():
            paths[category] = [p for p in candidates if shell("test -d " + shlex.quote(p), serial, 5).returncode == 0]
        return {**state, "connected": True, "serial": serial, "wifi": ":" in serial or "_adb-tls" in serial, "model": model or "Samsung", "paths": paths, "message": "الهاتف جاهز للنسخ."}
    except Exception as exc:
        return {**state, "connected": False, "message": str(exc)}


def browse(path, serial):
    path = storage_path(path, serial)
    if shell("test -d " + shlex.quote(path), serial).returncode:
        raise ValueError("المسار المختار ليس مجلدًا متاحًا.")
    entries, warnings = [], []
    cmd = "find " + shlex.quote(path + "/") + " -mindepth 1 -maxdepth 1 -exec stat -c '%s|%Y|%Z|%F|%n' {} +"
    result = shell(cmd, serial, 60)
    if result.returncode:
        warnings.append("بعض محتويات هذا المجلد غير قابلة للقراءة.")
    for line in result.stdout.splitlines():
        parts = line.split("|", 4)
        if len(parts) != 5:
            continue
        size, mod, chg, kind, name = parts
        try:
            item = normalize_path(name)
            entries.append({"name": posixpath.basename(item), "path": item, "is_dir": kind == "directory",
                            "size": None if kind == "directory" else int(size), "mod": int(mod) * 1000, "chg": int(chg) * 1000})
        except ValueError:
            warnings.append("تجاوزت أسماء تحتوي محارف غير مدعومة.")
    entries.sort(key=lambda item: (not item["is_dir"], item["name"].casefold()))
    return {"path": path, "parent": posixpath.dirname(path) if path != "/sdcard" else None,
            "serial": serial, "entries": entries, "warning": " ".join(sorted(set(warnings)))}


def exif_info(serial, path):
    try:
        from PIL import Image
    except ImportError:
        return {}
    tmp = tempfile.mkdtemp()
    try:
        dest = os.path.join(tmp, "x.jpg")
        if adb("pull", path, dest, serial=serial, timeout=60).returncode:
            return {}
        exif = Image.open(dest).getexif()
        sub = exif.get_ifd(0x8769)
        out = {}
        if sub.get(36867):
            out["التقاط الصورة"] = str(sub[36867])
        cam = " ".join(str(x) for x in (exif.get(271), exif.get(272)) if x)
        if cam:
            out["الكاميرا"] = cam
        if exif.get_ifd(0x8825):
            out["الموقع GPS"] = "محفوظ داخل الصورة"
        return out
    except Exception:
        return {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


META_DIR = DATA / ".appmeta"
def _find_aapt2():
    cands = sorted(glob.glob(str(Path.home() / "Library/Android/sdk/build-tools/*/aapt2")))
    return cands[-1] if cands else shutil.which("aapt2")


AAPT2 = _find_aapt2()     # اختياري: بدونه تظهر أسماء حزم التطبيقات بدل أسمائها الحقيقية
meta_lock = threading.Lock()
meta_started = set()
THUMB_DIR = DATA / ".thumbs"
thumb_sem = threading.Semaphore(3)
PIL_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
QL_EXT = {".heic", ".heif", ".tif", ".tiff", ".avif", ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".pages", ".key", ".numbers",
          ".mp4", ".mov", ".m4v", ".3gp", ".mkv", ".txt", ".rtf", ".csv", ".md"}
THUMB_MAX = 40 * 1024 * 1024


def make_thumb(serial, path, version, size=256, max_bytes=None):
    path = storage_path(path, serial)
    ext = posixpath.splitext(path)[1].lower()
    if ext not in PIL_EXT and ext not in QL_EXT:
        return None
    THUMB_DIR.mkdir(exist_ok=True)
    out = THUMB_DIR / (hashlib.sha1(f"{path}|{version}|{size}".encode()).hexdigest() + ".jpg")
    if out.exists():
        return out.read_bytes()
    with thumb_sem:
        fsz = shell("stat -c %s " + shlex.quote(path), serial).stdout.strip()
        if not fsz.isdigit() or int(fsz) > (max_bytes or THUMB_MAX):
            return None
        from PIL import Image, ImageOps
        tmp = tempfile.mkdtemp()
        try:
            src = os.path.join(tmp, "src" + ext)
            if adb("pull", path, src, serial=serial, timeout=120).returncode:
                return None
            if ext in PIL_EXT:
                image = Image.open(src)
            else:
                subprocess.run(["/usr/bin/qlmanage", "-t", "-s", str(size), "-o", tmp, src], capture_output=True, timeout=60)
                produced = src + ".png"
                if not os.path.exists(produced):
                    return None
                image = Image.open(produced)
            image = ImageOps.exif_transpose(image)
            image.thumbnail((size, size))
            image.convert("RGB").save(out, "JPEG", quality=78)
            return out.read_bytes()
        except Exception:
            return None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


_dsz = {}


_DSZ_FILE = None
_dsz_jobs = {}
_dsz_lock = threading.Lock()


def _dsz_path():
    return Path(os.environ.get("PB_DATA", Path.home() / "Library/Application Support/Phone Backup")) / ".dirsize.json"


def _dsz_load():
    if not _dsz:
        try:
            for k, v in json.loads(_dsz_path().read_text(encoding="utf-8")).items():
                _dsz[tuple(json.loads(k))] = (v["t"], v["out"])
        except Exception:
            pass


def _dsz_save():
    try:
        items = sorted(_dsz.items(), key=lambda kv: -kv[1][0])[:6000]
        _dsz_path().write_text(json.dumps({json.dumps(list(k)): {"t": t, "out": o} for k, (t, o) in items}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _dsz_compute(key, out):
    """يحسب الحجم في خيط خلفي ويحدّث out تدريجيًا (الأرقام الجزئية تُعرض فورًا)."""
    root, serial, path = key
    try:
        if root.startswith("rc:"):
            d = json.loads(rclone_src._run(["size", "--json", "--fast-list", rclone_src.spec(root, path)], 900))
            out.update(size=d.get("bytes", 0), files=d.get("count", 0))
        elif root:
            _b, t = cloud_resolve(root, path)
            from concurrent.futures import ThreadPoolExecutor as TPE

            def walk(top):
                size = files = dirs = 0
                stack = [top]
                while stack:
                    cur = stack.pop()
                    try:
                        with os.scandir(cur) as it:
                            for e in it:
                                try:
                                    if e.is_dir(follow_symlinks=False):
                                        dirs += 1
                                        stack.append(e.path)
                                    else:
                                        size += e.stat(follow_symlinks=False).st_size
                                        files += 1
                                except OSError:
                                    pass
                    except OSError:
                        pass
                    with _dsz_lock:  # تقدّم تدريجي لعرض رقم جزئي أثناء الحساب
                        out["size"] += size; out["files"] += files; out["dirs"] += dirs
                    size = files = dirs = 0
                return 0

            subs = []
            try:
                with os.scandir(t) as it:
                    for e in it:
                        try:
                            if e.is_dir(follow_symlinks=False):
                                out["dirs"] += 1; subs.append(e.path)
                            else:
                                out["size"] += e.stat(follow_symlinks=False).st_size; out["files"] += 1
                        except OSError:
                            pass
            except OSError:
                pass
            with TPE(8) as ex:
                list(ex.map(walk, subs))
        else:
            ser = connected_device(serial or None)
            q = shlex.quote(storage_path(path, ser))
            r = shell(f"du -sk {q} 2>/dev/null | cut -f1; find {q} -type f 2>/dev/null | wc -l; find {q} -mindepth 1 -type d 2>/dev/null | wc -l", ser, 600).stdout.split()
            if len(r) >= 3 and all(x.isdigit() for x in r[:3]):
                out.update(size=int(r[0]) * 1024, files=int(r[1]), dirs=int(r[2]))
            else:
                raise OSError("تعذّر قراءة الحجم")
        _dsz[key] = (time.time(), {k: out[k] for k in ("size", "files", "dirs")})
        out["ok"] = True
        _dsz_save()
    except Exception as e:
        out["error"] = str(e)
    finally:
        out["running"] = False


def dir_size(query):
    """حجم مجلد بكل ما فيه. الحساب يجري في الخلفية بلا حدّ زمني؛ يُعاد فورًا آخر قيمة معروفة (محفوظة على القرص)
    أو الرقم الجزئي الجاري، مع done=False إلى أن يكتمل."""
    root, path, serial = query.get("root", [""])[0], query.get("path", [""])[0], query.get("serial", [""])[0]
    fresh = query.get("fresh", [""])[0] == "1"
    key = (root, serial, path)
    _dsz_load()
    job = _dsz_jobs.get(key)
    hit = _dsz.get(key)
    if job and job["running"]:
        pass
    elif hit and not fresh and time.time() - hit[0] < 600:
        return dict(hit[1], done=True, partial=False)
    else:
        job = {"size": 0, "files": 0, "dirs": 0, "running": True, "t": time.time()}
        _dsz_jobs[key] = job
        threading.Thread(target=_dsz_compute, args=(key, job), daemon=True).start()
    deadline = time.time() + 2.5  # انتظار قصير: المجلدات الصغيرة تنتهي هنا فيصل الرقم النهائي بلا جولة ثانية
    while job["running"] and time.time() < deadline:
        time.sleep(0.05)
    if not job["running"]:
        if job.get("error"):
            if hit:
                return dict(hit[1], done=True, partial=False, stale=True)
            return {"size": None, "done": True, "error": job["error"]}
        return {"size": job["size"], "files": job["files"], "dirs": job["dirs"], "done": True, "partial": False}
    if hit:  # آخر قيمة معروفة أدق من رقم جزئي صغير
        return dict(hit[1], done=False, partial=True, stale=True, now=job["size"])
    return {"size": job["size"], "files": job["files"], "dirs": job["dirs"], "done": False, "partial": True}


def local_info(root, rel):
    arch_rel, inner = archives.split(rel)
    if inner is not None:
        _b, apath = cloud_resolve(root, arch_rel)
        e = archives.entry(apath, inner) if inner else {"name": apath.name, "size": apath.stat().st_size, "mtime": apath.stat().st_mtime, "is_dir": True}
        if not e:
            raise ValueError("العنصر غير موجود داخل الأرشيف.")
        return {"path": rel, "type": "dir" if e["is_dir"] else "file", "size": e["size"], "mod": int(e["mtime"] * 1000), "chg": int(e["mtime"] * 1000), "acc": 0,
                "birth": None, "perm": "—", "owner": "—",
                "extra": {"داخل أرشيف": apath.name, "التعديل": "متاح" if archives.writable(apath) else "للقراءة والاستخراج فقط"}}
    base, t = cloud_resolve(root, rel)
    st = t.stat()
    try:
        owner = pwd.getpwuid(st.st_uid).pw_name
    except Exception:
        owner = str(st.st_uid)
    out = {"path": rel or "/", "type": "dir" if t.is_dir() else "file", "size": st.st_size, "mod": int(st.st_mtime * 1000),
           "chg": int(st.st_ctime * 1000), "acc": int(st.st_atime * 1000),
           "birth": int(getattr(st, "st_birthtime", 0) * 1000) or None, "perm": statmod.filemode(st.st_mode), "owner": owner, "extra": {}}
    if t.is_dir():
        n = total = 0
        for dirpath, _d, files in os.walk(t):
            for f in files:
                n += 1
                try:
                    total += os.stat(os.path.join(dirpath, f)).st_size
                except OSError:
                    pass
            if n > 20000:
                break
        out["size"] = total
        out["extra"]["عدد الملفات"] = str(n) + ("+" if n > 20000 else "")
    elif t.suffix.lower() in (".jpg", ".jpeg") and st.st_size < 30 * 1024 * 1024:
        try:
            from PIL import Image
            exif = Image.open(t).getexif()
            sub = exif.get_ifd(0x8769)
            if sub.get(36867):
                out["extra"]["التقاط الصورة"] = str(sub[36867])
            cam = " ".join(str(x) for x in (exif.get(271), exif.get(272)) if x)
            if cam:
                out["extra"]["الكاميرا"] = cam
            if exif.get_ifd(0x8825):
                out["extra"]["الموقع GPS"] = "محفوظ داخل الصورة"
        except Exception:
            pass
    return out


def local_thumb(root, rel, version, size=256, max_bytes=None):
    THUMB_DIR.mkdir(exist_ok=True)
    out = THUMB_DIR / (hashlib.sha1(f"L|{root}|{rel}|{version}|{size}".encode()).hexdigest() + ".jpg")
    if out.exists():
        return out.read_bytes()
    if root.startswith("rc:"):  # حساب سحابي: نُنزّل الملف مؤقتًا ثم نصغّره
        ext = os.path.splitext(rel)[1].lower()
        if ext not in PIL_EXT and ext not in QL_EXT:
            return None
        st = rclone_src.stat(root, rel)
        if not st or st["is_dir"] or (st["size"] or 0) > min(max_bytes or THUMB_MAX, 60 * 1024 * 1024):
            return None
        dl = tempfile.mkdtemp()
        try:
            t = Path(dl) / posixpath.basename(rel)
            rclone_src.download(root, rel, t)
            return _thumb_from(t, out, size)
        except Exception:
            return None
        finally:
            shutil.rmtree(dl, ignore_errors=True)
    base, t = cloud_resolve(root, rel)
    ext = t.suffix.lower()
    if ext in ebook.EXTS and t.is_file():
        return ebook_card(t, out, size)
    if not t.is_file() or (ext not in PIL_EXT and ext not in QL_EXT) or t.stat().st_size > (max_bytes or THUMB_MAX):
        return None
    return _thumb_from(t, out, size)


def ios_thumb(udid, rel, version, size=256, max_bytes=None):
    THUMB_DIR.mkdir(exist_ok=True)
    out = THUMB_DIR / (hashlib.sha1(f"I|{udid}|{rel}|{version}|{size}".encode()).hexdigest() + ".jpg")
    if out.exists():
        return out.read_bytes()
    ext = os.path.splitext(rel)[1].lower()
    if ext not in PIL_EXT and ext not in QL_EXT:
        return None
    dl = tempfile.mkdtemp()
    try:
        t = Path(dl) / ("src" + ext)
        ios_src.pull(udid, rel, str(t))
        if t.stat().st_size > (max_bytes or 120 * 1024 * 1024):
            return None
        return _thumb_from(t, out, size)
    except Exception:
        return None
    finally:
        shutil.rmtree(dl, ignore_errors=True)


def ebook_card(t, out, size):
    """غلاف الكتاب إن وُجد، وإلا بطاقة بالعنوان والمؤلف."""
    if not ebook.available():
        return None
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    with thumb_sem:
        tmp = tempfile.mkdtemp()
        try:
            c = os.path.join(tmp, "c.jpg")
            if ebook.cover(t, c):
                im = ImageOps.exif_transpose(Image.open(c)).convert("RGB")
            else:
                inf = ebook.info(t)
                im = Image.new("RGB", (800, 1100), (34, 40, 52))
                d = ImageDraw.Draw(im)
                try:
                    f = ImageFont.truetype("/System/Library/Fonts/GeezaPro.ttc", 54)
                except Exception:
                    f = ImageFont.load_default()
                import textwrap
                y = 300
                for line in textwrap.wrap(inf.get("Title") or t.stem, 22)[:6] + [""] + textwrap.wrap(inf.get("Author(s)", ""), 26)[:2]:
                    d.text((400, y), line, font=f, fill=(235, 238, 245), anchor="mm"); y += 80
            im.thumbnail((size, size))
            im.save(out, "JPEG", quality=85)
            return out.read_bytes()
        except Exception:
            return None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def _thumb_from(t, out, size):
    ext = t.suffix.lower()
    with thumb_sem:
        from PIL import Image, ImageOps
        tmp = tempfile.mkdtemp()
        try:
            if ext in PIL_EXT:
                image = Image.open(t)
            else:
                src = t
                if "/Library/CloudStorage/" in str(t):
                    # معاينة الماك تعلق على ملفات Google Drive/OneDrive في مكانها؛ نسخة مؤقتة تُعاين فورًا
                    src = Path(tmp) / ("src" + ext)
                    shutil.copyfile(t, src)
                subprocess.run(["/usr/bin/qlmanage", "-t", "-s", str(size), "-o", tmp, str(src)], capture_output=True, timeout=25)
                produced = os.path.join(tmp, src.name + ".png")
                if not os.path.exists(produced):
                    return None
                image = Image.open(produced)
            image = ImageOps.exif_transpose(image)
            image.thumbnail((size, size))
            image.convert("RGB").save(out, "JPEG", quality=78 if size <= 256 else 88)
            return out.read_bytes()
        except Exception:
            return None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def storage_info(serial):
    r = shell("df -k /sdcard", serial, 15).stdout.strip().splitlines()
    parts = r[-1].split() if r else []
    if len(parts) >= 4 and parts[1].isdigit() and parts[3].isdigit():
        return {"total": int(parts[1]) * 1024, "free": int(parts[3]) * 1024}
    return {}


def adb_usage(serial, path):
    p = storage_path(path, serial)
    r = shell("cd " + shlex.quote(p) + " && du -sk * .[!.]* 2>/dev/null", serial, 240)
    children = []
    for line in r.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[0].isdigit():
            children.append({"name": parts[1], "size": int(parts[0]) * 1024})
    children.sort(key=lambda c: -c["size"])
    return {"children": children[:80], "total": sum(c["size"] for c in children)}


def info(path, serial):
    path = storage_path(path, serial)
    q = shlex.quote(path)
    r = shell("stat -c '%F|%s|%Y|%Z|%X|%A|%U' " + q, serial)
    parts = r.stdout.strip().split("|")
    if r.returncode or len(parts) != 7:
        raise ValueError("تعذر قراءة معلومات العنصر.")
    kind, size, mod, chg, acc, perm, owner = parts
    out = {"path": path, "type": "dir" if kind == "directory" else "file", "size": int(size),
           "mod": int(mod) * 1000, "chg": int(chg) * 1000, "acc": int(acc) * 1000, "perm": perm, "owner": owner, "extra": {}}
    if kind == "directory":
        kb = shell("du -sk " + q, serial, 120).stdout.split()
        cnt = shell("find " + q + " -type f | wc -l", serial, 120).stdout.strip()
        out["size"] = int(kb[0]) * 1024 if kb and kb[0].isdigit() else None
        out["extra"]["عدد الملفات"] = cnt
    elif posixpath.splitext(path)[1].lower() in (".jpg", ".jpeg") and int(size) < 30 * 1024 * 1024:
        out["extra"] = exif_info(serial, path)
    return out


def images(serial):
    result = shell("find /sdcard/ -type f -print0", serial, 180)
    paths = []
    skipped = False
    for item in result.stdout.split("\0"):
        if not item or posixpath.splitext(item)[1].lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            paths.append(normalize_path(item))
        except ValueError:
            skipped = True
    warning = "لم يسمح الهاتف بقراءة بعض المجلدات؛ القائمة تشمل الصور المتاحة فقط." if result.returncode else ""
    if skipped:
        warning += " تجاوزت أسماء تحتوي محارف غير مدعومة."
    paths = sorted(set(paths))
    return {"paths": paths, "count": len(paths), "serial": serial, "warning": warning,
            "scope": "/sdcard"}


CLOUD_BASE = Path.home() / "Library" / "CloudStorage"
ICLOUD_BASE = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
DEFAULT_DEST = Path.home() / "نسخ احتياطي"
PKG_RE = re.compile(r"^[A-Za-z0-9_.]+$")
ADDR_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}(:\d{2,5})?$")
WATCH_CFG = DATA / ".watch.json"
last_scan = 0.0


_vol_cache = {"t": 0.0, "v": []}


def volumes():
    """الأقراص الخارجية الموصولة بالكمبيوتر (USB، بطاقات...)."""
    if time.time() - _vol_cache["t"] < 5:
        return _vol_cache["v"]
    out = []
    try:
        mounts = subprocess.run(["/sbin/mount"], capture_output=True, text=True, timeout=8).stdout.splitlines()
    except Exception:
        mounts = []
    local = {}
    for line in mounts:
        m = re.match(r"^(/dev/\S+) on (/Volumes/.+?) \((\w+)(.*)\)$", line)
        if m:
            local[m.group(2)] = (m.group(3), m.group(4))
    try:
        entries = sorted(Path("/Volumes").iterdir())
    except Exception:
        entries = []
    for p in entries:
        try:
            if p.is_symlink() or not p.is_dir() or str(p) not in local:
                continue
            fs, flags = local[str(p)]
            if "nobrowse" in flags or (fs in ("apfs", "hfs") and "read-only" in flags):
                continue  # صور أقراص (dmg) وما شابهها
            du = safe_usage(p)
            out.append({"name": p.name, "path": str(p), "total": du.total, "free": du.free,
                        "fs": fs, "writable": os.access(p, os.W_OK)})
        except Exception:
            continue
    seen = {v["path"] for v in out}
    try:
        mounts = subprocess.run(["/sbin/mount"], capture_output=True, text=True, timeout=8).stdout.splitlines()
        for line in mounts:
            m = re.match(r"^(\S+) on (/Volumes/.+?) \((smbfs|nfs|afpfs|webdav)\b", line)
            if not m or m.group(2) in seen:
                continue
            mp = Path(m.group(2))
            try:
                du = safe_usage(mp)
            except OSError:
                continue
            out.append({"name": mp.name, "path": str(mp), "total": du.total, "free": du.free, "fs": m.group(3), "writable": os.access(mp, os.W_OK),
                        "network": True, "server": m.group(1)})
    except Exception:
        pass
    _vol_cache.update(t=time.time(), v=out)
    return out


def eject_volume(name):
    """إخراج آمن: يُنهي الكتابة المعلّقة ثم يفصل القرص. يرفض ما ليس ضمن الأقراص الظاهرة."""
    vol = next((v for v in volumes() if v["name"] == name), None)
    if not vol:
        raise ValueError("هذا القرص غير موجود.")
    cmd = ["/usr/sbin/diskutil", "unmount" if vol.get("network") else "eject", vol["path"]]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise ValueError("استغرق الإخراج وقتًا طويلًا؛ أغلق أي ملفات مفتوحة من القرص وأعد المحاولة.")
    _vol_cache["t"] = 0.0
    if r.returncode:
        msg = (r.stderr or r.stdout).strip()
        raise ValueError("لم يُخرَج القرص" + (": هناك ملفات مفتوحة منه." if "busy" in msg.lower() else f": {msg[-120:]}"))
    return {"ok": True, "message": f"أُخرج «{name}» بأمان — يمكنك نزعه الآن."}


def _disk(name, network_ok=False):
    vol = next((v for v in volumes() if v["name"] == name), None)
    if not vol or (vol.get("network") and not network_ok):
        raise ValueError("هذا القرص غير موجود أو ليس قرصًا محليًا.")
    return vol


def _diskutil(args, timeout=120):
    try:
        r = subprocess.run(["/usr/sbin/diskutil", *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ValueError("استغرقت العملية وقتًا طويلًا؛ أغلق الملفات المفتوحة من القرص وأعد المحاولة.")
    _vol_cache["t"] = 0.0
    if r.returncode:
        raise ValueError((r.stderr or r.stdout).strip()[-160:] or "فشلت العملية.")


def rename_volume(name, new):
    vol = _disk(name)
    new = (new or "").strip()
    if not new or "/" in new or len(new) > 32:
        raise ValueError("اسم غير صالح (حتى ٣٢ حرفًا بلا شرطة مائلة).")
    _diskutil(["rename", vol["path"], new], 60)
    return {"ok": True, "message": f"أُعيدت تسمية القرص إلى «{new}»."}


ERASE_FS = {"ExFAT": "ExFAT", "FAT32": "MS-DOS", "Mac": "JHFS+", "APFS": "APFS"}


def erase_volume(name, fs, new, confirm):
    """فرمتة: تمسح كل ما على هذا القسم نهائيًا. تُرفض ما لم يُكتب اسم القرص تأكيدًا."""
    vol = _disk(name)
    if confirm != name:
        raise ValueError("لم يُؤكَّد اسم القرص.")
    if fs not in ERASE_FS:
        raise ValueError("نظام ملفات غير معروف.")
    new = (new or name).strip()
    if fs == "FAT32":
        new = new.upper()[:11]
    if not new or "/" in new:
        raise ValueError("اسم غير صالح.")
    _diskutil(["eraseVolume", ERASE_FS[fs], new, vol["path"]], 900)
    return {"ok": True, "message": f"فُرمت القرص «{name}» وصار «{new}»."}


STREAM_DIR = DATA / ".stream"
EXTRA_MIME = {".m4a": "audio/mp4", ".opus": "audio/ogg", ".amr": "audio/amr", ".3ga": "audio/3gpp", ".flac": "audio/flac", ".mkv": "video/x-matroska",
              ".md": "text/plain", ".log": "text/plain", ".csv": "text/plain", ".json": "text/plain", ".py": "text/plain", ".js": "text/plain",
              ".html": "text/plain", ".xml": "text/plain", ".sh": "text/plain", ".srt": "text/plain", ".vtt": "text/vtt"}


def stream_source(query):
    """يعيد (نوع، حجم، قارئ(offset,count)) لملف من أي مصدر، للتشغيل والمعاينة دون حد للحجم."""
    path = query.get("path", [""])[0]
    ext = os.path.splitext(path)[1].lower()
    ctype = EXTRA_MIME.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"
    root = query.get("root", [""])[0]
    udid = query.get("udid", [""])[0]
    if udid:
        STREAM_DIR.mkdir(exist_ok=True)
        f = STREAM_DIR / (hashlib.sha1(f"ios|{udid}|{path}|{query.get('v', [''])[0]}".encode()).hexdigest() + ext)
        if not f.exists():
            tmp = str(f) + ".part"
            ios_src.pull(udid, path, tmp)
            os.replace(tmp, f)
        def read_ios(off, n):
            fh = open(f, "rb"); fh.seek(off); return fh, None
        return ctype, f.stat().st_size, read_ios
    if root.startswith("rc:"):
        st = rclone_src.stat(root, path)
        if not st or st["is_dir"]:
            raise ValueError("الملف غير موجود.")
        def read(off, n):
            p = subprocess.Popen([rclone_src.RCLONE, "cat", "--offset", str(off), "--count", str(n), rclone_src.spec(root, path)], stdout=subprocess.PIPE)
            return p.stdout, p
        return ctype, st["size"] or 0, read
    if root:
        _b, f = cloud_resolve(root, path)
    else:  # الهاتف أو الساعة: يُنزَّل مرة إلى ذاكرة مؤقتة ثم يُشغَّل منها
        serial = connected_device(query.get("serial", [None])[0])
        rp = storage_path(path, serial)
        STREAM_DIR.mkdir(exist_ok=True)
        f = STREAM_DIR / (hashlib.sha1(f"{serial}|{rp}|{query.get('v', [''])[0]}".encode()).hexdigest() + ext)
        if not f.exists():
            tmp = f.with_suffix(f.suffix + ".part")
            if adb("pull", rp, str(tmp), serial=serial, timeout=7200).returncode:
                raise ValueError("تعذّر جلب الملف من الجهاز.")
            tmp.rename(f)
            olds = sorted(STREAM_DIR.glob("*"), key=lambda x: x.stat().st_mtime)
            while sum(x.stat().st_size for x in olds) > 3 * 1024 ** 3 and len(olds) > 1:
                olds.pop(0).unlink(missing_ok=True)
    if not f.is_file():
        raise ValueError("الملف غير موجود.")
    def read(off, n):
        fh = open(f, "rb"); fh.seek(off); return fh, None
    return ctype, f.stat().st_size, read


def dupes_of(body):
    """مكررات المحتوى بين قائمة ملفات (نتائج بحث مثلًا): حجم متطابق ثم بصمة كاملة."""
    src, items = body.get("src") or {}, body.get("items") or []
    if not isinstance(items, list) or len(items) > 20000:
        raise ValueError("قائمة غير صالحة.")
    by_size = {}
    for it in items:
        if it.get("size"):
            by_size.setdefault(int(it["size"]), []).append(it)
    cands = [v for v in by_size.values() if len(v) > 1]
    groups = []
    root = src.get("root", "")
    job = {"cancel": False}
    for grp in cands:
        hashes = {}
        if src.get("type") == "adb":
            serial = connected_device(src.get("serial"))
            paths = [storage_path(i["path"], serial) for i in grp]
            out = shell("md5sum " + " ".join(shlex.quote(x) for x in paths), serial, 600).stdout
            hm = {ln.split(None, 1)[1].strip(): ln.split(None, 1)[0] for ln in out.splitlines() if len(ln.split(None, 1)) == 2}
            for i, rp in zip(grp, paths):
                if rp in hm:
                    hashes.setdefault(hm[rp], []).append(i)
        elif root.startswith("rc:"):
            for i in grp:
                try:
                    h = rclone_src._run(["md5sum", rclone_src.spec(root, i["path"])], 300).split()[0]
                    hashes.setdefault(h, []).append(i)
                except Exception:
                    pass
        else:
            for i in grp:
                try:
                    _b, f = cloud_resolve(root, i["path"])
                    hashes.setdefault(cleaner.hash_part(str(f)), []).append((i, f))
                except Exception:
                    pass
            full = {}
            for sub in hashes.values():
                if len(sub) < 2:
                    continue
                for i, f in sub:
                    try:
                        full.setdefault(cleaner.hash_full(job, str(f)), []).append(i)
                    except Exception:
                        pass
            hashes = full
        for sub in hashes.values():
            if len(sub) > 1:
                groups.append(sorted(sub, key=lambda x: (x.get("mod") or 0, len(x["path"]))))
    groups.sort(key=lambda g: -(g[0]["size"] * (len(g) - 1)))
    return {"groups": groups, "wasted": sum(g[0]["size"] * (len(g) - 1) for g in groups)}


def cloud_roots():
    roots = []
    if CLOUD_BASE.is_dir():
        roots += [{"id": p.name, "group": "cloud", "label": p.name.replace("GoogleDrive-", "Google Drive — ").replace("OneDrive-", "OneDrive — ").replace("\u200f", "").replace("iCloud\xa0Drive-iCloudDrive", "iCloud (نسخة قديمة)")}
                  for p in sorted(CLOUD_BASE.iterdir()) if p.is_dir()]
    if ICLOUD_BASE.is_dir():
        roots.append({"id": "icloud", "group": "cloud", "label": "iCloud Drive"})
    roots += rclone_src.remotes()
    roots += [{"id": "vol:" + v["name"], "group": "network" if v.get("network") else "disk", "label": ("🌐 " if v.get("network") else "💾 ") + v["name"]} for v in volumes()]
    roots.append({"id": "home", "group": "computer", "label": "هذا الكمبيوتر"})
    return roots


def cloud_allowed(base):
    """مجلد السحابة نفسه، ومرآة «Mi unidad/My Drive» إن كانت رابطًا."""
    allowed = [base]
    for name in ("Mi unidad", "My Drive"):
        link = base / name
        if link.is_symlink():
            allowed.append(link.resolve())
    return allowed


def inside(path, bases):
    return any(path == b or b in path.parents for b in bases)


def cloud_resolve(root, rel=""):
    if ".." in rel.split("/"):
        raise ValueError("مسار غير صالح.")
    if root == "home":
        base = Path.home().resolve()
        allowed = [base]
    elif root == "icloud":
        base = ICLOUD_BASE.resolve()
        if not base.is_dir():
            raise ValueError("iCloud Drive غير مفعّل على هذا الكمبيوتر.")
        allowed = [base]
    elif root == "uploads":
        import media
        base = media.get_upload_dir().resolve()
        base.mkdir(parents=True, exist_ok=True)
        allowed = [base]
    elif root.startswith("vol:"):
        if root[4:] not in {v["name"] for v in volumes()}:
            raise ValueError("القرص غير موصول.")
        base = (Path("/Volumes") / root[4:]).resolve()
        allowed = [base]
    else:
        base = (CLOUD_BASE / root).resolve()
        if base.parent != CLOUD_BASE.resolve() or not base.is_dir():
            raise ValueError("مجلد السحابة غير معروف.")
        allowed = cloud_allowed(base)
    target = (base / rel.lstrip("/")).resolve()
    if not inside(target, allowed):
        raise ValueError("مسار خارج المجلد المسموح.")
    return base, target


_LIBC = None


def _date_added(path, st):
    """«تاريخ الإضافة» كما يعرضه Finder (وسم Spotlight عبر getxattr)؛ وإلا تاريخ إنشاء الملف."""
    global _LIBC
    try:
        import ctypes
        if _LIBC is None:
            _LIBC = ctypes.CDLL(None, use_errno=True)
            _LIBC.getxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
        buf = ctypes.create_string_buffer(256)
        n = _LIBC.getxattr(os.fsencode(path), b"com.apple.metadata:kMDItemDateAdded", buf, 256, 0, 1)
        if n > 0:
            d = plistlib.loads(buf.raw[:n])
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            return int(d.timestamp() * 1000)
    except Exception:
        pass
    return int((getattr(st, "st_birthtime", None) or st.st_ctime) * 1000)


def cloud_browse(root, rel):
    if root.startswith("rc:"):
        return rclone_src.browse(root, rel)
    arch_rel, inner = archives.split(rel)
    if inner is not None:
        base, target = cloud_resolve(root, arch_rel)
        if not target.is_file() or not archives.is_archive_name(target.name):
            raise ValueError("ليس أرشيفًا مدعومًا.")
        return {"root": root, "path": rel, "entries": archives.browse(target, inner, arch_rel), "archive": {"writable": archives.writable(target), "name": target.name}}
    base, target = cloud_resolve(root, rel)
    if not target.is_dir():
        raise ValueError("ليس مجلدًا.")
    entries = []
    for e in os.scandir(target):
        if e.name in (".DS_Store", ".localized"):
            continue  # المخفية الأخرى تُعاد، والواجهة تخفيها ما لم يُطلب إظهارها
        if e.is_symlink():
            if not inside(Path(e.path).resolve(), cloud_allowed(base) if not (root.startswith('vol:') or root == 'home') else [base]):
                continue
        try:
            st = e.stat()
        except OSError:
            continue
        isdir = e.is_dir()
        entries.append({"name": e.name, "path": "/".join(x for x in (rel.strip("/"), e.name) if x), "is_dir": isdir,
                        "size": None if isdir else st.st_size, "mod": int(st.st_mtime * 1000), "chg": int(st.st_ctime * 1000),
                        "born": int((getattr(st, "st_birthtime", None) or st.st_ctime) * 1000), "added": _date_added(e.path, st),
                        "is_archive": (not isdir) and archives.is_archive_name(e.name)})
    entries.sort(key=lambda i: (not i["is_dir"], i["name"].casefold()))
    return {"root": root, "path": rel.strip("/"), "entries": entries}


def destinations():
    DEFAULT_DEST.mkdir(exist_ok=True)
    out = [{"label": "~/نسخ احتياطي (الافتراضي)", "path": str(DEFAULT_DEST)}]
    for r in cloud_roots():
        if r["group"] != "cloud":
            continue
        base = ICLOUD_BASE if r["id"] == "icloud" else CLOUD_BASE / r["id"]
        sub = next((base / n for n in ("Mi unidad", "My Drive") if (base / n).is_dir()), base)
        out.append({"label": r["label"] + " (متزامن)", "path": str(sub)})
    for v in volumes():
        if v["writable"]:
            out.append({"label": f"{'🌐' if v.get('network') else '💾'} {v['name']} (حرة {v['free'] / 1e9:.0f} GB)", "path": v["path"] + "/نسخ احتياطي"})
    return out


def exec_out(serial, command, timeout=60):
    r = subprocess.run([ADB, "-s", serial, "exec-out", command], capture_output=True, timeout=timeout)
    return r.stdout if r.returncode == 0 else b""


def app_meta(serial, pkg):
    """اسم التطبيق وأيقونته من ملف التثبيت (جزءان صغيران منه فقط)، مع حفظ النتيجة."""
    if not PKG_RE.match(pkg) or not AAPT2:
        return None
    META_DIR.mkdir(exist_ok=True)
    base = shell("pm path --user 0 " + pkg, serial, 15).stdout.splitlines()
    base = next((l[8:].strip() for l in base if l.startswith("package:")), "")
    if not base:
        return None
    key = hashlib.sha1((pkg + base).encode()).hexdigest()[:16]
    cache, icon_file = META_DIR / (pkg + ".json"), META_DIR / (pkg + ".png")
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("key") == key:
                return data
        except Exception:
            pass
    label, has_icon = "", False
    tmp = tempfile.mkdtemp()
    try:
        import zipfile
        q = shlex.quote(base)
        manifest = exec_out(serial, "unzip -p " + q + " AndroidManifest.xml")
        arsc = exec_out(serial, "unzip -p " + q + " resources.arsc", 120)
        mini = os.path.join(tmp, "m.apk")
        with zipfile.ZipFile(mini, "w", zipfile.ZIP_STORED) as z:
            z.writestr("AndroidManifest.xml", manifest)
            if arsc:
                z.writestr("resources.arsc", arsc)
        out = subprocess.run([AAPT2, "dump", "badging", mini], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stdout
        labels = dict(re.findall(r"^application-label(?:-([A-Za-z-]+))?:'(.*)'$", out, re.M))
        label = labels.get("ar") or labels.get("") or ""
        icon_path = (re.search(r"^application: .*icon='([^']+)'", out, re.M) or [None, ""])[1]
        stem = posixpath.splitext(posixpath.basename(icon_path))[0]
        rank = {"xxxhdpi": 6, "xxhdpi": 5, "xhdpi": 4, "hdpi": 3, "mdpi": 2, "ldpi": 1, "nodpi": 0}
        files = []
        if stem:
            res = subprocess.run([AAPT2, "dump", "resources", mini], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40).stdout
            block = re.search(r"resource 0x[0-9a-f]+ (?:mipmap|drawable)/" + re.escape(stem) + r"\n((?:      .*\n?)+)", res)
            for cfg, path in re.findall(r"\(([^)]*)\) \(file\) (\S+) type=", block.group(1) if block else ""):
                if path.lower().endswith((".png", ".webp")):
                    files.append((rank.get(cfg.split("-")[0], 0), path))
            if not files and icon_path.lower().endswith((".png", ".webp")):
                files = [(0, icon_path)]
        files.sort()
        if files:
            raw = exec_out(serial, "unzip -p " + q + " " + shlex.quote(files[-1][1]))
            if raw:
                from PIL import Image
                raw_path = os.path.join(tmp, "i")
                open(raw_path, "wb").write(raw)
                image = Image.open(raw_path).convert("RGBA")
                image.thumbnail((96, 96))
                image.save(icon_file, "PNG")
                has_icon = True
    except Exception:
        pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    data = {"pkg": pkg, "label": label, "icon": has_icon, "key": key}
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def app_meta_worker(serial, pkgs):
    for pkg in pkgs:
        try:
            app_meta(serial, pkg)
        except Exception:
            pass


def start_meta_prefetch(serial, pkgs):
    with meta_lock:
        if serial in meta_started:
            return
        meta_started.add(serial)
    chunks = [pkgs[i::3] for i in range(3)]
    for chunk in chunks:
        threading.Thread(target=app_meta_worker, args=(serial, chunk), daemon=True).start()


play_state = {"running": False, "done": 0, "total": 0}


def play_icon(pkg):
    """الأيقونة العامة من متجر Play (للتطبيقات التي لم تُستخرج أيقونتها محليًا)."""
    from PIL import Image
    req = urllib.request.Request(f"https://play.google.com/store/apps/details?id={pkg}&hl=en", headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    m = re.search(r'<meta property="og:image" content="([^"]+)"', html) or re.search(r'itemprop="image" content="([^"]+)"', html)
    if not m or not m.group(1).startswith("https://play-lh.googleusercontent.com/"):
        return False
    raw = urllib.request.urlopen(re.sub(r"=[^/=]*$", "", m.group(1)) + "=s96", timeout=15).read()
    tmp = tempfile.mkdtemp()
    try:
        path = os.path.join(tmp, "i")
        open(path, "wb").write(raw)
        image = Image.open(path).convert("RGBA")
        image.thumbnail((96, 96))
        image.save(META_DIR / (pkg + ".png"), "PNG")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    meta = META_DIR / (pkg + ".json")
    data = json.loads(meta.read_text(encoding="utf-8"))
    data["icon"] = True
    meta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return True


def play_worker(pkgs):
    def one(pkg):
        try:
            play_icon(pkg)
        except Exception:
            pass
        with lock:
            play_state["done"] += 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one, pkgs))
    with lock:
        play_state["running"] = False


def start_play_fetch():
    missing = [k for k, v in all_meta().items() if not v["icon"]]
    with lock:
        if play_state["running"]:
            return dict(play_state)
        play_state.update({"running": True, "done": 0, "total": len(missing)})
    threading.Thread(target=play_worker, args=(missing,), daemon=True).start()
    return dict(play_state)


genre_state = {"running": False, "done": 0, "total": 0}


def play_genre(pkg):
    """تصنيف التطبيق من متجر Play (للتجميع داخل الأداة فقط)."""
    meta = META_DIR / (pkg + ".json")
    if not meta.exists():
        return
    data = json.loads(meta.read_text(encoding="utf-8"))
    genre = "-"
    try:
        req = urllib.request.Request(f"https://play.google.com/store/apps/details?id={pkg}&hl=en", headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
        m = re.search(r'"applicationCategory":"([A-Z_]+)"', html)
        genre = m.group(1) if m else "-"
    except urllib.error.HTTPError:
        genre = "-"
    except Exception:
        return
    data["genre"] = genre
    meta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def genre_worker(pkgs):
    def one(pkg):
        try:
            play_genre(pkg)
        except Exception:
            pass
        with lock:
            genre_state["done"] += 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one, pkgs))
    with lock:
        genre_state["running"] = False


def start_genre_fetch():
    todo = [k for k, v in all_meta().items() if not v.get("genre")]
    with lock:
        if genre_state["running"]:
            return dict(genre_state)
        genre_state.update({"running": True, "done": 0, "total": len(todo)})
    threading.Thread(target=genre_worker, args=(todo,), daemon=True).start()
    return dict(genre_state)


FAV_FILE = DATA / ".favorites.json"


def favorites_get():
    try:
        d = json.loads(FAV_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def favorites_set(favs):
    """المفضلة تُحفظ داخل الأداة (ملف على الكمبيوتر) فتبقى بين الجلسات والنوافذ."""
    if not isinstance(favs, list) or len(favs) > 500:
        raise ValueError("قائمة المفضلة غير صالحة.")
    out, seen = [], set()
    for f in favs:
        if not isinstance(f, dict):
            continue
        fid = str(f.get("id") or f.get("src") or "")[:80]
        path = str(f.get("path", ""))[:1000]
        name = str(f.get("name", ""))[:200]
        under = bool(f.get("under", False))
        if not fid or (fid, path, under) in seen:
            continue
        seen.add((fid, path, under))
        out.append({"id": fid, "path": path, "name": name or path.split("/")[-1] or fid, "is_dir": bool(f.get("is_dir", True)), "added": int(f.get("added") or time.time() * 1000), "under": under})
    FAV_FILE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


APPGROUPS = DATA / ".appgroups.json"


def appgroups_get():
    try:
        return json.loads(APPGROUPS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def appgroups_set(pkg, cat):
    if not PKG_RE.match(pkg):
        raise ValueError("اسم حزمة غير صالح.")
    d = appgroups_get()
    if cat:
        d[pkg] = str(cat)[:40]
    else:
        d.pop(pkg, None)
    APPGROUPS.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


def _parse_ts(text):
    try:
        t = time.mktime(time.strptime(text, "%Y-%m-%d %H:%M:%S"))
        return int(t * 1000) if t > 978307200 else 0     # تجاهل التواريخ الفارغة (1969/1970)
    except Exception:
        return 0


def app_usage(serial):
    """آخر استخدام وعدد مرات الفتح (usagestats) + أحجام الكاش والبيانات (diskstats) لكل تطبيق."""
    usage = {}
    out = shell("dumpsys usagestats 2>/dev/null", serial, 180).stdout
    keys = ("lastTimeUsed", "lastTimeVisible", "lastTimeComponentUsed", "lastTimeFS")
    for line in out.splitlines():
        if "package=" not in line:
            continue
        m = re.search(r"package=(\S+)", line)
        if not m:
            continue
        u = usage.setdefault(m.group(1), {"last": 0, "launches": 0, "resumes": 0, "cache": None, "app": None, "data": None})
        for k in keys:
            mm = re.search(k + r'="([^"]+)"', line)
            if mm:
                u["last"] = max(u["last"], _parse_ts(mm.group(1)))
        lm = re.search(r"appLaunchCount=(\d+)", line)
        if lm:
            u["launches"] = max(u["launches"], int(lm.group(1)))
        if "type=ACTIVITY_RESUMED" in line or "type=MOVE_TO_FOREGROUND" in line:
            tm = re.search(r'time="([^"]+)"', line)
            if tm:
                u["last"] = max(u["last"], _parse_ts(tm.group(1)))
            u["resumes"] += 1
    ds = shell("dumpsys diskstats 2>/dev/null", serial, 120).stdout
    def arr(label):
        m = re.search(label + r": (\[.*?\])\s*$", ds, re.M)
        try:
            return json.loads(m.group(1)) if m else []
        except Exception:
            return []
    names, app, data, cache = arr("Package Names"), arr("App Sizes"), arr("App Data Sizes"), arr("Cache Sizes")
    for i, n in enumerate(names):
        u = usage.setdefault(n, {"last": 0, "launches": 0, "resumes": 0, "cache": None, "app": None, "data": None})
        u["app"] = app[i] if i < len(app) else None
        u["data"] = data[i] if i < len(data) else None
        u["cache"] = cache[i] if i < len(cache) else None
    return usage


def all_meta():
    out = {}
    if META_DIR.is_dir():
        for f in META_DIR.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                out[d["pkg"]] = {"label": d.get("label", ""), "icon": d.get("icon", False), "genre": d.get("genre", "")}
            except Exception:
                pass
    return out


def list_apps(serial):
    result = shell("pm list packages -3 -f --user 0", serial, 60)
    pkgs = sorted({line.rsplit("=", 1)[1].strip() for line in result.stdout.splitlines() if "=" in line})
    pkgs = [p for p in pkgs if PKG_RE.match(p)]
    if ":" not in serial and "_adb-tls" not in serial:
        start_meta_prefetch(serial, pkgs)
    return {"packages": pkgs, "serial": serial}


def phone_cfg():
    try:
        return json.loads((DATA / ".phone_wifi.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def phone_save(**kw):
    (DATA / ".phone_wifi.json").write_text(json.dumps({**phone_cfg(), **kw}), encoding="utf-8")


def phone_wifi_keeper():
    """الهاتف لاسلكيًا تلقائيًا: عند وصله بالكابل يُحفظ عنوانه على الواي فاي ويُفتح منفذ 5555؛
    وعند نزع الكابل يُعاد وصله لاسلكيًا ما دام على الشبكة نفسها."""
    armed = set()
    while True:
        time.sleep(15)
        try:
            rows = [l.split() for l in adb("devices").stdout.splitlines()[1:] if l.strip()]
            live = [r[0] for r in rows if len(r) > 1 and r[1] == "device"]
            usb = [d for d in live if ":" not in d and "_adb-tls" not in d and not is_watch(d)]
            if usb:
                d = usb[0]
                m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", shell("ip -f inet addr show wlan0", d, 8).stdout)
                if m:
                    phone_save(serial=d, ip=m.group(1))
                    if d not in armed and not backup_running and not any(x.startswith(m.group(1) + ":") for x in live):
                        if adb("tcpip", "5555", serial=d, timeout=15).returncode == 0:
                            armed.add(d)
                            time.sleep(4)
                            try_connect(f"{m.group(1)}:5555")
                continue
            armed.clear()
            cfg = phone_cfg()
            ip = cfg.get("ip")
            if not ip or any(x.startswith(ip + ":") or cfg.get("serial", "~") in x for x in live):
                continue
            if not try_connect(f"{ip}:5555"):
                for port in mdns_ports(ip):
                    if try_connect(f"{ip}:{port}"):
                        break
        except Exception:
            pass


def watch_cfg():
    try:
        return json.loads(WATCH_CFG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def watch_save(**kw):
    cfg = {**watch_cfg(), **kw}
    WATCH_CFG.write_text(json.dumps(cfg), encoding="utf-8")


_watch_cache = {}


def is_watch(serial):
    if serial in _watch_cache:
        return _watch_cache[serial]
    _watch_cache[serial] = False
    chars = shell("getprop ro.build.characteristics", serial, 8).stdout.lower()
    _watch_cache[serial] = "watch" in chars
    return _watch_cache[serial]


def watch_current(ip=None):
    """عنوان الساعة المتصلة الآن: بحسب النوع (ساعة) لا بحسب عنوان IP الذي قد يتغيّر."""
    for line in adb("devices").stdout.splitlines()[1:]:
        row = line.split()
        if len(row) < 2 or row[1] != "device":
            continue
        wireless = ":" in row[0] or "_adb-tls" in row[0]
        if not wireless:
            continue
        if (ip and row[0].startswith(ip + ":")) or is_watch(row[0]):
            if ":" in row[0]:
                watch_save(ip=row[0].split(":")[0], port=int(row[0].split(":")[1]))
            return row[0]
    return None


_ADB_HEALED = [0.0]


def _adb_state(addr):
    for line in adb("devices").stdout.splitlines()[1:]:
        row = line.split()
        if len(row) >= 2 and row[0] == addr:
            return row[1]
    return ""


def try_connect(addr):
    # إدخال قديم «offline» لنفس العنوان يجعل adb يقول «already connected» والجهاز غير صالح: نفصله أولًا ليبدأ اتصال نظيف
    if _adb_state(addr) in ("offline", "connecting"):
        adb("disconnect", addr, timeout=8)
        time.sleep(0.6)
    r = adb("connect", addr, timeout=12)
    text = (r.stdout + r.stderr).lower()
    if "no route to host" in text and time.time() - _ADB_HEALED[0] > 120:
        # خادم adb شغّله برنامج بلا إذن «الشبكة المحلية» (نسخة سابقة من زاجل أو الطرفية) ويبقى حيًّا بعده:
        # إن كان الهاتف يجيب فعلًا نعيد تشغيل الخادم من زاجل فيرث إذنه
        host, _, port = addr.partition(":")
        try:
            socket.create_connection((host, int(port or 5555)), 3).close()
            _ADB_HEALED[0] = time.time()
            adb("kill-server", timeout=10)
            r = adb("connect", addr, timeout=15)
            text = (r.stdout + r.stderr).lower()
        except OSError:
            pass
    ok = ("connected to" in text or "already connected" in text) and "cannot" not in text and "failed" not in text
    if ok:
        for _ in range(6):          # بعد الاتصال قد يبقى لحظات offline: ننتظر حتى يصير device
            st = _adb_state(addr)
            if st == "device":
                return True
            if st == "unauthorized":
                return False
            if st == "offline" and _ == 3:
                adb("disconnect", addr, timeout=8)
                adb("connect", addr, timeout=12)
            time.sleep(0.8)
        return _adb_state(addr) == "device"
    return False


def mdns_ports(ip):
    out = adb("mdns", "services", timeout=10).stdout
    return [int(m.group(1)) for m in re.finditer(re.escape(ip) + r":(\d+)", out)]


def scan_ports(ip):
    def probe(port):
        with socket.socket() as sock:
            sock.settimeout(0.4)
            return port if sock.connect_ex((ip, port)) == 0 else None
    with ThreadPoolExecutor(max_workers=600) as pool:
        return [p for p in pool.map(probe, range(30000, 50000)) if p]


def watch_reconnect(ip, allow_scan=True):
    """يجد منفذ الساعة الحالي تلقائيًا: ما حفظناه، ثم اكتشاف الشبكة، ثم مسح المنافذ."""
    global last_scan
    if watch_current(ip):
        return watch_current(ip)
    candidates = []
    saved = watch_cfg().get("port")
    candidates += mdns_ports(ip)
    if saved:
        candidates.append(saved)
    for port in dict.fromkeys(candidates):
        if try_connect(f"{ip}:{port}"):
            watch_save(ip=ip, port=port)
            return f"{ip}:{port}"
    if allow_scan and time.time() - last_scan > 120:
        last_scan = time.time()
        for port in scan_ports(ip):
            if try_connect(f"{ip}:{port}"):
                watch_save(ip=ip, port=port)
                return f"{ip}:{port}"
    return None


def watch_connect(addr):
    if not ADDR_RE.match(addr or ""):
        raise ValueError("اكتب عنوان الساعة، مثل: 192.168.1.20")
    ip = addr.split(":")[0]
    watch_save(ip=ip)
    if ":" in addr and try_connect(addr):
        watch_save(port=int(addr.split(":")[1]))
        current = addr
    else:
        current = watch_reconnect(ip)
    if not current:
        raise ValueError("لم أجد الساعة. تأكد أن «تصحيح ADB عبر Wi-Fi» مفعّل وأن شاشتها مضاءة، ثم أعد المحاولة.")
    model = shell("getprop ro.product.model", current).stdout.strip()
    return {"addr": current, "ip": ip, "model": model, "packages": list_apps(current)["packages"]}


def ensure_watch():
    ip = watch_cfg().get("ip")
    if not ip:
        raise ValueError("لم تُحفظ الساعة بعد. اتصل بها من تبويب «الساعة» مرة واحدة.")
    current = watch_current(ip) or watch_reconnect(ip)
    if not current:
        raise ValueError("الساعة غير متصلة الآن. فعّل التصحيح اللاسلكي وأضئ شاشتها.")
    return current


def watch_keeper():
    """يعيد وصل الساعة المحفوظة تلقائيًا كل نصف دقيقة."""
    while True:
        time.sleep(30)
        try:
            ip = watch_cfg().get("ip")
            if ip and not backup_running and not watch_current(ip):
                watch_reconnect(ip)
        except Exception:
            pass


PROTECTED_APPS = {"md.obsidian", "com.mohamad.khizana", "com.mohamad.smartnotehub", "com.mohamad.obsinote"}
PROTECTED_PATHS = {"/sdcard", "/sdcard/Android", "/sdcard/DCIM", "/sdcard/Pictures", "/sdcard/Download", "/sdcard/Documents",
                   "/sdcard/Music", "/sdcard/Movies", "/sdcard/Recordings"}
DELETE_LOG = DATA / "deletions.log"


def log_action(kind, items, ok, detail=""):
    with open(DELETE_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": dt.datetime.now().isoformat(timespec="seconds"), "kind": kind, "items": items, "ok": ok, "detail": detail[:500]}, ensure_ascii=False) + "\n")


def backup_roots():
    return [Path(d["path"]) for d in destinations()]


_index = {"time": 0.0, "by_size": {}, "keys": set()}
_sha_cache = {}


def backup_index(force=False):
    """فهرس بكل ملفات النسخ السابقة: بحسب الحجم، ومفتاح (الحجم، وقت التعديل). يُحدَّث كل دقيقة."""
    if not force and time.time() - _index["time"] < 60:
        return _index["by_size"]
    by_size, keys = {}, set()
    for root in backup_roots():
        for sub in ("sdcard", "watch/sdcard", "cloud"):
            for top in glob.glob(glob.escape(str(root)) + "/Samsung_*/" + sub):
                for dirpath, _dirs, files in os.walk(top):
                    for name in files:
                        full = os.path.join(dirpath, name)
                        try:
                            st = os.stat(full)
                        except OSError:
                            continue
                        keys.add((st.st_size, int(st.st_mtime)))
                        if sub != "cloud":
                            by_size.setdefault(st.st_size, []).append(full)
    _index.update(time=time.time(), by_size=by_size, keys=keys)
    return by_size


def sha256_file(path):
    st = os.stat(path)
    key = (path, st.st_size, st.st_mtime)
    if key not in _sha_cache:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        _sha_cache[key] = h.hexdigest()
    return _sha_cache[key]


def has_backup_copy(serial, remote_path):
    """هل يوجد على الكمبيوتر ملف مطابق لهذا الملف بالمحتوى (حتى لو تغيّر اسمه)؟"""
    out = shell("stat -c %s " + shlex.quote(remote_path) + "; sha256sum " + shlex.quote(remote_path), serial, 180).stdout.split()
    if len(out) < 2 or not out[0].isdigit():
        return False
    for candidate in backup_index().get(int(out[0]), []):
        if sha256_file(candidate) == out[1]:
            return True
    return False


def check_deletable(serial, path):
    """هل للملف نسخة مطابقة (بصمة) على الكمبيوتر؟"""
    path = storage_path(path, serial)
    if path in PROTECTED_PATHS:
        raise ValueError("هذا مجلد أساسي محمي: " + path)
    kind = shell("[ -d " + shlex.quote(path) + " ] && echo d || echo f", serial).stdout.strip()
    if kind == "d":
        files = [l for l in shell("find " + shlex.quote(path) + " -type f", serial, 120).stdout.splitlines() if l]
    else:
        files = [path]
    missing = 0
    for f in files[:5000]:
        if not has_backup_copy(serial, f):
            missing += 1
    return {"path": path, "files": len(files), "unverified": missing, "is_dir": kind == "d"}


def delete_paths(serial, paths, allow_unverified):
    report = []
    for raw in paths:
        try:
            info_ = check_deletable(serial, raw)
            if info_["unverified"] and not allow_unverified:
                report.append({"path": info_["path"], "ok": False, "detail": f"{info_['unverified']} ملف بلا نسخة مطابقة محفوظة."})
                continue
            r = shell("rm -rf " + shlex.quote(info_["path"]), serial, 300)
            shell("am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://" + shlex.quote(info_["path"]), serial, 20)
            report.append({"path": info_["path"], "ok": r.returncode == 0, "detail": (r.stderr or "").strip()[:200]})
        except Exception as exc:
            report.append({"path": str(raw), "ok": False, "detail": str(exc)})
    log_action("delete-files", [r["path"] for r in report], all(r["ok"] for r in report), json.dumps(report, ensure_ascii=False))
    return report


def uninstall_app(serial, pkg, keep_data, allow_protected):
    if not PKG_RE.match(pkg):
        raise ValueError("اسم حزمة غير صالح.")
    if pkg in PROTECTED_APPS and not allow_protected:
        raise ValueError("تطبيق محمي (من تطبيقاتك المهمة). لن يُحذف.")
    user_apps = set(list_apps(serial)["packages"])
    if pkg not in user_apps:
        raise ValueError("ليس تطبيقًا مثبّتًا من قبلك (تطبيق نظام)؛ لا يُحذف من هنا.")
    r = shell("pm uninstall --user 0 " + ("-k " if keep_data else "") + pkg, serial, 120)
    ok = "Success" in r.stdout
    log_action("uninstall", [pkg], ok, (r.stdout + r.stderr).strip())
    return {"package": pkg, "ok": ok, "detail": (r.stdout + r.stderr).strip()}


def install_apk(serial, path):
    """ملف apk واحد، أو حزمة .apks (ملفات مقسّمة مضغوطة)، أو مجلد فيه ملفات apk لتطبيق واحد."""
    f = Path(path).expanduser()
    tmp = None
    try:
        if f.is_dir():
            parts = sorted(f.glob("*.apk"))
        elif f.suffix.lower() == ".apks" and f.is_file():
            import zipfile
            tmp = Path(tempfile.mkdtemp(prefix="zajel-apks-"))
            with zipfile.ZipFile(f) as z:
                for n in z.namelist():
                    if n.lower().endswith(".apk") and "/" not in n.strip("/"):
                        z.extract(n, tmp)
            parts = sorted(tmp.glob("*.apk"))
        elif f.suffix.lower() == ".apk" and f.is_file():
            sib = sorted(f.parent.glob("split_*.apk"))  # ملف base.apk مسحوب مع أجزائه في مجلد واحد
            parts = [f] + [x for x in sib if x != f] if f.name == "base.apk" and sib else [f]
        else:
            raise ValueError("اختر ملف apk أو apks موجودًا على الكمبيوتر.")
        if not parts:
            raise ValueError("لا توجد ملفات apk في هذا المكان.")
        if len(parts) == 1:
            r = adb("install", "-r", "--user", "0", str(parts[0]), serial=serial, timeout=600)  # المستخدم الرئيسي فقط، لا نسخة في «التطبيقات المزدوجة»
        else:
            r = adb("install-multiple", "-r", "--user", "0", *[str(x) for x in parts], serial=serial, timeout=900)
        ok = "Success" in r.stdout
        log_action("install", [f.name], ok, (r.stdout + r.stderr).strip())
        return {"package": f.name, "ok": ok, "detail": (r.stdout + r.stderr).strip()}
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def pull_apks(serial, packages, dest=None, names=None):
    """التطبيق العادي ← «الاسم.apk»؛ والمقسّم (عدة ملفات) ← ملف واحد «الاسم.apks» يُثبَّت من زاجل كما هو."""
    import zipfile
    names = names or {}
    base_dest = Path(dest).expanduser() if dest else (Path.home() / "Downloads" / "زاجل APK")
    base_dest.mkdir(parents=True, exist_ok=True)
    results = []
    for pkg in packages:
        pkg = str(pkg).strip()
        if not PKG_RE.match(pkg):
            results.append({"package": pkg, "ok": False, "detail": "اسم حزمة غير صالح."})
            continue
        label = re.sub(r'[/\\:*?"<>|]+', " ", str(names.get(pkg) or pkg)).strip() or pkg
        tmp = Path(tempfile.mkdtemp(prefix="zajel-pull-"))
        try:
            r = shell("pm path " + pkg, serial, timeout=30)
            paths = [l.strip()[8:].strip() for l in r.stdout.splitlines() if l.strip().startswith("package:")]
            if not paths:
                results.append({"package": pkg, "ok": False, "detail": "تعذّر العثور على ملفات التطبيق."})
                continue
            got = []
            for p in paths:
                pr = adb("pull", p, str(tmp / posixpath.basename(p)), serial=serial, timeout=600)
                if pr.returncode:
                    raise ValueError((pr.stderr or pr.stdout).strip()[-160:])
                got.append(tmp / posixpath.basename(p))
            if len(got) == 1:
                out = base_dest / f"{label}.apk"
                shutil.move(str(got[0]), out)
            else:
                out = base_dest / f"{label}.apks"
                with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
                    for g in got:
                        z.write(g, g.name)
            results.append({"package": pkg, "ok": True, "file": str(out), "parts": len(got)})
        except Exception as e:
            results.append({"package": pkg, "ok": False, "detail": str(e)})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    overall_ok = any(r.get("ok") for r in results)
    log_action("pull-apk", packages, overall_ok, json.dumps(results, ensure_ascii=False))
    return {"ok": overall_ok, "results": results, "dest": str(base_dest)}


def installable_backups():
    out = []
    for root in backup_roots():
        for apk_dir in sorted(glob.glob(glob.escape(str(root)) + "/Samsung_*/apps/*"), reverse=True):
            d = Path(apk_dir)
            if d.is_dir() and any(d.glob("*.apk")):
                out.append({"package": d.name, "folder": str(d), "backup": d.parent.parent.name, "files": len(list(d.glob("*.apk")))})
    seen, unique = set(), []
    for item in out:
        if item["package"] not in seen:
            seen.add(item["package"])
            unique.append(item)
    return unique


def install_backup(serial, folder):
    d = Path(folder).resolve()
    if not any(d.parent.parent.parent == r.resolve() for r in backup_roots()) or d.parent.name != "apps":
        raise ValueError("المجلد ليس نسخة تطبيق محفوظة من هذه الأداة.")
    apks = sorted(str(p) for p in d.glob("*.apk"))
    if not apks:
        raise ValueError("لا توجد ملفات تثبيت في هذا المجلد.")
    r = adb("install-multiple", "-r", "--user", "0", *apks, serial=serial, timeout=600)
    ok = "Success" in r.stdout
    log_action("install", [d.name], ok, (r.stdout + r.stderr).strip())
    return {"package": d.name, "ok": ok, "detail": (r.stdout + r.stderr).strip()[-300:]}


def discover_hosts():
    """يكتشف خوادم SMB على الشبكة المحلية عبر Bonjour، ويحلّ عنوان كل جهاز."""
    def run(args, secs):
        try:
            return subprocess.run(["/usr/bin/dns-sd"] + args, capture_output=True, timeout=secs).stdout
        except subprocess.TimeoutExpired as exc:
            return exc.stdout or b""
        except Exception:
            return b""
    strip = lambda t: re.sub(r"[\u200e\u200f\u2066-\u2069]", "", t).strip()
    names = []
    for line in run(["-B", "_smb._tcp", "local."], 3).decode("utf-8", "replace").splitlines():
        if " Add " in line and "_smb._tcp." in line:
            name = line.split("_smb._tcp.", 1)[1].strip()
            if name and name not in names:
                names.append(name)
    own = set()
    for key in ("LocalHostName", "ComputerName"):
        try:
            own.add(subprocess.run(["/usr/sbin/scutil", "--get", key], capture_output=True, text=True, timeout=3).stdout.strip().lower().replace(" ", "-"))
        except Exception:
            pass
    own.add(socket.gethostname().split(".")[0].lower())
    out = []
    for name in names[:12]:
        txt = run(["-L", name, "_smb._tcp", "local."], 2).decode("utf-8", "replace")
        m = re.search(r"can be reached at (\S+?)\.?:\d+", txt)
        host = m.group(1).rstrip(".") if m else ""
        if host.split(".")[0].lower() in own:      # هذا الحاسوب نفسه: لا فائدة من الاتصال به
            continue
        out.append({"name": strip(name), "host": host})
    return out


def to_root(path_str):
    """يحوّل مسارًا مطلقًا إلى (root، مسار نسبي) ضمن المسموح به."""
    p = Path(path_str).resolve()
    home = Path.home().resolve()
    if p == home or home in p.parents:
        return "home", str(p.relative_to(home)) if p != home else ""
    for v in volumes():
        vp = Path(v["path"]).resolve()
        if p == vp or vp in p.parents:
            return "vol:" + v["name"], str(p.relative_to(vp)) if p != vp else ""
    raise ValueError("مسار خارج المصادر المسموحة.")


def clean_start(body):
    kind = str(body.get("kind", ""))
    options = body.get("options") or {}
    srcd = body.get("src") or {}
    if srcd.get("type") == "adb":
        serial = connected_device(srcd.get("serial"))
        path = storage_path(str(body.get("path") or "/sdcard"), serial)
        return cleaner.public(adbclean.start(serial, kind, path, options))
    if kind == "caches":
        base = target = Path.home().resolve()
    else:
        root = str(body.get("root", ""))
        if root.startswith("rc:"):
            import rclone_src as R
            return cleaner.public(cleaner.rc_start(kind, R.spec(root, str(body.get("path", "")).strip("/")), options))
        if kind in ("duplicates", "similar") and not (root == "home" or root.startswith("vol:")):
            raise ValueError("المكرر والمتشابه هنا يعملان على الكمبيوتر والأقراص فقط (حتى لا تُنزَّل الملفات). لفحص المكرر في Google Drive اختر حسابه المباشر من «☁ سحابة».")
        base, target = cloud_resolve(root, str(body.get("path", "")))
        if not target.is_dir():
            raise ValueError("اختر مجلدًا.")
    return cleaner.public(cleaner.start(kind, base, target, options))


def record_result(record):
    with lock:
        key = "completed" if record["ok"] else "errors"
        backup_state[key] = backup_state[key] + [record]
        backup_state["skipped"] = backup_state.get("skipped", 0) + record.get("skipped", 0)
        backup_state["copied"] = backup_state.get("copied", 0) + record.get("copied", 0)


def write_csv(target):
    rows = [["المسار النسبي", "الحجم (بايت)", "آخر تعديل"]]
    for p in sorted(target.rglob("*")):
        if p.is_file() and p.name not in ("backup-report.json", "metadata.csv"):
            st = p.stat()
            rows.append([str(p.relative_to(target)), st.st_size, dt.datetime.fromtimestamp(st.st_mtime).isoformat(sep=" ", timespec="seconds")])
    with open(target / "metadata.csv", "w", newline="", encoding="utf-8-sig") as fh:
        csv.writer(fh).writerows(rows)


def stat_many(serial, paths):
    out = {}
    for i in range(0, len(paths), 150):
        chunk = paths[i:i + 150]
        r = shell("stat -c '%F|%s|%Y|%n' " + " ".join(shlex.quote(p) for p in chunk), serial, 120)
        for line in r.stdout.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4 and parts[1].isdigit():
                out[parts[3]] = (parts[0], int(parts[1]), int(parts[2]))
    return out


def plan_phone(serial, sources):
    plan = {}
    stats = stat_many(serial, sources)
    for src in sources:
        st = stats.get(src)
        if not st:
            continue
        if st[0] == "directory":
            r = shell("find " + shlex.quote(src) + " -type f -exec stat -c '%s|%Y|%n' {} +", serial, 600)
            files = []
            for line in r.stdout.splitlines():
                parts = line.split("|", 2)
                if len(parts) == 3 and parts[0].isdigit():
                    files.append((parts[2], int(parts[0]), int(parts[1])))
            plan[src] = files
        else:
            plan[src] = [(src, st[1], st[2])]
    return plan


def known(keys, size, mtime):
    """هل لدينا ملف بهذا الحجم ووقت التعديل؟ (بتسامح ثانية، لأن أقراص FAT/exFAT تقرّب الوقت)"""
    return any((size, mtime + d) in keys for d in (-1, 0, 1))


def copy_incremental(src, dst, keys, incremental):
    copied = skipped = 0
    files = []
    if src.is_dir():
        for dirpath, _dirs, names in os.walk(src):
            files += [(Path(dirpath) / n, dst / Path(dirpath).relative_to(src) / n) for n in names]
    else:
        files = [(src, dst)]
    for f, d in files:
        if f.is_symlink():
            continue
        st = f.stat()
        if incremental and known(keys, st.st_size, int(st.st_mtime)):
            skipped += 1
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, d)
        copied += 1
    return copied, skipped


def copy_files(serial, jobs, target, initial_errors, want_csv, incremental=True):
    global backup_running
    results = list(initial_errors)
    try:
        target.mkdir(parents=True, exist_ok=False)
        backup_index(force=True)
        keys = _index["keys"]
        plan = {}
        phone_sources = [j["source"] for j in jobs if j["kind"] == "phone" and not j.get("watch")]
        if incremental and phone_sources:
            try:
                plan = plan_phone(serial, phone_sources)
            except Exception:
                plan = {}
        for job in jobs:
            kind, source = job["kind"], job["source"]
            with lock:
                backup_state["current"] = source
            try:
                if job.get("watch"):
                    current = watch_current() or watch_reconnect(watch_cfg().get("ip"), allow_scan=False)
                    if not current:
                        raise ValueError("الساعة غير متصلة الآن. أضئ شاشتها وفعّل التصحيح اللاسلكي.")
                    job["serial"] = current
                if kind == "phone":
                    src = storage_path(source, job["serial"])
                    prefix = job.get("prefix", "sdcard")
                    destination = target / prefix / src.removeprefix("/sdcard").lstrip("/")
                    files = plan.get(src) if not job.get("watch") else None
                    new = [f for f in files if not known(keys, f[1], f[2])] if files is not None else None
                    if new is not None and files and len(new) < len(files):
                        failed = 0
                        for f_path, _size, _mod in new:
                            dest_file = target / "sdcard" / f_path.removeprefix("/sdcard").lstrip("/")
                            dest_file.parent.mkdir(parents=True, exist_ok=True)
                            if adb("pull", "-a", f_path, str(dest_file), serial=job["serial"], timeout=3600).returncode:
                                failed += 1
                        record = {"source": src, "destination": str(destination), "ok": failed == 0, "copied": len(new) - failed,
                                  "skipped": len(files) - len(new), "detail": f"جديد {len(new)} · موجود سابقًا {len(files) - len(new)}" + (f" · فشل {failed}" if failed else "")}
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        result = adb("pull", "-a", src, str(destination), serial=job["serial"], timeout=3600)
                        record = {"source": src, "destination": str(destination), "ok": result.returncode == 0,
                                  "copied": len(files) if files else 0, "skipped": 0,
                                  "detail": (result.stdout + result.stderr).strip()[-2000:]}
                elif kind == "watchfs":
                    destination = target / "watch" / "sdcard"
                    destination.mkdir(parents=True, exist_ok=True)
                    result = adb("pull", "-a", "/sdcard/.", str(destination), serial=job["serial"], timeout=3600)
                    detail = (result.stdout + result.stderr).strip()[-2000:]
                    if result.returncode:
                        detail = "انقطع اتصال الساعة أو تعذّر النسخ. أعد الاتصال (قد يتغيّر المنفذ). " + detail
                    record = {"source": "watch:/sdcard", "ok": result.returncode == 0, "detail": detail}
                elif kind == "app":
                    out = shell("pm path --user 0 " + job["source"], job["serial"], 30)
                    if "not found" in out.stderr or "offline" in out.stderr:
                        raise ValueError("انقطع اتصال الجهاز أثناء النسخ. أعد الاتصال وجرّب مرة أخرى.")
                    paths = [l[8:].strip() for l in out.stdout.splitlines() if l.startswith("package:")]
                    if not paths:
                        raise ValueError("لم أجد ملفات التثبيت لهذا التطبيق.")
                    destination = target / job["folder"] / source
                    destination.mkdir(parents=True, exist_ok=True)
                    ok = all(adb("pull", p, str(destination), serial=job["serial"], timeout=600).returncode == 0 for p in paths)
                    record = {"source": source, "destination": str(destination), "ok": ok, "detail": f"{len(paths)} ملف تثبيت"}
                elif kind == "push":
                    base, src = cloud_resolve(job["root"], source)
                    remote_parent = posixpath.normpath("/sdcard/Download/من القرص/" + posixpath.dirname(source.strip("/")))
                    if not remote_parent.startswith("/sdcard/Download/من القرص"):
                        raise ValueError("وجهة غير صالحة على الهاتف.")
                    shell("mkdir -p " + shlex.quote(remote_parent), job["serial"], 30)
                    result = adb("push", str(src), remote_parent + "/", serial=job["serial"], timeout=3600)
                    record = {"source": str(src), "destination": "phone:" + remote_parent, "ok": result.returncode == 0,
                              "detail": (result.stdout + result.stderr).strip()[-500:]}
                else:  # cloud / disk
                    base, src = cloud_resolve(job["root"], source)
                    destination = target / "cloud" / job["root"].replace("/", "_") / job["source"].strip("/")
                    copied, skipped = copy_incremental(src, destination, keys, incremental)
                    record = {"source": str(src), "destination": str(destination), "ok": True, "copied": copied, "skipped": skipped,
                              "detail": f"جديد {copied} · موجود سابقًا {skipped}"}
            except Exception as exc:
                record = {"source": source, "ok": False, "detail": str(exc)}
            results.append(record)
            record_result(record)
        report = target / "backup-report.json"
        report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        if want_csv:
            write_csv(target)
        with lock:
            backup_state["report"] = str(report)
    except Exception as exc:
        record_result({"ok": False, "detail": str(exc)})
    finally:
        with lock:
            backup_running = False
            backup_state.update({"running": False, "current": ""})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{PORT}"

    def do_GET(self):
        if not self.valid_host():
            self.send_json({"error": "عنوان الخادم غير مسموح."}, 403)
            return
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        if agent_server.owns(url.path):
            agent_server.handle(self, "GET")
            return
        try:
            if url.path == "/api/health":
                if os.environ.get("PB_OVERLAY_ACTIVE") == "1":      # أقلع سليمًا: صفّر عدّاد المحاولات الفاشلة
                    try:
                        (ROOT / ".boots").write_text("0")
                    except OSError:
                        pass
                self.send_json({"app": APP_ID, "version": 3})
            elif url.path == "/api/status":
                self.send_json(status())
            elif url.path == "/api/browse":
                serial = connected_device(query.get("serial", [None])[0])
                self.send_json(browse(query.get("path", ["/sdcard"])[0], serial))
            elif url.path == "/api/thumb":
                serial = connected_device(query.get("serial", [None])[0])
                data = make_thumb(serial, query.get("path", [""])[0], query.get("v", [""])[0])
                if data is None:
                    self.send_response(204)
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    self.wfile.write(data)
            elif url.path == "/api/books/job":
                self.send_json(BOOKJOBS.get(query.get("id", [""])[0]) or {"state": "error", "error": "غير موجود"})
            elif url.path == "/api/kindle/status":
                self.send_json({"kindle": kindle_src.present()})
            elif url.path == "/api/kindle/browse":
                self.send_json(kindle_src.browse(query.get("path", ["/"])[0]))
            elif url.path == "/api/ios/devices":
                self.send_json({"devices": ios_src.devices()})
            elif url.path == "/api/ios/browse":
                self.send_json(ios_src.browse(query.get("udid", [""])[0], query.get("path", ["/"])[0]))
            elif url.path in ("/api/ithumb", "/api/ipreview"):
                big = url.path == "/api/ipreview"
                data = ios_thumb(query.get("udid", [""])[0], query.get("path", [""])[0], query.get("v", [""])[0], size=2000 if big else 256)
                if data is None:
                    self.send_response(204); self.end_headers()
                else:
                    self.send_response(200); self.send_header("Content-Type", "image/jpeg"); self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=86400"); self.end_headers(); self.wfile.write(data)
            elif url.path == "/api/dirsize":
                self.send_json(dir_size(query))
            elif url.path == "/api/lfs/info":
                self.send_json(local_info(query.get("root", [""])[0], query.get("path", [""])[0]))
            elif url.path == "/api/lthumb":
                data = local_thumb(query.get("root", [""])[0], query.get("path", [""])[0], query.get("v", [""])[0])
                if data is None:
                    self.send_response(204)
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    self.wfile.write(data)
            elif url.path == "/api/stream":
                ctype, size, read = stream_source(query)
                rng = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "") or "")
                start, end = 0, max(0, size - 1)
                if rng and (rng.group(1) or rng.group(2)):
                    if rng.group(1):
                        start = int(rng.group(1)); end = int(rng.group(2)) if rng.group(2) else end
                    else:
                        start = max(0, size - int(rng.group(2)))
                    end = min(end, size - 1, start + 32 * 1024 * 1024 - 1)  # قطع حتى 32MB لكل طلب
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                else:
                    self.send_response(200)
                n = max(0, end - start + 1)
                self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(n))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                fh, proc = read(start, n)
                try:
                    left = n
                    while left > 0:
                        b = fh.read(min(1 << 20, left))
                        if not b:
                            break
                        self.wfile.write(b)
                        left -= len(b)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    fh.close()
                    if proc:
                        proc.kill()
            elif url.path in ("/api/preview", "/api/lpreview"):
                if url.path == "/api/preview":
                    serial = connected_device(query.get("serial", [None])[0])
                    data = make_thumb(serial, query.get("path", [""])[0], query.get("v", [""])[0], size=2000, max_bytes=120 * 1024 * 1024)
                else:
                    data = local_thumb(query.get("root", [""])[0], query.get("path", [""])[0], query.get("v", [""])[0], size=2000, max_bytes=400 * 1024 * 1024)
                if data is None:
                    self.send_response(204)
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    self.wfile.write(data)
            elif url.path == "/api/network/discover":
                self.send_json({"hosts": discover_hosts()})
            elif url.path == "/api/search/job":
                job = finder.JOBS.get(query.get("id", [""])[0])
                if not job:
                    raise ValueError("البحث غير موجود.")
                self.send_json(finder.public(job))
            elif url.path == "/manifest.webmanifest":
                body = json.dumps({"name": "زاجل", "short_name": "زاجل", "description": "نسخ احتياطي وإدارة ملفات الهاتف والساعة والأقراص والسحابة", "start_url": "/",
                                   "scope": "/", "display": "standalone", "dir": "rtl", "lang": "ar", "background_color": "#14171c", "theme_color": "#2f6bff",
                                   "icons": [{"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                                             {"src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/sw.js" or url.path.startswith("/icons/"):
                f = ROOT / ("sw.js" if url.path == "/sw.js" else "icons/" + os.path.basename(url.path))
                if not f.is_file():
                    self.send_error(404)
                    return
                body = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript; charset=utf-8" if f.suffix == ".js" else "image/png")
                self.send_header("Content-Length", str(len(body)))
                if f.suffix == ".js":
                    self.send_header("Service-Worker-Allowed", "/")
                    self.send_header("Cache-Control", "no-store")
                else:
                    self.send_header("Cache-Control", "max-age=86400")
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/api/ops/get":
                self.send_json(fileops.details(query.get("id", [""])[0]))
            elif url.path == "/api/ops/list":
                self.send_json({"ops": fileops.listing()})
            elif url.path == "/api/clean/resolve":
                abs_path = query.get("path", [""])[0]
                if not os.path.isdir(abs_path):
                    raise ValueError("ليس مجلدًا.")
                root, rel = to_root(abs_path)
                self.send_json({"root": root, "path": rel})
            elif url.path == "/api/clean/rules":
                self.send_json({"rules": cleaner.load_rules(), "choices": cleaner.KEEP_CHOICES})
            elif url.path == "/api/clean/job":
                job = cleaner.JOBS.get(query.get("id", [""])[0])
                if not job:
                    raise ValueError("الفحص غير موجود.")
                self.send_json(cleaner.public(job))
            elif url.path == "/api/clean/thumb":
                job = cleaner.JOBS.get(query.get("job", [""])[0])
                pth = query.get("path", [""])[0]
                if not job or pth not in job["allowed"]:
                    raise ValueError("غير مسموح.")
                root, rel = to_root(pth)
                data = local_thumb(root, rel, query.get("v", [""])[0], size=int(query.get("s", ["256"])[0]) if query.get("s", ["256"])[0] in ("256", "2000") else 256, max_bytes=400 * 1024 * 1024)
                if data is None:
                    self.send_response(204)
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=3600")
                    self.end_headers()
                    self.wfile.write(data)
            elif url.path == "/api/adb/usage":
                self.send_json(adb_usage(connected_device(query.get("serial", [None])[0]), query.get("path", [""])[0]))
            elif url.path == "/api/sync":
                self.send_json(syncer.status())
            elif url.path == "/api/sync/overview":
                self.send_json(syncer.overview(query.get("refresh", [""])[0] == "1"))
            elif url.path == "/api/migrate":
                self.send_json(migrate.status())
            elif url.path == "/api/space":
                r = query.get("root", [""])[0]
                p = Path.home() if r in ("home", "icloud") or r.startswith(("GoogleDrive-", "OneDrive-")) or CLOUD_BASE.joinpath(r).is_dir() else None
                du = shutil.disk_usage(p) if p else None
                self.send_json({"total": du.total, "used": du.total - du.free, "free": du.free} if du else {})
            elif url.path == "/api/storage":
                self.send_json(storage_info(connected_device(query.get("serial", [None])[0])))
            elif url.path == "/api/info":
                serial = connected_device(query.get("serial", [None])[0])
                self.send_json(info(query.get("path", [""])[0], serial))
            elif url.path == "/api/apps":
                serial = connected_device(query.get("serial", [None])[0])
                self.send_json(list_apps(serial))
            elif url.path == "/api/appmeta":
                self.send_json({"meta": all_meta(), "play": dict(play_state), "genres": dict(genre_state), "overrides": appgroups_get()})
            elif url.path == "/api/favorites":
                self.send_json({"favs": favorites_get()})
            elif url.path == "/api/realpath":
                root = query.get("src", [""])[0]
                rel = query.get("path", [""])[0]
                try:
                    _base, target = cloud_resolve(root, rel)
                    self.send_json({"ok": True, "path": str(target)})
                except Exception as e:
                    self.send_json({"ok": False, "error": str(e)}, 400)
            elif url.path == "/api/appusage":
                self.send_json({"usage": app_usage(connected_device(query.get("serial", [None])[0]))})
            elif url.path == "/api/appicon":
                pkg = query.get("pkg", [""])[0]
                f = META_DIR / (pkg + ".png")
                if not PKG_RE.match(pkg) or not f.exists():
                    self.send_response(204)
                    self.end_headers()
                else:
                    data = f.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=3600")
                    self.end_headers()
                    self.wfile.write(data)
            elif url.path == "/api/backups/apps":
                self.send_json({"items": installable_backups(), "protected": sorted(PROTECTED_APPS)})
            elif url.path == "/api/destinations":
                self.send_json({"items": destinations()})
            elif url.path == "/api/cloud/roots":
                self.send_json({"roots": cloud_roots()})
            elif url.path == "/api/cloud/browse":
                self.send_json(cloud_browse(query.get("root", [""])[0], query.get("path", [""])[0]))
            elif url.path == "/api/images":
                serial = connected_device(query.get("serial", [None])[0])
                self.send_json(images(serial))
            elif url.path in ("/", "/index.html", "/app.js", "/ui.js", "/assistant.js", "/assistant_nav.js", "/sections.js"):
                js = url.path in ("/app.js", "/ui.js", "/assistant.js", "/assistant_nav.js", "/sections.js")
                body = (ROOT / (url.path[1:] if js else "samsung_backup.html")).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript; charset=utf-8" if js else "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
        except (ValueError, subprocess.TimeoutExpired) as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        if self.valid_host() and agent_server.owns(urlsplit(self.path).path):
            agent_server.handle(self, "POST")  # مساعد زاجل: المفتاح السري للوكيل، وOrigin للواجهة
            return
        if not self.valid_host() or self.headers.get("Origin") != f"http://127.0.0.1:{PORT}":
            self.send_json({"error": "مصدر الطلب غير مسموح."}, 403)
            return
        try:
            if self.path == "/api/choose-folder":
                result = subprocess.run(["/usr/bin/osascript", "-e", 'POSIX path of (choose folder with prompt "اختر مجلد حفظ النسخة")'],
                                        text=True, capture_output=True, timeout=90)
                if result.returncode and "-128" not in result.stderr:
                    raise RuntimeError(result.stderr.strip() or "تعذر فتح اختيار المجلد؛ اكتب المسار مباشرةً.")
                self.send_json({"path": result.stdout.rstrip("\n") if not result.returncode else "", "cancelled": result.returncode != 0})
            elif self.path == "/api/choose-file":
                result = subprocess.run(["/usr/bin/osascript", "-e", 'POSIX path of (choose file with prompt "اختر ملف التطبيق (APK)" default location (path to downloads folder))'],
                                        text=True, capture_output=True, timeout=300)
                if result.returncode and "-128" not in result.stderr:
                    raise RuntimeError(result.stderr.strip() or "تعذّر فتح نافذة الاختيار.")
                self.send_json({"path": result.stdout.rstrip("\n") if not result.returncode else "", "cancelled": result.returncode != 0})
            elif self.path.startswith("/api/install-apk-upload"):
                # ملفات مسحوبة من Finder: المتصفح لا يعطي مساراتها، فيُرسل كل ملف وحده في «دفعة» واحدة، ثم نثبّت الدفعة كاملة مع آخر ملف
                q = parse_qs(urlsplit(self.path).query)
                name = Path(q.get("name", ["app.apk"])[0]).name
                batch = re.sub(r"[^a-z0-9]", "", q.get("batch", [""])[0])[:24] or uuid.uuid4().hex[:12]
                last = q.get("last", ["1"])[0] == "1"
                size = int(self.headers.get("Content-Length", "0"))
                if not name.lower().endswith((".apk", ".apks")) or not 0 < size < 4 * 1024 ** 3:
                    raise ValueError("اسحب ملف apk أو apks.")
                d = Path(tempfile.gettempdir()) / ("zajel-apk-" + batch)
                d.mkdir(exist_ok=True)
                try:
                    with open(d / name, "wb") as fh:
                        left = size
                        while left:
                            chunk = self.rfile.read(min(left, 1 << 20))
                            if not chunk:
                                break
                            fh.write(chunk); left -= len(chunk)
                    if not last:
                        self.send_json({"ok": True, "pending": True})
                    else:
                        files = sorted(d.iterdir())
                        target = files[0] if len(files) == 1 else d
                        self.send_json(install_apk(connected_device(q.get("serial", [None])[0] or None), target))
                finally:
                    if last:
                        shutil.rmtree(d, ignore_errors=True)
            elif self.path == "/api/open":
                # فتح ملف بتطبيقه في الماك، أو إظهاره في Finder (reveal)
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                _b, t = cloud_resolve(str(body.get("root") or ""), str(body.get("path") or ""))
                if not t.exists():
                    raise ValueError("الملف غير موجود.")
                subprocess.Popen(["/usr/bin/open", "-R", str(t)] if body.get("reveal") else ["/usr/bin/open", str(t)])
                self.send_json({"ok": True})
            elif self.path == "/api/clean/reveal":
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                job = cleaner.JOBS.get(str(body.get("job", ""))); pth = str(body.get("path", ""))
                if not job or pth not in job["allowed"] or not pth.startswith("/") or not os.path.exists(pth):
                    raise ValueError("غير متاح.")
                subprocess.Popen(["/usr/bin/open", "-R", pth]); self.send_json({"ok": True})
            elif self.path == "/api/books/names":
                self.send_json(book_names_start(json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")))
            elif self.path in ("/api/sync", "/api/sync/run"):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                if self.path == "/api/sync":
                    self.send_json({"groups": syncer.save(body.get("groups"))})
                else:
                    threading.Thread(target=syncer.run, args=(str(body.get("id")),), daemon=True).start()
                    self.send_json({"ok": True})
            elif self.path in ("/api/migrate", "/api/migrate/run"):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                if self.path == "/api/migrate":
                    self.send_json({"rules": migrate.save_rules(body.get("rules"))})
                else:
                    threading.Thread(target=migrate.run_all, args=(body.get("id"),), daemon=True).start()
                    self.send_json({"ok": True})
            elif self.path == "/api/dupes":
                self.send_json(dupes_of(json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")))
            elif self.path == "/api/cloud/account":
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                self.send_json(rclone_src.manage(body.get("action"), body.get("name"), body.get("new")))
            elif self.path in ("/api/disk-rename", "/api/disk-erase"):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                if self.path == "/api/disk-rename":
                    self.send_json(rename_volume(body.get("name"), body.get("new")))
                else:
                    self.send_json(erase_volume(body.get("name"), body.get("fs"), body.get("new"), body.get("confirm")))
            elif self.path == "/api/eject":
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                self.send_json(eject_volume(body.get("name")))
            elif self.path == "/api/cloud/add":
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                self.send_json(rclone_src.add_account(body.get("kind"), body.get("name")))
            elif self.path in ("/api/uninstall", "/api/install", "/api/install-apk", "/api/phone-delete", "/api/phone-delete-check"):
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size))
                serial = connected_device(body.get("serial"))
                if self.path == "/api/phone-delete-check":
                    self.send_json({"items": [check_deletable(serial, x) for x in body.get("paths", [])[:2000]]})
                elif body.get("confirm") is not True:
                    raise ValueError("يلزم تأكيد صريح من المستخدم.")
                elif self.path == "/api/uninstall":
                    self.send_json(uninstall_app(serial, str(body.get("package", "")), bool(body.get("keep_data")), bool(body.get("allow_protected"))))
                elif self.path == "/api/install-apk":
                    self.send_json(install_apk(serial, str(body.get("path", ""))))
                elif self.path == "/api/install":
                    self.send_json(install_backup(serial, str(body.get("folder", ""))))
                else:
                    paths = body.get("paths", [])
                    if not isinstance(paths, list) or not paths or len(paths) > 2000:
                        raise ValueError("قائمة غير صالحة.")
                    self.send_json({"report": delete_paths(serial, paths, bool(body.get("allow_unverified")))})
            elif self.path == "/api/pull-apk":
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size) if size else b"{}")
                packages = body.get("packages", [])
                if not isinstance(packages, list) or not packages:
                    raise ValueError("يلزم تحديد حزمة تطبيق واحدة على الأقل.")
                serial = connected_device(body.get("serial"))
                dest = body.get("dest")
                self.send_json(pull_apks(serial, packages, dest, body.get("names") if isinstance(body.get("names"), dict) else None))
            elif self.path == "/api/search/multi":
                self.send_json(finder.start_multi(json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")))
            elif self.path in ("/api/search/start", "/api/search/cancel"):
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size))
                if self.path == "/api/search/start":
                    self.send_json(finder.start(body))
                else:
                    finder.cancel(str(body.get("id", "")))
                    self.send_json({"ok": True})
            elif self.path == "/api/network/connect":
                size = int(self.headers.get("Content-Length", "0"))
                url_ = str(json.loads(self.rfile.read(size)).get("url", "")).strip()
                if not re.fullmatch(r"(smb|afp|nfs)://[A-Za-z0-9._@:%/\-]{3,200}", url_):
                    raise ValueError("اكتب رابطًا مثل smb://اسم-الجهاز/المشاركة")
                subprocess.Popen(["/usr/bin/open", url_])
                self.send_json({"ok": True, "message": "تُفتح نافذة الاتصال من macOS؛ أدخل كلمة المرور هناك."})
            elif self.path == "/api/ops/pause":
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
                fileops.pause(str(body.get("id", "")), body.get("paused", True))
                self.send_json({"ok": True})
            elif self.path in ("/api/ops/start", "/api/ops/cancel"):
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size))
                if self.path == "/api/ops/start":
                    self.send_json(fileops.start(body))
                else:
                    fileops.cancel(str(body.get("id", "")))
                    self.send_json({"ok": True})
            elif self.path == "/api/clean/rules":
                size = int(self.headers.get("Content-Length", "0"))
                self.send_json({"rules": cleaner.save_rules(json.loads(self.rfile.read(size)))})
            elif self.path in ("/api/clean/start", "/api/clean/cancel", "/api/clean/remove"):
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size))
                if self.path == "/api/clean/start":
                    self.send_json(clean_start(body))
                elif self.path == "/api/clean/cancel":
                    job = cleaner.JOBS.get(str(body.get("id", "")))
                    if job:
                        job["cancel"] = True
                    self.send_json({"ok": True})
                else:
                    if body.get("confirm") is not True:
                        raise ValueError("يلزم تأكيد صريح من المستخدم.")
                    paths = body.get("paths", [])
                    if not isinstance(paths, list) or not paths or len(paths) > 5000:
                        raise ValueError("قائمة غير صالحة.")
                    job = cleaner.JOBS.get(str(body.get("job", "")))
                    if job and job.get("serial"):
                        self.send_json({"report": adbclean.remove(job, [str(x) for x in paths])})
                    else:
                        self.send_json({"report": cleaner.remove(str(body.get("job", "")), [str(x) for x in paths], bool(body.get("permanent")))})
            elif self.path == "/api/favorites":
                size = int(self.headers.get("Content-Length", "0"))
                self.send_json({"favs": favorites_set(json.loads(self.rfile.read(size)).get("favs"))})
            elif self.path == "/api/appgenres/fetch":
                self.send_json(start_genre_fetch())
            elif self.path == "/api/appgroups":
                size = int(self.headers.get("Content-Length", "0"))
                b = json.loads(self.rfile.read(size))
                self.send_json({"overrides": appgroups_set(str(b.get("pkg", "")), b.get("cat"))})
            elif self.path == "/api/appicons/fetch":
                self.send_json(start_play_fetch())
            elif self.path == "/api/watch/connect":
                size = int(self.headers.get("Content-Length", "0"))
                self.send_json(watch_connect(json.loads(self.rfile.read(size)).get("addr", "")))
            elif self.path == "/api/backup":
                self.start_backup()
            else:
                self.send_error(404)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def start_backup(self):
        global backup_running, backup_state
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 32 * 1024 * 1024:
            raise ValueError("حجم الطلب غير صالح.")
        payload = json.loads(self.rfile.read(size))
        if not isinstance(payload, dict):
            raise ValueError("طلب النسخ غير صالح.")
        categories, requested = payload.get("categories", []), payload.get("paths", [])
        if not isinstance(categories, list) or any(not isinstance(c, str) or c not in CATEGORIES for c in categories):
            raise ValueError("قائمة الفئات غير صالحة.")
        if not isinstance(requested, list) or len(requested) > 100000:
            raise ValueError("قائمة الملفات غير صالحة أو كبيرة جدًا.")
        apps, cloud = payload.get("apps", []), payload.get("cloud", [])
        if not isinstance(apps, list) or any(not isinstance(a, str) or not PKG_RE.match(a) for a in apps):
            raise ValueError("قائمة التطبيقات غير صالحة.")
        if not isinstance(cloud, list) or any(not isinstance(c, dict) for c in cloud):
            raise ValueError("قائمة السحابة غير صالحة.")
        watch = payload.get("watch")
        if watch:
            watch = {"addr": ensure_watch()}
        destination = payload.get("destination")
        if not isinstance(destination, str) or not destination.strip():
            raise ValueError("اختر مجلد الحفظ.")
        destination = Path(destination).expanduser()
        if not destination.is_dir():
            vols = [Path(v["path"]) for v in volumes() if v["writable"]]
            if destination.parent in vols:
                destination.mkdir()
            else:
                raise ValueError("المجلد غير موجود؛ اختر مجلدًا موجودًا على الكمبيوتر.")
        errors, paths = [], deduplicate(requested)
        serial = None
        if paths or categories or apps or any(c.get("to_phone") for c in cloud):
            serial = connected_device(payload.get("serial"))
        for category in categories:
            found = [p for p in CATEGORIES[category] if shell("test -d " + shlex.quote(p), serial, 5).returncode == 0]
            if not found:
                errors.append({"category": category, "ok": False, "detail": "لم يوجد مجلد متاح لهذه الفئة."})
            paths.extend(found)
        paths = deduplicate(paths)
        jobs = [{"kind": "phone", "source": p, "serial": serial} for p in paths]
        jobs += [{"kind": "app", "source": a, "serial": serial, "folder": "apps"} for a in apps]
        for c in cloud:
            jobs.append({"kind": "push" if c.get("to_phone") else "cloud", "root": str(c.get("root", "")), "source": str(c.get("path", "")), "serial": serial})
        wpaths = payload.get("watch_paths", [])
        if wpaths:
            if not isinstance(wpaths, list) or len(wpaths) > 5000:
                raise ValueError("قائمة ملفات الساعة غير صالحة.")
            waddr = ensure_watch()
            jobs += [{"kind": "phone", "source": normalize_path(w), "serial": waddr, "watch": True, "prefix": "watch/sdcard"} for w in deduplicate(wpaths)]
        if watch:
            if payload.get("watchfs"):
                jobs.append({"kind": "watchfs", "source": "watch", "serial": watch["addr"], "watch": True})
            for pkg in list_apps(watch["addr"])["packages"] if payload.get("watchapps") else []:
                jobs.append({"kind": "app", "source": pkg, "serial": watch["addr"], "folder": "watch/apps", "watch": True})
        if not jobs:
            raise ValueError("اختر عناصر للنسخ.")
        target = destination / ("Samsung_" + dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_" + uuid.uuid4().hex[:6])
        with lock:
            if backup_running:
                self.send_json({"error": "هناك عملية نسخ جارية بالفعل."}, 409)
                return
            backup_running = True
            backup_state = {"running": True, "target": str(target), "serial": serial, "completed": [],
                            "errors": errors, "total": len(jobs), "current": "", "skipped": 0, "copied": 0}
        worker = threading.Thread(target=copy_files, args=(serial, jobs, target, errors, bool(payload.get("csv", True)), bool(payload.get("incremental", True))), daemon=False)
        try:
            worker.start()
        except Exception:
            with lock:
                backup_running = False
                backup_state["running"] = False
            raise
        self.send_json({"started": True, "target": str(target), "total": len(jobs)})


def main():
    fileops.init(sys.modules[__name__])
    finder.init(sys.modules[__name__])
    adbclean.init(sys.modules[__name__], cleaner)
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    url = f"http://127.0.0.1:{PORT}/"
    try:
        with urllib.request.urlopen(url + "api/health", timeout=2) as response:
            existing = json.load(response)
        if existing.get("app") == APP_ID:
            if not args.no_browser:
                webbrowser.open(url)
            return
    except (OSError, ValueError):
        pass
    subprocess.run([ADB, "start-server"], capture_output=True, timeout=15)
    threading.Thread(target=watch_keeper, daemon=True).start()
    threading.Thread(target=phone_wifi_keeper, daemon=True).start()
    migrate.init(sys.modules[__name__], DATA)
    syncer.init(sys.modules[__name__], DATA)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    agent_server.init(sys.modules[__name__], DATA, PORT)
    print(f"Backup interface: {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
