"""الترحيل التلقائي: كلما وُصل الهاتف، تُفحص مجلدات محددة فيه، وكل ملف جديد يُنقل (أو يُنسخ)
إلى مجلد على الكمبيوتر. سجلّ دائم يمنع ترحيل الملف نفسه مرتين، ولا يُحذف شيء من الهاتف
إلا بعد التحقق من أن النسخة على الكمبيوتر بالحجم نفسه."""
from __future__ import annotations

import json
import os
import posixpath
import shlex
import threading
import time
import uuid
from pathlib import Path

import vision as V

M = None  # يُضبط من الخادم: وحدة samsung_backup_web
RULES = LEDGER = None
LOCK = threading.Lock()
STATE = {"running": False, "last": 0.0, "last_result": []}


class _Skip(Exception):
    pass


def init(module, data_dir: Path):
    global M, RULES, LEDGER
    M = module
    RULES, LEDGER = data_dir / ".migrate.json", data_dir / ".migrate_ledger.json"
    threading.Thread(target=_loop, daemon=True).start()


def _load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(p, v):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def rules():
    return _load(RULES, [])


def save_rules(items):
    out = []
    for r in items if isinstance(items, list) else []:
        src = str(r.get("src") or "").rstrip("/")
        dst = str(r.get("dst") or "").rstrip("/")
        droot, dpath = str(r.get("dst_root") or ""), str(r.get("dst_path") or "").strip("/")
        if droot:
            if ".." in dpath.split("/"):
                raise ValueError("مجلد وجهة غير صالح.")
            if not droot.startswith("rc:"):
                dst = str(M.cloud_resolve(droot, dpath)[1])  # مصدر محلي (قرص، مجلد متزامن…) ← مسار مطلق
                droot = ""
        ios = r.get("dev") == "ios"
        if not (src.startswith("/") if ios else src.startswith("/sdcard/")) or ".." in src.split("/") or not (dst.startswith("/") or droot):
            raise ValueError("مجلد غير صالح في إحدى القواعد.")
        exts = [e.lower().lstrip(".") for e in (r.get("exts") or []) if str(e).strip()]
        out.append({"id": r.get("id") or uuid.uuid4().hex[:8], "name": str(r.get("name") or posixpath.basename(src))[:60], "src": src, "dst": dst,
                    "dst_root": droot, "dst_path": dpath, "dst_label": str(r.get("dst_label") or "")[:120],
                    "dev": "ios" if ios else "adb", "udid": str(r.get("udid") or "") if ios else "",
                    "mode": "move" if r.get("mode") == "move" and not ios else "copy", "exts": exts, "content": [str(w).strip()[:30] for w in (r.get("content") or []) if str(w).strip()][:8], "keep_tree": bool(r.get("keep_tree", True)),
                    "enabled": bool(r.get("enabled", True))})
    with LOCK:
        _save(RULES, out)
    return out


def status():
    led = _load(LEDGER, {})
    return {"rules": rules(), "running": STATE["running"], "last": STATE["last"], "last_result": STATE["last_result"],
            "counts": {k: len(v) for k, v in led.items()}}


def _remote_files(serial, src):
    out = M.shell(f"find {shlex.quote(src)} -type f -exec stat -c '%s|%Y|%n' {{}} + 2>/dev/null", serial, 300).stdout
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3 and parts[0].isdigit():
            yield int(parts[0]), int(parts[1]), parts[2]


