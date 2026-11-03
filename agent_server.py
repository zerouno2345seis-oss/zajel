"""حارس مساعد زاجل: المفتاح السري، الطلبات المعلّقة، دفتر التدقيق، ونقاط /api/agent و/api/assistant.
يُربط بالخادم بسطرين في Handler (انظر samsung_backup_web.py). كل تنفيذ يمرّ بنداء ارتدادي إلى نقاط زاجل نفسها."""
import hmac
import json
import subprocess
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import agent_tools as T

M = DATA = None
PORT = 0
KEY = ""
LOCK = threading.RLock()
PENDING = {}   # رقم ← طلب أحمر ينتظر الموافقة
HISTORY = {}   # رقم ← حالة نهائية (approved/denied/expired) ونتيجتها
EXPIRY = int(os.environ.get("PB_AGENT_EXPIRY") or 600)   # عشر دقائق (يُقصَّر في الاختبار فقط)
RED_LIMIT_PER_HOUR = int(os.environ.get("PB_AGENT_RED_LIMIT") or 12)   # يُرفع في الاختبار فقط
_red_times = []
NAV = []           # طلبات «افتح المجلد» من المساعد؛ يلتقطها assistant_nav.js في الواجهة
NAV_SEQ = [0]


def nav_push(place, path, is_file=False):
    with LOCK:
        NAV_SEQ[0] += 1
        NAV.append({"seq": NAV_SEQ[0], "place": place, "path": path, "is_file": is_file, "t": time.time()})
        del NAV[:-20]


OWNED_UI = ("/api/assistant/", "/api/sync/item", "/api/migrate/item", "/api/term/")


def owns(path):
    return path.startswith("/api/agent/") or path.startswith(OWNED_UI)


