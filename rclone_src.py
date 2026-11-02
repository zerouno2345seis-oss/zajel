"""حسابات سحابية عبر rclone — قراءة فقط (المرحلة ٢). كلمات المرور لا تمر من هنا أبدًا."""
import json, re, shutil, subprocess, time

_cache = {"remotes": (0, []), "dirs": {}}


def _clear():
    _cache["remotes"] = (0, [])
    _cache["dirs"].clear()

RCLONE = shutil.which("rclone") or "/opt/homebrew/bin/rclone"
KINDS = {"drive": "Google Drive", "onedrive": "OneDrive", "dropbox": "Dropbox", "box": "Box", "pcloud": "pCloud", "iclouddrive": "iCloud Drive"}
EXPORT = "docx,xlsx,pptx"  # ملفات Google الأصلية تُصدَّر إلى صيغ Office
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def _run(args, timeout=60):
    r = subprocess.run([RCLONE, *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise ValueError((r.stderr.strip().splitlines() or ["تعذّر الاتصال بالحساب."])[-1])
    return r.stdout


def remotes():
    t, v = _cache["remotes"]
    if time.time() - t < 5:
        return v
    out = _remotes()
    _cache["remotes"] = (time.time(), out)
    return out


def _remotes():
    try:
        names = [n.rstrip(":") for n in _run(["listremotes"], 10).split()]
        types = json.loads(_run(["config", "dump"], 10))
    except Exception:
        return []
    return [{"id": "rc:" + n, "group": "rclone", "label": n, "kind": KINDS.get(types.get(n, {}).get('type'), 'سحابة'), "email": info(n).get("email", ""), "used": info(n).get("used"), "total": info(n).get("total")} for n in names]


def browse(root, rel):
    key = (root, rel.strip("/"))
    hit = _cache["dirs"].get(key)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    res = _browse(root, rel)
    _cache["dirs"][key] = (time.time(), res)
    return res


def _browse(root, rel):
    name = root[3:]
    if not NAME_RE.match(name) or ".." in rel.split("/"):
        raise ValueError("مسار غير صالح.")
    items = json.loads(_run(["lsjson", "--drive-export-formats", EXPORT, f"{name}:{rel.strip('/')}"]) or "[]")
    from datetime import datetime
    entries = []
    for it in items:
        try:
            mod = int(datetime.fromisoformat(it["ModTime"].replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:
            mod = 0
        isdir = bool(it.get("IsDir"))
        entries.append({"name": it["Name"], "path": "/".join(x for x in (rel.strip("/"), it["Name"]) if x), "is_dir": isdir,
                        "size": None if isdir or (it.get("Size") or 0) < 0 else it.get("Size"), "mod": mod, "chg": mod, "is_archive": False})
    entries.sort(key=lambda i: (not i["is_dir"], i["name"].casefold()))
    return {"root": root, "path": rel.strip("/"), "entries": entries}


def add_account(kind, name):
    """ينشئ بطاقة الدخول ويفتح المتصفح للتفويض (OAuth)؛ يعمل في الخلفية."""
    if kind not in KINDS or not NAME_RE.match(name or ""):
        raise ValueError("نوع أو اسم غير صالح (حروف لاتينية وأرقام وشرطة فقط).")
    if "rc:" + name in [r["id"] for r in remotes()]:
        raise ValueError("هذا الاسم مستعمل.")
    _clear()
    if kind == "iclouddrive":  # كلمة مرور آبل ورمز التحقق يكتبهما المستخدم في الطرفية؛ الأداة لا تراهما
        import os, stat, tempfile
        fd, path = tempfile.mkstemp(suffix=".command", prefix="icloud-")
        with os.fdopen(fd, "w") as f:
            f.write(f"#!/bin/sh\nclear\necho 'iCloud: answer the questions below (Apple ID, password, 2FA code).'\necho\n"
                    f"'{RCLONE}' config create '{name}' iclouddrive --all\nrm -f '{path}'\necho\necho 'Done. You can close this window.'\n")
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        subprocess.Popen(["/usr/bin/open", "-a", "Terminal", path])
        return {"ok": True, "terminal": True}
    subprocess.Popen([RCLONE, "config", "create", name, kind], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True}


def _split(root, rel):
    name = root[3:]
    if not NAME_RE.match(name) or ".." in rel.split("/"):
        raise ValueError("مسار غير صالح.")
    return name, rel.strip("/")


def spec(root, rel):
    name, rel = _split(root, rel)
    return f"{name}:{rel}"


def stat(root, rel):
    """يعيد {'is_dir':..} أو None إن لم يوجد."""
    try:
        d = json.loads(_run(["lsjson", "--stat", "--drive-export-formats", EXPORT, spec(root, rel)], 60))
    except ValueError:
        return None
    return {"is_dir": bool(d.get("IsDir")), "size": d.get("Size")}


def download(root, rel, dest, on_proc=None):
    st = stat(root, rel)
    if st is None:
        raise ValueError("لم يعد موجودًا في السحابة.")
    _run_progress(["copyto", spec(root, rel), str(dest), "--drive-export-formats", EXPORT], None, on_proc=on_proc)
    return st


def _run_progress(args, cb, timeout=7200, on_proc=None):
    """يشغّل rclone ويقرأ إحصاءاته كل ثانية (بايتات منقولة) ويمرّرها إلى cb."""
    p = subprocess.Popen([RCLONE, *args, "--use-json-log", "--stats", "1s", "--stats-log-level", "NOTICE", "-v"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if on_proc:
        on_proc(p)
    last = ""
    for line in p.stderr:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        st = d.get("stats")
        if st and cb:
            cb(int(st.get("bytes") or 0))
        if d.get("level") == "error":
            last = d.get("msg", "")
    if p.wait():
        raise ValueError(last or "تعذّر النقل إلى السحابة.")


def upload(local, root, rel, progress=None, on_proc=None):
    _clear()
    if progress or on_proc:
        _run_progress(["copyto", str(local), spec(root, rel)], progress, on_proc=on_proc)
    else:
        _run(["copyto", str(local), spec(root, rel)], 7200)


def remove(root, rel, is_dir):
    _clear()
    """إلى سلة الخدمة (جوجل درايف يستعمل السلة افتراضيًا)."""
    _run(["purge" if is_dir else "deletefile", spec(root, rel)], 600)


# ---------- معلومات الحساب وإدارته ----------
import threading, urllib.request

_info = {}  # name -> (time, dict)


def _token(name):
    cfg = json.loads(_run(["config", "dump"], 10)).get(name, {})
    return cfg.get("type"), json.loads(cfg.get("token") or "{}").get("access_token")


def _fetch_info(name):
    try:  # يجدّد rclone المفتاح المنتهي قبل أن نقرأه
        _run(["lsf", "--max-depth", "0", name + ":"], 40)
    except Exception:
        pass
    typ, tok = _token(name)
    if not tok:
        return {}
    hdr = {"Authorization": "Bearer " + tok}
    try:
        if typ == "drive":
            req = urllib.request.Request("https://www.googleapis.com/drive/v3/about?fields=user(emailAddress,displayName),storageQuota(limit,usage)", headers=hdr)
            d = json.load(urllib.request.urlopen(req, timeout=15))
            q = d.get("storageQuota", {})
            return {"email": d.get("user", {}).get("emailAddress", ""), "owner": d.get("user", {}).get("displayName", ""),
                    "used": int(q["usage"]) if "usage" in q else None, "total": int(q["limit"]) if "limit" in q else None}
        if typ == "onedrive":
            req = urllib.request.Request("https://graph.microsoft.com/v1.0/me/drive?select=owner,quota", headers=hdr)
            d = json.load(urllib.request.urlopen(req, timeout=15))
            u = d.get("owner", {}).get("user", {})
            return {"email": u.get("email", ""), "owner": u.get("displayName", ""), "used": d.get("quota", {}).get("used"), "total": d.get("quota", {}).get("total")}
    except Exception:
        return {}
    return {}


def info(name, wait=False):
    hit = _info.get(name)
    if hit and time.time() - hit[0] < (600 if hit[1] else 60):
        return hit[1]
    def work():
        _info[name] = (time.time(), _fetch_info(name))
    if wait:
        work()
        return _info[name][1]
    _info[name] = (time.time(), hit[1] if hit else {})  # يمنع تكرار الطلب أثناء الجلب
    threading.Thread(target=work, daemon=True).start()
    return hit[1] if hit else {}


def _conf_path():
    from pathlib import Path
    return Path(_run(["config", "file"], 10).strip().splitlines()[-1].split(":", 1)[-1].strip())


def manage(action, name, new=None):
    if not NAME_RE.match(name or ""):
        raise ValueError("اسم غير صالح.")
    if "rc:" + name not in [r["id"] for r in remotes()]:
        raise ValueError("الحساب غير موجود.")
    if action == "info":
        d = dict(info(name, wait=True))
        try:
            a = json.loads(_run(["about", "--json", name + ":"], 40))
            d.update(used=a.get("used", d.get("used")), total=a.get("total", d.get("total")), trashed=a.get("trashed"))
        except Exception:
            pass
        return d
    if action == "delete":  # يزيل بطاقة الدخول فقط؛ ملفاتك في السحابة لا تُمسّ
        _run(["config", "delete", name], 20)
    elif action == "reconnect":
        subprocess.Popen([RCLONE, "config", "reconnect", name + ":"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif action == "rename":
        if not NAME_RE.match(new or ""):
            raise ValueError("اسم جديد غير صالح (حروف لاتينية وأرقام وشرطة).")
        if "rc:" + new in [r["id"] for r in remotes()]:
            raise ValueError("هذا الاسم مستعمل.")
        p = _conf_path()
        txt = p.read_text()
        if f"[{name}]" not in txt:
            raise ValueError("تعذّر العثور على الحساب في الإعدادات.")
        shutil.copy2(p, str(p) + ".bak")
        p.write_text(txt.replace(f"[{name}]", f"[{new}]", 1))
        _info.pop(name, None)
    else:
        raise ValueError("إجراء غير معروف.")
    _clear()
    return {"ok": True}