def run_rule(rule, serial):
    """يرحّل الجديد فقط. يعيد (عدد المرحّل، الأخطاء)."""
    led_all = _load(LEDGER, {})
    led = set(led_all.get(rule["id"], []))
    cloud = rule.get("dst_root", "").startswith("rc:")
    if cloud:
        import rclone_src as R
        import tempfile
        tmpdir = Path(tempfile.mkdtemp(prefix="pbmig-"))
        dst_root = tmpdir
    else:
        dst_root = Path(rule["dst"])
        dst_root.mkdir(parents=True, exist_ok=True)
    moved, errors, skipped = 0, [], 0
    op = M.fileops.new_op("copy" if rule["mode"] == "copy" else "move", {"name": "ترحيل تلقائي: " + rule["name"]}, 0)
    op["title"] = "ترحيل تلقائي: " + rule["name"]
    try:
        ios = rule.get("dev") == "ios"
        if ios:
            import ios_src
        files = [f for f in (ios_src.files(serial, rule["src"]) if ios else _remote_files(serial, rule["src"]))
                 if (not rule["exts"] or posixpath.splitext(f[2])[1].lower().lstrip(".") in rule["exts"])
                 and not posixpath.basename(f[2]).startswith(".")
                 and (not rule.get("content") or V.is_image(f[2]))]
        new = [f for f in files if f"{f[2]}|{f[0]}|{f[1]}" not in led]
        op["total"] = len(new)
        op["bytes_total"] = sum(f[0] for f in new) or None
        op["bytes_base"] = 0
        for size, mtime, rp in new:
            if op["cancel"]:
                break
            op["current"] = rp
            rel = posixpath.relpath(rp, rule["src"]) if rule["keep_tree"] else posixpath.basename(rp)
            target = dst_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not cloud and target.exists() and target.stat().st_size != size:
                stem, ext = os.path.splitext(target.name)
                i = 2
                while target.exists():
                    target = target.with_name(f"{stem} {i}{ext}")
                    i += 1
            try:
                if not (target.exists() and target.stat().st_size == size):
                    op["probe"] = str(target)
                    if ios:
                        ios_src.pull(serial, rp, str(target))
                    else:
                        r = M.adb("pull", "-a", rp, str(target), serial=serial, timeout=7200)
                        if r.returncode:
                            raise ValueError((r.stderr or r.stdout).strip()[-120:] or "تعذّر السحب.")
                if target.stat().st_size != size:
                    raise ValueError("الحجم لا يطابق؛ لم يُحذف الأصل.")
                if rule.get("content") and not V.matches(V.analyze([target]).get(str(target)), rule["content"]):
                    target.unlink(missing_ok=True)  # لا تطابق الكلمات: لا تُحفظ ولا تُمس في الجهاز
                    led.add(f"{rp}|{size}|{mtime}")
                    skipped += 1
                    raise _Skip()
                if cloud:  # رفع إلى الحساب السحابي ثم التحقق من الحجم هناك
                    crel = "/".join(x for x in (rule.get("dst_path", ""), rel) if x)
                    R.upload(target, rule["dst_root"], crel, progress=lambda b: op.__setitem__("rc_bytes", b), on_proc=lambda p: op.__setitem__("proc", p))
                    st = R.stat(rule["dst_root"], crel)
                    if not st or st.get("size") != size:
                        raise ValueError("لم أتحقق من النسخة في السحابة؛ لم يُحذف الأصل.")
                    target.unlink(missing_ok=True)
                    op["rc_bytes"] = 0
                if rule["mode"] == "move" and not ios:
                    M.shell("rm -f " + shlex.quote(rp), serial, 60)
                led.add(f"{rp}|{size}|{mtime}")
                moved += 1
            except _Skip:
                pass
            except Exception as exc:
                errors.append(f"{posixpath.basename(rp)}: {exc}")
                op["errors"].append(f"{rp}: {exc}")
            op["bytes_base"] += size
            op["probe"] = None
            op["done"] += 1
            with LOCK:
                led_all = _load(LEDGER, {})
                led_all[rule["id"]] = sorted(led)
                _save(LEDGER, led_all)
        op["detail"] = f"رُحّل {moved}" + (f" · لا يطابق الكلمات {skipped}" if skipped else "") + (f" · {len(errors)} فشل" if errors else "") + (" · لا جديد" if not new else "")
        op["state"] = "done" if not errors or moved else "error"
    except Exception as exc:
        op["state"] = "error"
        op["errors"].append(str(exc))
    finally:
        op["current"] = ""
        op["ended"] = time.time()
        M.fileops.persist(op)
        if cloud:
            import shutil
            shutil.rmtree(dst_root, ignore_errors=True)
    return moved, errors


def _targets():
    """الأجهزة المتاحة الآن: {"adb": serial أو None, "ios": {udid,…}}."""
    try:
        serial = M.connected_device()
    except Exception:
        serial = None
    try:
        import ios_src
        ios = {d["udid"] for d in ios_src.devices() if not d.get("asleep") and d.get("trusted", True)}
    except Exception:
        ios = set()
    return serial, ios


def _target_for(r, serial, ios):
    if r.get("dev") == "ios":
        u = r.get("udid") or ""
        return u if u in ios else (next(iter(ios)) if not u and ios else None)
    return serial


def run_all(only=None):
    if STATE["running"]:
        return
    STATE["running"] = True
    res = []
    try:
        serial, ios = _targets()
        for r in rules():
            if (only and r["id"] != only) or (not only and not r["enabled"]):
                continue
            t = _target_for(r, serial, ios)
            if not t:
                if only:
                    res.append({"id": r["id"], "name": r["name"], "moved": 0, "errors": ["الجهاز غير متصل."]})
                continue
            n, errs = run_rule(r, t)
            res.append({"id": r["id"], "name": r["name"], "moved": n, "errors": errs[:5]})
    finally:
        STATE.update(running=False, last=time.time(), last_result=res)


def _loop():
    """يفحص كل 15 ثانية؛ ويبدأ فورًا عند وصل جهاز من جديد، وإلا كل 10 دقائق."""
    seen = set()
    last_run = 0.0
    while True:
        time.sleep(15)
        try:
            active = [r for r in rules() if r["enabled"]]
            if not active:
                seen = set()
                continue
            serial, ios = _targets()
            now = {_target_for(r, serial, ios) for r in active} - {None}
            if now and (now - seen or time.time() - last_run > 600):
                last_run = time.time()
                run_all()
            seen = now
        except Exception:
            pass