def init(module, data_dir, port):
    """يولّد مفتاحًا جديدًا في كل تشغيل بصلاحية صاحب الحساب وحده، ويكتب رقم المنفذ الحالي."""
    global M, DATA, PORT, KEY
    M, DATA, PORT = module, Path(data_dir), int(port)
    DATA.mkdir(parents=True, exist_ok=True)
    KEY = secrets.token_urlsafe(32)
    kf = DATA / ".agent_key"
    try:
        kf.unlink()
    except FileNotFoundError:
        pass
    fd = os.open(kf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(KEY)
    os.chmod(kf, 0o600)
    (DATA / ".zajel_port").write_text(str(PORT), encoding="utf-8")
    import agent_runner
    agent_runner.init(DATA, PORT)
    import automation, agent_scripts
    automation.init(DATA)
    agent_scripts.init(DATA)
    import servers
    servers.init(DATA, PORT)
    import media
    media.init(DATA)
    agent_scripts.M = M
    def _phone_serial():
        import phone_link
        st = phone_link.status(M)
        return st.get("wireless") or (st.get("usb") or [""])[0]
    agent_scripts.PHONE_SERIAL = _phone_serial
    threading.Thread(target=automation.scheduler, args=(Helper,), daemon=True).start()   # قواعد المراقبة الدورية
    import phone_link
    threading.Thread(target=phone_link.keeper, args=(M,), daemon=True).start()   # إعادة وصل الهاتف لاسلكيًا تلقائيًا


# ---------- دفتر التدقيق ----------
def audit(agent, tool, args, tier, decision, result="", job="", extra=None):
    rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "agent": agent or "?", "job": job, "tool": tool, "tier": tier, "decision": decision,
           "args": json.dumps(args, ensure_ascii=False)[:400], "result": str(result)[:300]}
    if extra:
        rec.update(extra)
    try:
        with open(DATA / "agent_audit.log", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return rec


def audit_tail(n=60, job=""):
    try:
        lines = (DATA / "agent_audit.log").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines[-2000:]:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if not job or r.get("job") == job:
            out.append(r)
    return out[-n:]


# ---------- مساعد الأدوات ----------
class Helper:
    q = staticmethod(lambda s: urllib.parse.quote(str(s), safe=""))

    def __init__(self):
        self.M = M

    def http(self, method, path, body=None, timeout=90):
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method,
                                     headers={"Origin": f"http://127.0.0.1:{PORT}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error")
            except Exception:
                msg = None
            raise ValueError(msg or f"خطأ {e.code}")

    # --- دليل الأماكن ---
    def places(self):
        home = Path.home()
        out = {"folders": [], "favorites": [], "disks": [], "clouds": [], "devices": [], "syncs": [], "computer": {"id": "home", "name": "هذا الكمبيوتر (مجلد المستخدم)"}}
        for sub, name in (("Desktop", "سطح المكتب"), ("Documents", "المستندات"), ("Downloads", "التنزيلات"), ("Pictures", "الصور"), ("Movies", "الأفلام"), ("Music", "الموسيقى")):
            if (home / sub).is_dir():
                out["folders"].append({"name": name, "place": "home", "path": sub})
        out["folders"].append({"name": "المرفقات", "place": "uploads", "path": ""})
        for f in M.favorites_get():
            out["favorites"].append({"name": f.get("name"), "place": f.get("id"), "path": f.get("path", "")})
        for r in M.cloud_roots():
            row = {"name": re.sub(r"^[^\w؀-ۿ]+", "", r.get("label", r["id"])), "place": r["id"]}
            if r["group"] in ("disk", "network"):
                out["disks"].append(row)
            elif r["group"] in ("cloud", "rclone"):
                out["clouds"].append(row | ({"kind": r.get("kind")} if r.get("kind") else {}))
        for v in M.volumes():
            for d in out["disks"]:
                if d["place"] == "vol:" + v["name"]:
                    d["free_bytes"], d["total_bytes"] = v.get("free"), v.get("total")
        try:
            st = self.http("GET", "/api/status")
            out["devices"].append({"name": st.get("model") or "الهاتف", "place": "phone", "connected": bool(st.get("connected")), "root_path": "/sdcard"})
        except Exception:
            out["devices"].append({"name": "الهاتف", "place": "phone", "connected": False})
        try:
            for d in self.http("GET", "/api/ios/devices").get("devices", []):
                out["devices"].append({"name": d.get("name") or d.get("cls"), "place": "ios:" + d["udid"], "connected": not d.get("locked")})
        except Exception:
            pass
        for g in M.syncer.groups():
            out["syncs"].append({"id": g.get("id"), "name": g.get("name"), "places": [l.get("label") or l.get("root") or "الهاتف" for l in g.get("locations", [])],
                                 "deletes": bool(g.get("deletes")), "mode": g.get("mode")})
        out["note"] = "استعمل place وpath في الأدوات. المسارات نسبية داخل المكان، وللهاتف مطلقة مثل /sdcard/DCIM."
        return out

    def place_label(self, pid):
        pid = str(pid or "")
        if pid == "home":
            return "هذا الكمبيوتر"
        if pid == "phone":
            return "الهاتف"
        if pid == "uploads":
            return "المرفقات"
        for r in M.cloud_roots():
            if r["id"] == pid:
                return re.sub(r"^[^\w؀-ۿ]+", "", r.get("label", pid))
        return pid

    def search_wait(self, jid, secs):
        end = time.time() + secs
        job = {}
        while time.time() < end:
            job = self.http("GET", "/api/search/job?id=" + self.q(jid))
            if job.get("state") != "running":
                break
            time.sleep(0.6)
        ents = job.get("entries") or []
        keep = ("name", "path", "is_dir", "size", "sid", "label", "place", "root", "src")
        slim = [{k: e[k] for k in keep if k in e and e[k] not in (None, "")} for e in ents[:30]]   # نتائج مضغوطة: النتيجة الضخمة تبطئ الوكيل
        return {"id": jid, "state": job.get("state"), "count": len(ents), "entries": slim, "truncated": job.get("truncated") or len(ents) > 30,
                "error": job.get("error") or "", "note": "لم ينتهِ البحث بعد؛ استعمل search_result." if job.get("state") == "running" else "",
                **({"sources": {k: {x: v[x] for x in ("state", "count", "seconds", "error") if v.get(x) not in (None, "")} for k, v in job["sources"].items()}} if job.get("sources") else {})}

    def wait_op(self, oid, secs):
        end = time.time() + secs
        while True:
            d = self.http("GET", "/api/ops/get?id=" + self.q(oid))
            if d.get("state") != "running" or time.time() >= end:
                return d
            time.sleep(0.8)

    # --- حفظ عنصر واحد دون استبدال القائمة ---
    def sync_upsert(self, g):
        return sync_item({"op": "upsert", "group": g})

    def sync_patch(self, gid, fields):
        cur = next((x for x in M.syncer.groups() if x.get("id") == gid), None)
        if not cur:
            raise ValueError("المزامنة غير موجودة.")
        return sync_item({"op": "upsert", "group": cur | fields})

    def sync_remove(self, gid):
        return sync_item({"op": "delete", "id": gid})

    def migrate_upsert(self, r):
        return migrate_item({"op": "upsert", "rule": r})

    def migrate_remove(self, rid):
        return migrate_item({"op": "delete", "id": rid})

    def approval_status(self, pid):
        with LOCK:
            _expire()
            if pid in PENDING:
                return {"state": "pending", "expires_in": int(PENDING[pid]["expires"] - time.time())}
            return HISTORY.get(pid) or {"state": "unknown"}


def sync_item(b):
    with LOCK:
        cur = M.syncer.groups()
        if b.get("op") == "delete":
            new = [g for g in cur if g.get("id") != b.get("id")]
            if len(new) == len(cur):
                raise ValueError("المزامنة غير موجودة.")
        else:
            g = dict(b.get("group") or {})
            if not g:
                raise ValueError("لا مزامنة في الطلب.")
            gid = g.get("id")
            new, hit = [], False
            for x in cur:
                if gid and x.get("id") == gid:
                    new.append(g)
                    hit = True
                else:
                    new.append(x)
            if not hit:
                g.pop("id", None) if not gid else None
                new.append(g)
        saved = M.syncer.save(new)
    return {"groups": saved, "count": len(saved)}


def migrate_item(b):
    with LOCK:
        cur = M.migrate.rules()
        if b.get("op") == "delete":
            new = [r for r in cur if r.get("id") != b.get("id")]
            if len(new) == len(cur):
                raise ValueError("القاعدة غير موجودة.")
        else:
            r = dict(b.get("rule") or {})
            if not r:
                raise ValueError("لا قاعدة في الطلب.")
            rid = r.get("id")
            new, hit = [], False
            for x in cur:
                if rid and x.get("id") == rid:
                    new.append(r)
                    hit = True
                else:
                    new.append(x)
            if not hit:
                new.append(r)
        saved = M.migrate.save_rules(new)
    return {"rules": saved, "count": len(saved)}


# ---------- الحارس ----------
def _expire():
    now = time.time()
    for pid in [k for k, v in PENDING.items() if v["expires"] < now]:
        p = PENDING.pop(pid)
        HISTORY[pid] = {"state": "expired", "tool": p["tool"]}
        audit(p["agent"], p["tool"], p["args"], T.RED, "expired", job=p.get("job", ""))
    while len(HISTORY) > 200:
        HISTORY.pop(next(iter(HISTORY)))


def call(name, args, agent="", job=""):
    """نقطة القرار الوحيدة: ممنوع ← يُرفض؛ أخضر/أصفر ← يُنفَّذ؛ أحمر ← يُحفظ معلّقًا."""
    args = args if isinstance(args, dict) else {}
    if name in T.FORBIDDEN_NAMES:
        audit(agent, name, args, T.FORBIDDEN, "refused", job=job)
        return {"refused": True, "error": "هذه العملية ممنوعة على المساعد نهائيًا (الفرمتة وحسابات السحابة والطرفية). تبقى للمستخدم من داخل زاجل."}
    t = T.TOOLS.get(name)
    if not t:
        audit(agent, name, args, "?", "unknown", job=job)
        return {"error": "أداة غير معروفة: " + name}
    args = T.normalize_args(name, args)
    tier = t["classify"](args) if t["classify"] else t["tier"]
    H = Helper()
    try:
        if tier != T.GREEN or name == "preview":
            T.validate_args(name, args) if name != "preview" else None
        if tier == T.RED:
            now = time.time()
            with LOCK:
                _expire()
                _red_times[:] = [x for x in _red_times if now - x < 3600]
                if len(_red_times) >= RED_LIMIT_PER_HOUR:
                    audit(agent, name, args, tier, "rate-limited", job=job)
                    return {"error": "تجاوز المساعد حدّ العمليات الحمراء في الساعة؛ انتظر أو نفّذها بنفسك."}
                pv = T.make_preview(name, args, H)
                pid = uuid.uuid4().hex[:8]
                PENDING[pid] = {"id": pid, "tool": name, "args": args, "preview": pv, "created": now, "expires": now + EXPIRY, "agent": agent, "job": job,
                                "word": T.NEEDS_WORD.get(name)}
                _red_times.append(now)
            audit(agent, name, args, tier, "pending:" + pid, job=job)
            return {"pending": True, "id": pid, "preview": pv,
                    "message": "بانتظار موافقة المستخدم. ستصله بطاقة موافقة بأزرار في تيليجرام، وتظهر أيضًا في نافذة زاجل، وله أن يوافق من أيهما (صالحة 10 دقائق). لا تقل له إن الموافقة في نافذة زاجل فقط؛ قل: «ضغط «تابع» في بطاقة تيليجرام أو في زاجل». لا تعد الطلب، ثم افحص approval_status."}
        res = t["run"](args, H)
        extra = {"search_id": res["id"], "search_place": args.get("place") or "", "search_count": res.get("count")} if name in ("search", "search_all", "search_result") and isinstance(res, dict) and res.get("id") else None
        audit(agent, name, args, tier, "done", json.dumps(res, ensure_ascii=False)[:200] if res is not None else "", job, extra)
        return {"ok": True, "tier": tier, "result": res}
    except Exception as exc:
        audit(agent, name, args, tier, "error", str(exc), job)
        return {"error": str(exc)}


def approve(pid, word=""):
    with LOCK:
        _expire()
        p = PENDING.get(pid)
        if not p:
            raise ValueError("الطلب غير موجود أو انتهت صلاحيته.")
        if p["word"] and word.strip() != p["word"]:
            raise ValueError(f"اكتب كلمة التأكيد «{p['word']}» للموافقة.")
        del PENDING[pid]
    t = T.TOOLS[p["tool"]]
    try:
        res = t["run"](p["args"], Helper())
        HISTORY[pid] = {"state": "approved", "tool": p["tool"], "result": res}
        audit(p["agent"], p["tool"], p["args"], T.RED, "approved-done", json.dumps(res, ensure_ascii=False)[:200], p.get("job", ""))
        return {"ok": True, "result": res}
    except Exception as exc:
        HISTORY[pid] = {"state": "approved", "tool": p["tool"], "error": str(exc)}
        audit(p["agent"], p["tool"], p["args"], T.RED, "approved-error", str(exc), p.get("job", ""))
        raise


def deny(pid):
    with LOCK:
        p = PENDING.pop(pid, None)
    if not p:
        raise ValueError("الطلب غير موجود.")
    HISTORY[pid] = {"state": "denied", "tool": p["tool"]}
    audit(p["agent"], p["tool"], p["args"], T.RED, "denied", job=p.get("job", ""))
    return {"ok": True}


def pending_list():
    with LOCK:
        _expire()
        rows = [{k: v for k, v in p.items() if k != "args"} | {"expires_in": int(p["expires"] - time.time()), "needs_word": p["word"]} for p in PENDING.values()]
    return rows


def stop_all():
    """زر «أوقف الكل»: يقتل الوكلاء، يلغي العمليات الجارية، ويرفض كل المعلّق."""
    import agent_runner
    n_jobs = agent_runner.stop_all()
    n_ops = 0
    try:
        for o in M.fileops.listing():
            if o.get("state") == "running":
                M.fileops.cancel(o["id"])
                n_ops += 1
    except Exception:
        pass
    with LOCK:
        ids = list(PENDING)
    for pid in ids:
        try:
            deny(pid)
        except ValueError:
            pass
    audit("ui", "stop_all", {}, "ui", "done", f"jobs={n_jobs} ops={n_ops} pending={len(ids)}")
    return {"agents_stopped": n_jobs, "ops_cancelled": n_ops, "pending_denied": len(ids)}


# ---------- نقاط HTTP ----------
class _LimitedReader:
    def __init__(self, rfile, length):
        self.rfile = rfile
        self.remaining = length

    def read(self, size=-1):
        if self.remaining <= 0:
            return b""
        if size < 0 or size > self.remaining:
            size = self.remaining
        chunk = self.rfile.read(size)
        if not chunk:
            self.remaining = 0
            return b""
        self.remaining -= len(chunk)
        return chunk


def _body(h):
    n = int(h.headers.get("Content-Length", "0") or 0)
    if n > 2_000_000:
        raise ValueError("طلب كبير.")
    return json.loads(h.rfile.read(n) or b"{}") if n else {}


def handle(h, method):
    """يُستدعى من Handler بعد فحص Host. يعالج مسارات الوكيل (بمفتاح) ومسارات الواجهة (بـOrigin)."""
    url = urllib.parse.urlsplit(h.path)
    path, query = url.path, urllib.parse.parse_qs(url.query)
    try:
        if path.startswith("/api/agent/"):
            if not KEY or not hmac.compare_digest(h.headers.get("X-Zajel-Key", ""), KEY):
                h.send_json({"error": "مفتاح الوكيل مفقود أو خاطئ."}, 401)
                return
            if method == "GET" and path == "/api/agent/tools":
                h.send_json({"tools": T.public_catalog()})
            elif method == "POST" and path == "/api/agent/call":
                b = _body(h)
                import agent_runner
                job = h.headers.get("X-Zajel-Job", "") or agent_runner.CURRENT
                h.send_json(call(str(b.get("tool", "")), b.get("args"), h.headers.get("X-Zajel-Agent", ""), job))
            else:
                h.send_json({"error": "غير موجود."}, 404)
            return
        # مسارات الواجهة: نفس شرط Origin الحالي، وترفض أي طلب يحمل مفتاح الوكيل (الوكيل لا يوافق عن المستخدم)
        if method == "POST" and h.headers.get("Origin") != f"http://127.0.0.1:{PORT}":
            h.send_json({"error": "مصدر الطلب غير مسموح."}, 403)
            return
        if h.headers.get("X-Zajel-Key"):
            h.send_json({"error": "طلبات الوكيل لا تصل إلى نقاط الواجهة."}, 403)
            return
        import agent_runner
        import assistant_store as S
        if path == "/api/assistant/upload" and method == "POST":
            import media
            raw_name = query.get("name", [""])[0]
            name = urllib.parse.unquote(raw_name)
            try:
                length = int(h.headers.get("Content-Length", "0") or 0)
            except (ValueError, TypeError):
                length = 0
            limit = 500 * 1024 * 1024
            if length > limit:
                h.send_json({"ok": False, "error": "حجم الملف يتجاوز الحد المسموح (500 ميغابايت)."}, 400)
                return
            try:
                reader = _LimitedReader(h.rfile, length)
                info = media.save_upload(reader, name, max_size=limit)
                h.send_json({"ok": True, **info})
            except ValueError as exc:
                h.send_json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:
                h.send_json({"ok": False, "error": f"تعذر حفظ المرفق: {exc}"}, 500)
            return
        elif path == "/api/assistant/upload/file" and method == "GET":
            import media, mimetypes
            rel_path = query.get("path", [""])[0]
            if not rel_path:
                h.send_json({"error": "حدد مسار الملف."}, 400)
                return
            up_dir = media.get_upload_dir().resolve()
            p_obj = Path(rel_path)
            target = p_obj.resolve() if p_obj.is_absolute() else (up_dir / rel_path.lstrip("/")).resolve()
            if not media.is_under_uploads(target) or not target.is_file():
                h.send_json({"error": "الملف غير موجود أو خارج مجلد المرفقات المسموح."}, 404)
                return
            ext = target.suffix.lower()
            if ext in media.IMG_EXT:
                mime, _ = mimetypes.guess_type(str(target))
                ctype = mime if mime and mime.startswith("image/") else "image/jpeg"
            else:
                ctype = "application/octet-stream"
            size = target.stat().st_size
            h.send_response(200)
            h.send_header("Content-Type", ctype)
            h.send_header("Content-Length", str(size))
            h.send_header("X-Content-Type-Options", "nosniff")
            h.send_header("Cache-Control", "private, max-age=3600")
            h.end_headers()
            with open(target, "rb") as fh:
                while True:
                    chunk = fh.read(65536)
                    if not chunk:
                        break
                    h.wfile.write(chunk)
            return
        elif path == "/api/sync/item" and method == "POST":
            h.send_json(sync_item(_body(h)))
        elif path == "/api/migrate/item" and method == "POST":
            h.send_json(migrate_item(_body(h)))
        elif path == "/api/assistant/pending":
            h.send_json({"pending": pending_list(), "recent": [{"id": k} | v for k, v in list(HISTORY.items())[-8:]]})
        elif path == "/api/assistant/approve" and method == "POST":
            b = _body(h)
            h.send_json(approve(str(b.get("id", "")), str(b.get("word", ""))))
        elif path == "/api/assistant/deny" and method == "POST":
            h.send_json(deny(str(_body(h).get("id", ""))))
        elif path == "/api/assistant/places":
            h.send_json(Helper().places())
        elif path == "/api/assistant/agents":
            h.send_json({"agents": agent_runner.agents(), "settings": agent_runner.settings()})
        elif path == "/api/assistant/models/refresh" and method == "POST":
            h.send_json({"result": agent_runner.refresh_models(str(_body(h).get("agent") or "")), "agents": agent_runner.agents()})
        elif path == "/api/assistant/settings" and method == "POST":
            agent_runner.set_settings(_body(h))
            h.send_json({"settings": agent_runner.settings(), "agents": agent_runner.agents()})
        elif path == "/api/assistant/automations":
            import automation
            h.send_json({"rules": [automation.public(r) for r in automation.rules_list()], "notices": automation.notices_list()})
        elif path == "/api/assistant/automations/toggle" and method == "POST":
            import automation
            b = _body(h)
            automation.set_enabled(str(b.get("id")), bool(b.get("enabled")))
            h.send_json({"ok": True})
        elif path == "/api/assistant/automations/run" and method == "POST":
            import automation
            h.send_json({"note": automation.run_now(str(_body(h).get("id")), Helper())})
        elif path == "/api/assistant/automations/delete" and method == "POST":
            import automation
            automation.delete_rule(str(_body(h).get("id")))
            h.send_json({"ok": True})
        elif path == "/api/assistant/notices/read" and method == "POST":
            import automation
            automation.notices_read(_body(h).get("ids"))
            h.send_json({"ok": True})
        elif path == "/api/assistant/scripts":
            import agent_scripts
            h.send_json({"scripts": agent_scripts.listing()})
        elif path == "/api/assistant/scripts/get":
            import agent_scripts
            h.send_json(agent_scripts.get(query.get("name", [""])[0]))
        elif path == "/api/assistant/scripts/meta" and method == "POST":
            import agent_scripts
            b = _body(h)
            agent_scripts.meta_update(str(b.get("name")), b.get("title"), b.get("description"), b.get("tags"), b.get("params"))
            h.send_json({"scripts": agent_scripts.listing()})
        elif path == "/api/assistant/scripts/delete" and method == "POST":
            import agent_scripts
            agent_scripts.delete(str(_body(h).get("name")))
            h.send_json({"scripts": agent_scripts.listing()})
        elif path == "/api/assistant/scripts/run" and method == "POST":
            # تشغيل من المكتبة: ضغط المستخدم نفسه بعد أن رأى الكود؛ البصمة تمنع تشغيل نص تغيّر بعد عرضه
            import agent_scripts, shlex
            b = _body(h)
            if not b.get("sha"):
                raise ValueError("بصمة السكربت مطلوبة؛ افتح الكود أولًا.")
            args = agent_scripts.build_args(str(b.get("name")), b["values"]) if isinstance(b.get("values"), dict) else shlex.split(str(b.get("args") or ""))[:20]
            h.send_json(agent_scripts.start(str(b.get("name")), args, 1800, str(b.get("sha") or ""), T._finish_notice))
        elif path == "/api/assistant/servers":
            import servers
            h.send_json({"servers": servers.listing(), "saved": servers.definitions()})
        elif path == "/api/assistant/servers/stop" and method == "POST":
            import servers
            b = _body(h)
            h.send_json(servers.stop(int(b.get("pid") or 0), bool(b.get("force"))))
        elif path == "/api/assistant/servers/start" and method == "POST":
            import servers
            h.send_json(servers.start(str(_body(h).get("id"))))
        elif path == "/api/assistant/servers/define" and method == "POST":
            import servers
            b = _body(h)
            h.send_json(servers.define(b.get("name"), b.get("cmd"), b.get("cwd"), b.get("port")))
        elif path == "/api/assistant/servers/forget" and method == "POST":
            import servers
            servers.forget(str(_body(h).get("id")))
            h.send_json({"ok": True})
        elif path == "/api/assistant/phone/control" and method == "POST":
            import phone_link
            b = _body(h)
            try:
                h.send_json(phone_link.control(M, b.get("action"), b))
            except (ValueError, subprocess.TimeoutExpired) as exc:
                h.send_json({"error": str(exc) or "انتهت مهلة الأمر."}, 400)
        elif path == "/api/assistant/phone/screen" and method == "POST":
            import phone_link
            b = _body(h)
            act = str(b.get("action") or "start")
            try:
                if act == "stop":
                    h.send_json(phone_link.screen_stop())
                elif act == "status":
                    h.send_json(phone_link.screen_status())
                else:
                    h.send_json(phone_link.screen_start(M, b))
            except ValueError as exc:
                h.send_json({"error": str(exc)}, 400)
        elif path == "/api/assistant/phone/details":
            import phone_link
            h.send_json(phone_link.details(M))
        elif path == "/api/assistant/phone" and method == "POST":
            import phone_link
            b = _body(h)
            h.send_json(phone_link.connect(M, str(b.get("ip") or ""), str(b.get("port") or ""), str(b.get("pair_addr") or ""), str(b.get("pair_code") or "")))
        elif path == "/api/assistant/phone":
            import phone_link
            h.send_json(phone_link.status(M))
        elif path == "/api/assistant/audit":
            h.send_json({"log": audit_tail(int(query.get("n", ["60"])[0]), query.get("job", [""])[0])})
        elif path == "/api/assistant/quick" and method == "POST":
            act = str(_body(h).get("action"))
            if act == "stop_all":
                h.send_json(stop_all())
            elif act in ("status", "ops"):
                h.send_json(call("status" if act == "status" else "list_ops", {}, "ui"))
            else:
                raise ValueError("إجراء غير معروف.")
        elif path == "/api/assistant/chat" and method == "POST":
            b = _body(h)
            import media
            raw_att = b.get("attachments")
            attachments = []
            if raw_att is not None:
                if not isinstance(raw_att, list):
                    h.send_json({"error": "المرفقات يجب أن تكون قائمة."}, 400)
                    return
                if len([x for x in raw_att if not (isinstance(x, dict) and x.get("ref"))]) > 10 or len(raw_att) > 110:
                    h.send_json({"error": "الحد الأقصى للمرفقات هو 10 ملفات (و100 عنصر من نتائج البحث)."}, 400)
                    return
                up_dir = media.get_upload_dir().resolve()
                for a in raw_att:
                    if not isinstance(a, dict):
                        h.send_json({"error": "بيانات المرفق غير صالحة."}, 400)
                        return
                    p = a.get("path")
                    if not p:
                        h.send_json({"error": "مسار المرفق مفقود."}, 400)
                        return
                    if a.get("ref"):     # عنصر من نتائج البحث: مرجع إلى مكانه الأصلي لا نسخة مرفوعة
                        place = str(a.get("sid") or "")[:200]
                        if not place or "\x00" in str(p) or len(str(p)) > 1500:
                            h.send_json({"error": "مرجع نتيجة غير صالح."}, 400)
                            return
                        attachments.append({"ref": True, "place": place, "path": str(p), "name": str(a.get("name") or str(p).rsplit("/", 1)[-1])[:200],
                                            "kind": "ref", "is_dir": bool(a.get("is_dir"))})
                        continue
                    p_obj = Path(p)
                    target = p_obj.resolve() if p_obj.is_absolute() else (up_dir / str(p).lstrip("/")).resolve()
                    if not media.is_under_uploads(target):
                        h.send_json({"error": f"المرفق خارج مجلد المرفقات المسموح: {p}"}, 400)
                        return
                    attachments.append({
                        "path": str(target),
                        "name": str(a.get("name") or target.name),
                        "kind": str(a.get("kind") or media.kind_of(target))
                    })
            h.send_json(agent_runner.start_chat(
                str(b.get("agent") or agent_runner.settings()["default_agent"]),
                str(b.get("text") or ""),
                b.get("context") or {},
                str(b.get("conversation") or ""),
                str(b.get("model") or ""),
                attachments=attachments if attachments else None
            ))
        elif path == "/api/assistant/nav":
            after = int(query.get("after", ["-1"])[0])
            with LOCK:
                h.send_json({"seq": NAV_SEQ[0], "items": [n for n in NAV if n["seq"] > after] if after >= 0 else []})
        elif path == "/api/assistant/chats":
            h.send_json({"chats": S.chats_list()})
        elif path == "/api/assistant/chat/get":
            h.send_json(S.chat_get(query.get("id", [""])[0]))
        elif path == "/api/assistant/chat/rename" and method == "POST":
            b = _body(h); S.chat_rename(str(b.get("id", "")), b.get("title")); h.send_json({"chats": S.chats_list()})
        elif path == "/api/assistant/chat/delete" and method == "POST":
            S.chat_delete(str(_body(h).get("id", ""))); h.send_json({"chats": S.chats_list()})
        elif path == "/api/term/list":
            import terminal
            h.send_json(terminal.listing())
        elif path == "/api/term/screen":
            import terminal
            h.send_json(terminal.screen(query.get("id", [""])[0], query.get("since", [""])[0], int(query.get("hist", ["0"])[0] or 0)))
        elif path.startswith("/api/term/") and method == "POST":
            import terminal
            b = _body(h)
            i, act = str(b.get("id", "")), path.rsplit("/", 1)[1]
            if act == "start":
                h.send_json(terminal.start(i, str(b.get("cwd", ""))))
            elif act == "stop":
                h.send_json(terminal.stop(i))
            elif act == "restart":
                h.send_json(terminal.restart(i))
            elif act == "send":
                h.send_json(terminal.send(i, str(b.get("text", "")), b.get("keys") or [], bool(b.get("paste"))))
            elif act == "resize":
                h.send_json(terminal.resize(i, b.get("cols", 100), b.get("rows", 30)))
            elif act == "notify":
                h.send_json(terminal.set_notify(b.get("on")))
            else:
                h.send_json({"error": "غير موجود."}, 404)
        elif path == "/api/assistant/whatsapp/status":
            import whatsapp_watch
            h.send_json(whatsapp_watch.status())
        elif path.startswith("/api/assistant/whatsapp/") and method == "POST":
            import whatsapp_watch
            act = path.rsplit("/", 1)[1]
            if act == "configure":
                h.send_json(whatsapp_watch.configure(_body(h)))
            elif act == "preview":
                h.send_json(whatsapp_watch.preview())
            elif act == "digest":
                h.send_json(whatsapp_watch.digest_now())
            elif act == "ai_test":
                h.send_json(whatsapp_watch.ai_selftest())
            else:
                h.send_json({"error": "غير معروف"}, 404)
        elif path == "/api/assistant/telegram/status":
            import telegram_link
            h.send_json(telegram_link.status())
        elif path.startswith("/api/assistant/telegram/") and method == "POST":
            import telegram_link
            b = _body(h); act = path.rsplit("/", 1)[1]
            if act == "token":
                telegram_link.set_token(b.get("token")); h.send_json(telegram_link.status())
            elif act == "configure":
                h.send_json(telegram_link.configure(b))
            elif act == "pair":
                telegram_link.new_pair_code(); h.send_json(telegram_link.status())
            elif act == "unpair":
                telegram_link.unpair(); h.send_json(telegram_link.status())
            elif act == "forget":
                telegram_link.forget(); h.send_json(telegram_link.status())
            elif act == "test":
                h.send_json({"sent": telegram_link.send("رسالة تجربة من زاجل ✅")})
            else:
                h.send_error(404)
        elif path == "/api/assistant/app/update/check":
            import app_update
            h.send_json(app_update.check())
        elif path == "/api/assistant/app/update/apply" and method == "POST":
            import app_update
            h.send_json(app_update.apply())
        elif path == "/api/assistant/sync/status":
            import app_update
            h.send_json(app_update.sync_status())
        elif path == "/api/assistant/sync/run" and method == "POST":
            import app_update
            h.send_json(app_update.sync_run())
        elif path == "/api/assistant/agents/stats":
            import agent_metrics
            hrs = int((query.get("hours") or ["24"])[0] or 24)
            inst = {a["id"]: a["installed"] for a in agent_runner.agents()}
            h.send_json(agent_metrics.stats(hrs, inst, [a["id"] for a in agent_runner.agents()]) | {"names": {a["id"]: a["name"] for a in agent_runner.agents()}})
        elif path == "/api/assistant/agents/ping" and method == "POST":
            h.send_json(agent_runner.ping(str(_body(h).get("agent", ""))))
        elif path == "/api/assistant/memory":
            h.send_json({"memory": S.memory_list(), "budget": S.memory_budget(), "status": dict(agent_runner.LEARN) | {"auto": agent_runner.settings().get("auto_learn", True)}})
        elif path == "/api/assistant/memory/add" and method == "POST":
            b = _body(h); S.memory_add(b.get("text"), kind=str(b.get("kind") or "fact"), reason=str(b.get("reason") or "")); h.send_json({"memory": S.memory_list(), "budget": S.memory_budget()})
        elif path == "/api/assistant/memory/update" and method == "POST":
            b = _body(h); S.memory_update(str(b.get("id", "")), b.get("text")); h.send_json({"memory": S.memory_list(), "budget": S.memory_budget()})
        elif path == "/api/assistant/memory/rate" and method == "POST":
            b = _body(h); S.memory_rate(str(b.get("id", "")), b.get("rating", 0)); h.send_json({"memory": S.memory_list(), "budget": S.memory_budget()})
        elif path == "/api/assistant/memory/import/scan" and method == "POST":
            h.send_json({"candidates": S.memory_import_scan(str(_body(h).get("agent", "hermes")))})
        elif path == "/api/assistant/memory/import/commit" and method == "POST":
            b = _body(h); n, k = S.memory_import_commit(str(b.get("agent", "hermes")), b.get("texts") or [])
            h.send_json({"added": n, "skipped": k, "memory": S.memory_list(), "budget": S.memory_budget()})
        elif path == "/api/assistant/memory/delete" and method == "POST":
            S.memory_delete(str(_body(h).get("id", ""))); h.send_json({"memory": S.memory_list()})
        elif path == "/api/assistant/memory/pin" and method == "POST":
            b = _body(h); S.memory_pin(str(b.get("id", "")), b.get("pinned", True)); h.send_json({"memory": S.memory_list()})
        elif path == "/api/assistant/memory/organize" and method == "POST":
            h.send_json({"started": agent_runner.organize(force=True), "status": dict(agent_runner.LEARN)})
        elif path == "/api/assistant/memory/export" and method == "POST":
            fmt = "json" if str(_body(h).get("format")) == "json" else "md"
            text, ext = S.memory_export(fmt)
            d = Path(os.environ.get("PB_EXPORT_DIR") or (Path.home() / "Documents" / "ذاكرة المساعد"))
            d.mkdir(parents=True, exist_ok=True)
            f = d / f"ذاكرة_{time.strftime('%Y%m%d_%H%M')}.{ext}"
            f.write_text(text, encoding="utf-8")
            h.send_json({"path": str(f), "count": len(S.memory_list()), "text": text[:120000]})
        elif path == "/api/assistant/prompts":
            h.send_json({"prompts": S.prompts_list()})
        elif path == "/api/assistant/prompts/save" and method == "POST":
            b = _body(h); h.send_json({"prompts": S.prompt_save(str(b.get("id") or ""), b.get("title"), b.get("text"))})
        elif path == "/api/assistant/prompts/delete" and method == "POST":
            S.prompt_delete(str(_body(h).get("id", ""))); h.send_json({"prompts": S.prompts_list()})
        elif path == "/api/assistant/job":
            h.send_json(agent_runner.job_view(query.get("id", [""])[0]))
        elif path == "/api/assistant/clarify" and method == "POST":
            h.send_json({"id": agent_runner.clarify_start(_body(h).get("text"))})
        elif path == "/api/assistant/clarify/get":
            h.send_json(agent_runner.clarify_view(query.get("id", [""])[0]))
        elif path == "/api/assistant/improve" and method == "POST":
            h.send_json({"id": agent_runner.improve_start(_body(h).get("text"))})
        elif path == "/api/assistant/improve/get":
            h.send_json(agent_runner.improve_view(query.get("id", [""])[0]))
        elif path == "/api/assistant/stop" and method == "POST":
            h.send_json({"stopped": agent_runner.stop(str(_body(h).get("id", "")))})
        else:
            h.send_json({"error": "غير موجود."}, 404)
    except Exception as exc:
        h.send_json({"error": str(exc)}, 400)
