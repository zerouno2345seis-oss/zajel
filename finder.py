"""البحث الذكي: بالاسم و/أو اللاحقة داخل مصدر كامل (الكمبيوتر، الأقراص، السحابة، الهاتف، الساعة).
يعمل كمهمة خلفية تُستطلَع نتائجها، ويمكن إلغاؤها."""
from __future__ import annotations

import json
import os
import posixpath
import re
import shlex
import threading
import time
import uuid

M = None            # وحدة الخادم (adb وcloud_resolve...)
JOBS: dict[str, dict] = {}
MAX_RESULTS = 5000
LIMIT_SECONDS = 240
SOURCE_LIMIT = 75        # مهلة كل مصدر في البحث المتعدد: بعدها تُعرض نتائجه الجزئية ويُبلَّغ بتأخره
SLOW_AFTER = 20          # مصدر استغرق أكثر من هذا يُوسم «بطيء» في الحالة
CACHE_TTL = 120
_CACHE: dict = {}        # مفتاح (مصدر، كلمة، لواحق) ← (وقت، نتائج) للمصادر التي اكتمل بحثها بلا أخطاء
MULTI_WORKERS = 9


def init(module):
    global M
    M = module


def public(job, full=False):
    ents = job["entries"]
    return {"id": job["id"], "state": job["state"], "count": len(ents), "truncated": job["truncated"], "error": job["error"],
            "seconds": round(time.time() - job["started"], 1), "scanned": job.get("scanned"), "to_scan": job.get("to_scan"), "sources": job.get("sources"), "entries": ents if (full or job["state"] != "running") else ents[:300]}


def start(body):
    src = body.get("src") or {}
    q = str(body.get("q") or "").strip()
    exts = [e.lower().lstrip(".") for e in (body.get("exts") or []) if re.fullmatch(r"\.?[A-Za-z0-9_+\-]{1,12}", str(e))]
    content = [str(w).strip()[:30] for w in (body.get("content") or []) if str(w).strip()][:8]
    if not q and not exts and not content:
        raise ValueError("اكتب اسمًا أو اختر لاحقة.")
    scope = "all" if body.get("scope") == "all" else "here"
    path = str(body.get("path") or "")
    if "::" in path:
        raise ValueError("البحث داخل الأرشيف غير مدعوم؛ اخرج منه أولًا.")
    if src.get("type") == "adb":
        src["serial"] = M.connected_device(src.get("serial"))
    job = {"id": uuid.uuid4().hex[:10], "state": "running", "entries": [], "truncated": False, "error": "", "cancel": False, "started": time.time()}
    JOBS[job["id"]] = job
    if len(JOBS) > 10:
        for k in sorted(JOBS, key=lambda x: JOBS[x]["started"])[:-10]:
            JOBS.pop(k, None)
    threading.Thread(target=run, args=(job, src, path, q, exts, scope, content), daemon=True).start()
    return public(job)


def cancel(job_id):
    job = JOBS.get(job_id)
    if job:
        _stop(job)


def _stop(job):
    job["cancel"] = True
    for sub in job.get("subs") or []:
        _stop(sub)
    p = job.get("_proc")
    if p and p.poll() is None:
        try:
            p.kill()
        except Exception:
            pass


def run(job, src, path, q, exts, scope, content=None):
    if content:
        return run_content(job, src, path, q, exts, scope, content)
    try:
        if src.get("type") == "adb":
            run_adb(job, src, path, q, set(exts), scope)
        elif src.get("type") == "ios":
            run_ios(job, src, path, q, set(exts), scope)
        elif str(src.get("root", "")).startswith("rc:"):
            run_rclone(job, src, path, q, set(exts), scope)
        else:
            run_local(job, src, path, q, set(exts), scope)
        if job["state"] == "running":
            job["state"] = "cancelled" if job["cancel"] else "done"
    except Exception as exc:
        job["state"] = "error"
        job["error"] = str(exc)


# ---------- البحث بالكلمات داخل الصور (أشخاص، حيوانات، طعام…) ----------
REMOTE_LIMIT = 400  # صور الهاتف/الآيفون تُفحص عبر مصغّراتها؛ حدّ حتى لا يطول الانتظار
_vc = {"d": None}


def _vcache():
    if _vc["d"] is None:
        try:
            _vc["d"] = json.loads((M.DATA / ".vision_cache.json").read_text(encoding="utf-8"))
        except Exception:
            _vc["d"] = {}
    return _vc["d"]


def _vsave():
    try:
        d = _vc["d"] or {}
        if len(d) > 60000:
            for k in list(d)[:len(d) - 50000]:
                d.pop(k, None)
        (M.DATA / ".vision_cache.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def run_content(job, src, path, q, exts, scope, words):
    import vision as V
    import tempfile
    if not V.available():
        job.update(state="error", error="أداة تصنيف الصور غير متوفرة في هذا الجهاز.")
        return
    img = {e.lstrip(".") for e in V.IMG_EXT}
    sub = {"id": "", "state": "running", "entries": [], "truncated": False, "error": "", "cancel": False, "started": time.time()}
    run(sub, src, path, q, (set(exts) & img) or img, scope)
    if sub["error"]:
        job.update(state="error", error=sub["error"])
        return
    cands = [e for e in sub["entries"] if not e["is_dir"] and V.is_image(e["name"])]
    kind = "adb" if src.get("type") == "adb" else "ios" if src.get("type") == "ios" else "rc" if str(src.get("root", "")).startswith("rc:") else "local"
    if kind == "rc":
        job.update(state="error", error="البحث داخل الصور غير متاح للحسابات السحابية المباشرة؛ استعمله في المجلد المتزامن أو الكمبيوتر.")
        return
    if kind != "local" and len(cands) > REMOTE_LIMIT:
        cands, job["truncated"] = cands[:REMOTE_LIMIT], True
    job["scanned"], job["to_scan"] = 0, len(cands)
    cache, sid = _vcache(), src.get("root") or src.get("serial") or src.get("udid") or ""
    tmp = tempfile.mkdtemp(prefix="pbvis-")
    try:
        for k in range(0, len(cands), 24):
            if job["cancel"]:
                break
            chunk, todo = cands[k:k + 24], {}
            for e in chunk:
                key = f"{sid}|{e['path']}|{e.get('size')}|{e.get('mod')}"
                if key in cache:
                    continue
                try:
                    if kind == "local":
                        fp = str(M.cloud_resolve(src["root"], e["path"])[1])
                    else:
                        data = (M.make_thumb(src["serial"], e["path"], e.get("mod")) if kind == "adb"
                                else M.ios_thumb(src["udid"], e["path"], e.get("mod")))
                        if not data:
                            continue
                        fp = os.path.join(tmp, f"{len(todo)}.jpg")
                        with open(fp, "wb") as fh:
                            fh.write(data)
                    todo[fp] = key
                except Exception:
                    continue
            if todo:
                res = V.analyze(list(todo))
                for fp, key in todo.items():
                    info = res.get(fp) or {}
                    cache[key] = {"l": {a: round(b, 2) for a, b in (info.get("labels") or {}).items()}, "f": info.get("faces", 0), "s": bool(info.get("screenshot"))}
            for e in chunk:
                c = cache.get(f"{sid}|{e['path']}|{e.get('size')}|{e.get('mod')}")
                if c and V.matches({"labels": c["l"], "faces": c["f"], "screenshot": c["s"]}, words):
                    if not add(job, e["name"], e["path"], False, e["size"], e["mod"], e["chg"], e.get("folder", "")):
                        return
            job["scanned"] += len(chunk)
        _vsave()
        job["state"] = "cancelled" if job["cancel"] else "done"
        job["truncated"] = job["truncated"] or sub["truncated"]
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def limit_of(job):
    return job.get("limit") or LIMIT_SECONDS


def matches(name, q, exts):
    low = name.lower()
    if q and q.lower() not in low:
        return False
    if exts:
        ext = os.path.splitext(low)[1].lstrip(".")
        return ext in exts
    return True


def add(job, name, path, is_dir, size, mod, chg, folder, born=None):
    if len(job["entries"]) >= MAX_RESULTS:
        job["truncated"] = True
        return False
    e = {"name": name, "path": path, "is_dir": is_dir, "size": None if is_dir else size, "mod": mod, "chg": chg, "folder": folder, "born": born}
    job["entries"].append(e)
    par = job.get("parent")
    if par is not None:      # بحث متعدد: تصل النتيجة إلى الواجهة فور إيجادها دون انتظار انتهاء المصدر
        par["entries"].append(e | {"sid": job["sid"]})
    return True


def walk_roots(root_id, base, target, path, scope):
    """قائمة (مجلد حقيقي، بادئة المسار النسبي) للمرور عليها. تدعم مرآة Drive (رابط Mi unidad)."""
    prefix = "" if scope == "all" else path.strip("/")
    roots = [(target, prefix)]
    if scope == "all" and not (root_id == "home" or root_id.startswith("vol:")):
        for name in ("Mi unidad", "My Drive"):
            link = base / name
            if link.is_symlink():
                roots.append((link.resolve(), name))
    return roots


def _spotlight(job, target, root_prefix, q, exts, skip, show_hidden, seen, lock):
    """نتائج فورية من فهرس Spotlight (أجزاء من الثانية) قبل المرور الكامل. تُهمَل بصمت إن لم يكن المكان مفهرسًا."""
    import subprocess
    conds = []
    if q:
        conds.append('kMDItemDisplayName == "*%s*"cd' % q.replace("\\", "\\\\").replace('"', '\\"'))
    if exts:
        conds.append("(" + " || ".join('kMDItemFSName == "*.%s"c' % e.replace('"', "") for e in sorted(exts)) + ")")
    if not conds:
        return
    try:
        r = subprocess.run(["/usr/bin/mdfind", "-onlyin", str(target), " && ".join(conds)], capture_output=True, text=True, timeout=25)
    except Exception:
        return
    tp = str(target).rstrip("/")
    for line in r.stdout.splitlines()[:MAX_RESULTS]:
        if job["cancel"]:
            return
        if not line.startswith(tp + "/"):
            continue
        rel = line[len(tp) + 1:]
        parts = rel.split("/")
        if any(x in skip or (not show_hidden and x.startswith(".")) for x in parts):
            continue
        try:
            st = os.stat(line)
        except OSError:
            continue
        is_dir = os.path.isdir(line)
        if exts and is_dir:
            continue
        key = "/".join(x for x in (root_prefix, rel) if x)
        with lock:
            if key in seen:
                continue
            seen.add(key)
            folder = "/".join(x for x in (root_prefix, "/".join(parts[:-1])) if x)
            if not add(job, parts[-1], key, is_dir, 0 if is_dir else st.st_size, int(st.st_mtime * 1000), int(st.st_ctime * 1000), folder, int(getattr(st, "st_birthtime", 0) * 1000) or None):
                return


def run_local(job, src, path, q, exts, scope):
    """بحث محلي سريع: فهرس Spotlight فورًا، ثم مرور متوازٍ (ثمانية خيوط على المجلدات العليا) يكمل ما لم يُفهرس."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    base, target = M.cloud_resolve(src["root"], "" if scope == "all" else path)
    root_id = src["root"]
    skip = {"node_modules", "Library", ".Trash"} if root_id == "home" and scope == "all" else {"node_modules"}
    show_hidden = q.startswith(".")
    lock, seen = threading.Lock(), set()
    stop = {"v": False}

    def over():
        if job["cancel"] or stop["v"]:
            return True
        if time.time() - job["started"] > limit_of(job):
            job["truncated"] = job["timed_out"] = True
            stop["v"] = True
            return True
        return False

    def scan(walk_root, prefix, start, shallow):
        for dirpath, dirs, files in os.walk(start):
            if over():
                return
            dirs[:] = [] if shallow else [d for d in dirs if (show_hidden or not d.startswith(".")) and d not in skip and not os.path.islink(os.path.join(dirpath, d))]
            rel_dir = os.path.relpath(dirpath, walk_root)
            rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
            folder = "/".join(x for x in (prefix, rel_dir) if x)
            batch = []
            if not exts:
                batch += [(d, True) for d in os.listdir(dirpath) if matches(d, q, set()) and (show_hidden or not d.startswith(".")) and d not in skip and os.path.isdir(os.path.join(dirpath, d))] if shallow else [(d, True) for d in dirs if matches(d, q, set())]
            batch += [(f, False) for f in files if (show_hidden or not f.startswith(".")) and matches(f, q, exts)]
            for name, is_dir in batch:
                try:
                    st = os.stat(os.path.join(dirpath, name))
                except OSError:
                    continue
                key = "/".join(x for x in (folder, name) if x)
                with lock:
                    if key in seen:
                        continue
                    seen.add(key)
                    if not add(job, name, key, is_dir, 0 if is_dir else st.st_size, int(st.st_mtime * 1000), int(st.st_ctime * 1000), folder, int(getattr(st, "st_birthtime", 0) * 1000) or None):
                        stop["v"] = True
                        return

    for walk_root, prefix in walk_roots(root_id, base, target, path, scope):
        _spotlight(job, walk_root, prefix, q, exts, skip, show_hidden, seen, lock)
        scan(walk_root, prefix, walk_root, True)  # ملفات المستوى الأول
        try:
            subs = [e.path for e in os.scandir(walk_root) if e.is_dir(follow_symlinks=False) and (show_hidden or not e.name.startswith(".")) and e.name not in skip]
        except OSError:
            subs = []
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda sd: scan(walk_root, prefix, sd, False), subs))
        if over():
            return


def run_adb(job, src, path, q, exts, scope):
    serial = src["serial"]
    start_path = M.storage_path("/sdcard" if scope == "all" else (path or "/sdcard"), serial)
    conds = []
    if q:
        conds.append("-iname " + shlex.quote("*" + q + "*"))
    if exts:
        conds.append("\\( " + " -o ".join("-iname " + shlex.quote("*." + e) for e in sorted(exts)) + " \\)")
    typ = "-type f " if exts else ""
    prune = "-path /sdcard/Android -prune -o " if start_path == "/sdcard" else ""
    cmd = f"find {shlex.quote(start_path.rstrip(chr(47)) + chr(47))} {prune}{typ}{' '.join(conds)} -exec stat -c '%F|%s|%Y|%Z|%n' {{}} + 2>/dev/null"
    try:
        r = M.shell(cmd, serial, limit_of(job))
    except Exception as exc:
        if "timed out" in str(exc).lower() or "timeout" in str(exc).lower():
            job["truncated"] = job["timed_out"] = True
            return
        raise
    for line in r.stdout.splitlines():
        if job["cancel"]:
            return
        parts = line.split("|", 4)
        if len(parts) != 5 or not parts[1].isdigit():
            continue
        kind, size, mod, chg, name = parts
        try:
            full = M.normalize_path(name)
        except ValueError:
            continue
        if full == start_path:
            continue
        folder = posixpath.dirname(full)
        if not add(job, posixpath.basename(full), full, kind == "directory", int(size), int(mod) * 1000, int(chg) * 1000, folder):
            break


IOS_ALL = ["/DCIM", "/Downloads", "/Books", "/Recordings", "/Music", "/@apps"]


def run_ios(job, src, path, q, exts, scope):
    """الآيفون/الآيباد: يمشي في المجلدات عبر AFC (أبطأ من غيره)؛ «الكل» = مجلدات الوسائط وملفات التطبيقات."""
    import ios_src
    udid = src.get("udid", "")
    stack = list(reversed(IOS_ALL)) if scope == "all" or (path or "/") == "/" else [path]
    t0 = time.time()
    fails, ok_any = [], False
    while stack and not job["cancel"]:
        if time.time() - t0 > limit_of(job):
            job["truncated"] = job["timed_out"] = True
            break
        cur = stack.pop()
        try:
            ents = ios_src.browse(udid, cur)["entries"]
            ok_any = True
        except Exception as exc:
            fails.append(str(exc))
            continue
        for e in ents:
            if e["is_dir"]:
                stack.append(e["path"])
            if matches(e["name"], q, exts) and not (e["is_dir"] and exts):
                if not add(job, e["name"], e["path"], e["is_dir"], e["size"], e["mod"], e["chg"], cur):
                    return
    if fails and not ok_any and not job["entries"]:
        job["error"] = fails[0]
        job["state"] = "error"


def run_rclone(job, src, path, q, exts, scope):
    """البحث داخل حساب سحابي مباشر: قائمة متكررة بمرشّحات rclone، تُقرأ سطرًا سطرًا لتظهر النتائج فور وصولها
    وتبقى الجزئية منها إن انتهت المهلة."""
    from datetime import datetime
    import subprocess as _sp
    import rclone_src as R
    base = "" if scope == "all" else path.strip("/")
    args = ["lsf", "-R", "--fast-list", "--ignore-case", "--format", "pst", "--separator", "\t", "--drive-export-formats", R.EXPORT]
    if exts:
        args.append("--files-only")
        for e in sorted(exts):
            args += ["--include", f"*{'*' + q + '*' if q else ''}.{e}" if q else f"*.{e}"]
    elif q:
        args += ["--include", f"*{q}*", "--include", f"*{q}*/**"]
    args.append(R.spec(src["root"], base))
    import tempfile
    errf = tempfile.TemporaryFile()
    p = _sp.Popen([R.RCLONE, *args], stdout=_sp.PIPE, stderr=errf, text=True, encoding="utf-8", errors="replace")
    job["_proc"] = p
    left = limit_of(job) - (time.time() - job["started"])

    def expire():
        job["truncated"] = job["timed_out"] = True
        try:
            p.kill()
        except Exception:
            pass
    timer = threading.Timer(max(1, left), expire)
    timer.daemon = True
    timer.start()
    try:
        for line in p.stdout:
            if job["cancel"]:
                p.kill()
                return
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            rpath, size, stamp = parts
            is_dir = rpath.endswith("/")
            rpath = rpath.rstrip("/")
            name = posixpath.basename(rpath)
            if not matches(name, q, exts if not is_dir else set()):
                continue
            rel = "/".join(x for x in (base, rpath) if x)
            try:
                mod = int(datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=__import__("datetime").timezone.utc).timestamp() * 1000)
            except Exception:
                mod = 0
            sz = int(size) if size.lstrip("-").isdigit() and int(size) >= 0 else None
            if not add(job, name, rel, is_dir, sz, mod, mod, posixpath.dirname(rel)):
                p.kill()
                return
    finally:
        timer.cancel()
        try:
            p.kill()
        except Exception:
            pass
        p.wait()
        if p.returncode not in (0, None) and not job["cancel"] and not job.get("timed_out") and not job["entries"]:
            try:
                errf.seek(0)
                msg = errf.read().decode("utf-8", "replace").strip().splitlines()
                last = next((x for x in reversed(msg) if x.strip()), "")
                job["error"] = ("انتهت صلاحية دخول هذا الحساب؛ أعد ربطه من إعدادات السحابة." if "invalid_grant" in last else last[-160:]) or "تعذّر البحث في هذا الحساب."
                job["state"] = "error"
            except Exception:
                pass
        errf.close()


def _ckey(sid, src, q, exts, content):
    return json.dumps([sid, src.get("root") or src.get("serial") or src.get("udid") or src.get("type"), q.lower(), sorted(exts), sorted(content)], ensure_ascii=False)


def start_multi(body):
    """بحث واحد في عدة مصادر معًا وبالتوازي؛ كل نتيجة تحمل معرّف مصدرها (sid) وتظهر فور وصولها.
    لكل مصدر مهلة وحالة (جارٍ/تم/بطيء/متأخر/تعذّر) في job["sources"]. يلغي بحثًا متعددًا سابقًا ما زال جاريًا."""
    from concurrent.futures import ThreadPoolExecutor
    lst = body.get("sources") or []
    q = str(body.get("q") or "").strip()
    exts = [e.lower().lstrip(".") for e in (body.get("exts") or []) if re.fullmatch(r"\.?[A-Za-z0-9_+\-]{1,12}", str(e))]
    content = [str(w).strip()[:30] for w in (body.get("content") or []) if str(w).strip()][:8]
    if not q and not exts and not content:
        raise ValueError("اكتب اسمًا أو اختر نوعًا.")
    if not lst or len(lst) > 30:
        raise ValueError("اختر مصدرًا واحدًا على الأقل.")
    for old in list(JOBS.values()):          # بحث جديد يُلغي القديم الجاري
        if old.get("multi") and old["state"] == "running":
            _stop(old)
    fresh = bool(body.get("fresh"))
    job = {"id": uuid.uuid4().hex[:10], "state": "running", "entries": [], "truncated": False, "error": "", "cancel": False, "started": time.time(),
           "progress": [], "multi": True, "subs": [], "sources": {}}
    JOBS[job["id"]] = job
    if len(JOBS) > 10:
        for k in sorted(JOBS, key=lambda x: JOBS[x]["started"])[:-10]:
            if JOBS[k]["state"] != "running":
                JOBS.pop(k, None)
    lock = threading.Lock()

    def one(it):
        sid, src = str(it.get("sid")), dict(it.get("src") or {})
        st = {"state": "running", "count": 0, "seconds": 0, "error": "", "cached": False}
        job["sources"][sid] = st
        t0 = time.time()
        try:
            if job["cancel"]:
                st["state"] = "cancelled"
                return
            if src.get("type") == "adb":
                src["serial"] = M.connected_device(src.get("serial"))
            key = _ckey(sid, src, q, exts, content)
            hit = None if fresh else _CACHE.get(key)
            if hit and time.time() - hit[0] < CACHE_TTL:
                for e in hit[1]:
                    job["entries"].append(e | {"sid": sid})
                st.update(state="done", count=len(hit[1]), cached=True, seconds=round(time.time() - t0, 1))
                return
            sub = {"id": "", "state": "running", "entries": [], "truncated": False, "error": "", "cancel": False, "started": time.time(),
                   "parent": job, "sid": sid, "limit": SOURCE_LIMIT, "timed_out": False}
            with lock:
                job["subs"].append(sub)
            run(sub, src, "", q, exts, "all", content)
            st["seconds"] = round(time.time() - t0, 1)
            st["count"] = len(sub["entries"])
            job["truncated"] = job["truncated"] or sub["truncated"]
            if sub["error"]:
                st.update(state="error", error=sub["error"])
            elif sub["timed_out"]:
                st.update(state="timeout", error=f"انتهت مهلته ({SOURCE_LIMIT} ثانية)؛ هذه نتائجه الجزئية")
            elif job["cancel"]:
                st["state"] = "cancelled"
            else:
                st["state"] = "slow" if st["seconds"] > SLOW_AFTER else "done"
                if not sub["truncated"]:
                    _CACHE[key] = (time.time(), [dict(e) for e in sub["entries"]])
                    if len(_CACHE) > 200:
                        _CACHE.pop(next(iter(_CACHE)), None)
        except Exception as exc:
            st.update(state="error", error=str(exc), seconds=round(time.time() - t0, 1))
        finally:
            job["progress"].append(sid)

    def go():
        with ThreadPoolExecutor(min(MULTI_WORKERS, len(lst))) as ex:
            list(ex.map(one, lst))
        bad = [f"{sid}: {st['error']}" for sid, st in job["sources"].items() if st["error"]]
        job["error"] = " · ".join(bad)
        job["state"] = "cancelled" if job["cancel"] else "done"
    threading.Thread(target=go, daemon=True).start()
    return public(job)
