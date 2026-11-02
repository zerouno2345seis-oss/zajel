"""حفظ دائم لمساعد زاجل: المحادثات السابقة، الذاكرة (أشياء مهمة تُحفظ تلقائيًا)، والأوامر الجاهزة.
كلها ملفات JSON صغيرة داخل مجلد بيانات زاجل؛ لا مفاتيح ولا كلمات مرور فيها."""
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

DATA = None
LOCK = threading.RLock()
MAX_CHATS, MAX_MSGS, MAX_MEMORY, MAX_PROMPTS = 60, 80, 80, 40


def init(data_dir):
    global DATA
    DATA = Path(data_dir)


def _file(name):
    return DATA / name


def _load(name, default):
    try:
        return json.loads(_file(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(name, obj):
    p = _file(name)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


# ---------- المحادثات ----------
def chats_list():
    with LOCK:
        d = _load("assistant_chats.json", {})
    rows = [{"id": k, "title": v.get("title") or "محادثة", "updated": v.get("updated", 0), "agent": v.get("agent", ""), "model": v.get("model", ""),
             "count": len(v.get("messages", []))} for k, v in d.items()]
    return sorted(rows, key=lambda r: -r["updated"])


def chat_get(cid):
    with LOCK:
        c = _load("assistant_chats.json", {}).get(cid)
    if not c:
        raise ValueError("المحادثة غير موجودة.")
    return {"id": cid, "title": c.get("title", ""), "agent": c.get("agent", ""), "model": c.get("model", ""), "messages": c.get("messages", []), "updated": c.get("updated", 0)}


def chat_session(cid):
    """ما يلزم لاستئناف المحادثة بعد إعادة التشغيل: وكيلها ونموذجها ومعرّف جلسة الوكيل."""
    with LOCK:
        c = _load("assistant_chats.json", {}).get(cid) or {}
    return {"agent": c.get("agent"), "model": c.get("model"), "session": c.get("session"), "n": c.get("n", 0)} if c else None


def chat_append(cid, agent, model, msg, session=None, n=None):
    with LOCK:
        d = _load("assistant_chats.json", {})
        c = d.setdefault(cid, {"title": "", "messages": [], "agent": agent, "model": model})
        c["agent"], c["model"] = agent, model
        if not c["title"] and msg.get("role") == "user":
            c["title"] = " ".join(str(msg.get("text", "")).split())[:48]
        c["messages"].append(msg)
        c["messages"] = c["messages"][-MAX_MSGS:]
        if session:
            c["session"] = session
        if n is not None:
            c["n"] = n
        c["updated"] = time.time()
        for k in sorted(d, key=lambda x: d[x].get("updated", 0))[:-MAX_CHATS]:
            d.pop(k, None)
        _save("assistant_chats.json", d)


def chat_rename(cid, title):
    with LOCK:
        d = _load("assistant_chats.json", {})
        if cid not in d:
            raise ValueError("المحادثة غير موجودة.")
        d[cid]["title"] = str(title or "").strip()[:60] or d[cid]["title"]
        _save("assistant_chats.json", d)


def chat_delete(cid):
    with LOCK:
        d = _load("assistant_chats.json", {})
        d.pop(cid, None)
        _save("assistant_chats.json", d)


# ---------- الذاكرة ----------
# مرجعها ملف نصي مقروء (assistant_memory.md) يمكن فتحه وتعديله باليد؛ كل عنصر يبدأ بسطر «§ …» ثم نصه.
KINDS = ("fact", "preference", "alias", "place", "routine", "decision", "question")
SECRET_WORDS = ("password", "كلمة المرور", "كلمة السر", "token", "api key", "apikey", "مفتاح api", "رمز الدخول", "secret")
STALE_DAYS = 90
MEM_BUDGET = 2200          # حجم ما يُحقن في كل محادثة (أحرف)، مثل دفتر Hermes الصغير
MEM_TEXT_MAX = 240
MEM_FILE = "assistant_memory.md"
_SECRET_RES = [re.compile(p) for p in (
    r"\bsk-[A-Za-z0-9_\-]{16,}", r"\bsk-ant-[A-Za-z0-9_\-]{10,}", r"\bAKIA[0-9A-Z]{12,}", r"\bgh[pousr]_[A-Za-z0-9]{20,}",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}", r"\bxox[bapsr]-[A-Za-z0-9\-]{10,}", r"\bAIza[0-9A-Za-z_\-]{20,}", r"\bnvapi-[A-Za-z0-9_\-]{20,}",
    r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}", r"-----BEGIN [A-Z ]*PRIVATE KEY", r"[A-Za-z0-9._%+\-]+:[^\s@/]{3,}@[A-Za-z0-9.\-]+")]
_BLOB_RE = re.compile(r"[A-Za-z0-9_\-+/=]{32,}")
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ \-]?){13,19}(?!\d)")
_META_RE = re.compile(r"(\w+)=([^|]*)")


def _luhn(num):
    s, alt = 0, False
    for ch in reversed(num):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        s += d
        alt = not alt
    return s % 10 == 0


def is_secret(text):
    """يكشف ما يشبه سرًّا: كلمات دالة، أو أنماط مفاتيح معروفة، أو سلسلة عشوائية طويلة، أو رقم بطاقة."""
    t = str(text or "")
    low = t.lower()
    if any(w in low for w in SECRET_WORDS):
        return True
    if any(r.search(t) for r in _SECRET_RES):
        return True
    for m in _BLOB_RE.findall(t):
        if re.search(r"\d", m) and re.search(r"[A-Za-z]", m):
            return True
    for m in _CARD_RE.findall(t):
        digits = re.sub(r"\D", "", m)
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return True
    return False


def _clean(text, limit=MEM_TEXT_MAX):
    return " ".join(str(text or "").split())[:limit]


def _norm(r):
    r["id"] = str(r.get("id") or uuid.uuid4().hex[:8])
    r["text"] = _clean(r.get("text"))
    r["kind"] = r.get("kind") if r.get("kind") in KINDS else "fact"
    r["reason"] = _clean(r.get("reason"), 160)
    try:
        r["rating"] = max(-1, min(1, int(r.get("rating") or 0)))
    except (TypeError, ValueError):
        r["rating"] = 0
    r["pinned"] = bool(r.get("pinned"))
    r["auto"] = bool(r.get("auto"))
    r["source"] = _clean(r.get("source") or "زاجل", 40)
    for k in ("uses",):
        try:
            r[k] = int(r.get(k) or 0)
        except (TypeError, ValueError):
            r[k] = 0
    for k in ("t", "last_used"):
        try:
            r[k] = float(r.get(k) or 0)
        except (TypeError, ValueError):
            r[k] = 0.0
    r["last_used"] = r["last_used"] or r["t"]
    r["deleted"] = bool(r.get("deleted"))
    try:
        r["updated"] = float(r.get("updated") or 0) or r["t"]
    except (TypeError, ValueError):
        r["updated"] = r["t"]
    return r


def _mem_parse(text, with_deleted=False):
    rows = []
    text = re.sub(r"\A(?:\s*#[^\n]*\n)+", "", text)      # سطور العنوان في أول الملف
    for block in re.split(r"(?m)^§", text):
        lines = [l.rstrip() for l in block.strip().splitlines()]
        if not lines or not "".join(lines).strip():
            continue
        meta, body = {}, []
        if "=" in lines[0] and "|" in lines[0] or lines[0].strip().startswith("id="):
            meta = {k: v.strip() for k, v in _META_RE.findall(lines[0])}
            lines = lines[1:]
        reason = ""
        for l in lines:
            if l.startswith("سبب:"):
                reason = l[4:].strip()
            elif l.strip():
                body.append(l.strip())
        if not body:
            continue
        r = {"id": meta.get("id"), "text": " ".join(body), "kind": meta.get("kind"), "reason": reason, "rating": meta.get("rating"),
             "pinned": meta.get("pinned") in ("1", "true"), "auto": meta.get("auto") in ("1", "true"), "source": meta.get("source"),
             "uses": meta.get("uses"), "t": meta.get("t") or time.time(), "last_used": meta.get("last_used"),
             "deleted": meta.get("deleted") in ("1", "true"), "updated": meta.get("updated")}
        rows.append(_norm(r))
    return rows if with_deleted else [r for r in rows if not r["deleted"]]


def _mem_dump(rows):
    out = ["# ذاكرة مساعد زاجل — يمكنك تعديل النصوص هنا مباشرة. كل عنصر يبدأ بسطر § وسطر وصفي."]
    for r in rows:
        out.append(f"§ id={r['id']} | kind={r['kind']} | rating={r['rating']} | pinned={int(r['pinned'])} | source={r['source']} | uses={r['uses']} | auto={int(r['auto'])} | t={int(r['t'])} | last_used={int(r['last_used'])} | updated={r['updated']:.3f}" + (" | deleted=1" if r.get("deleted") else ""))
        out.append(r["text"])
        if r.get("reason"):
            out.append("سبب: " + r["reason"])
    return "\n".join(out) + "\n"


TOMB_DAYS = 90        # شواهد الحذف تبقى هذه المدة ليصل الحذف إلى الكمبيوتر الآخر عند المزامنة
_CMP = ("text", "kind", "reason", "rating", "pinned")


def _mem_all():
    p = _file(MEM_FILE)
    try:
        return _mem_parse(p.read_text(encoding="utf-8"), with_deleted=True) if p.exists() else []
    except OSError:
        return []


def _mem_write(rows):
    p = _file(MEM_FILE)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(_mem_dump(rows), encoding="utf-8")
    os.replace(tmp, p)


def _mem_save(rows):
    """يحفظ القائمة الحيّة: ما اختفى منها يصير شاهد حذف، وما تغيّر نصه أو تقييمه أو تثبيته يأخذ وقت تحديث جديدًا."""
    now = time.time()
    old = {r["id"]: r for r in _mem_all()}
    out = []
    for r in rows:
        o = old.get(r["id"])
        if o is None or o["deleted"] or any(o[k] != r[k] for k in _CMP):
            r["updated"] = now
        r["deleted"] = False
        out.append(r)
    live = {r["id"] for r in out}
    for i, o in old.items():
        if i in live:
            continue
        if o["deleted"]:
            if now - o["updated"] < TOMB_DAYS * 86400:
                out.append(o)
        else:
            o["deleted"] = True; o["updated"] = now
            out.append(o)
    _mem_write(out)


def memory_merge_remote(remote_text):
    """يدمج ذاكرة الكمبيوتر الآخر: لكل عنصر يفوز الأحدث تحديثًا (وشاهد الحذف عنصر كغيره). يعيد (أُضيف، تحدّث، حُذف)."""
    with LOCK:
        local = {r["id"]: r for r in _mem_all()}
        added = updated = removed = 0
        for r in _mem_parse(remote_text, with_deleted=True):
            l = local.get(r["id"])
            if l is None:
                local[r["id"]] = r
                if not r["deleted"]:
                    added += 1
            elif r["updated"] > l["updated"] or (r["updated"] == l["updated"] and r["deleted"] and not l["deleted"]):
                if r["deleted"] and not l["deleted"]:
                    removed += 1
                elif not r["deleted"]:
                    updated += 1
                local[r["id"]] = r
        _mem_write(sorted(local.values(), key=lambda r: r["t"]))
        return added, updated, removed


def memory_dump_text():
    with LOCK:
        return _mem_dump(_mem_all())


def memory_list():
    with LOCK:
        p = _file(MEM_FILE)
        if p.exists():
            try:
                return _mem_parse(p.read_text(encoding="utf-8"))
            except OSError:
                return []
        old = _file("assistant_memory.json")
        if not old.exists():
            return []
        rows = [_norm(dict(r, source=r.get("source") or "زاجل")) for r in _load("assistant_memory.json", []) if isinstance(r, dict)]
        bak = _file("assistant_memory.json.bak")
        if not bak.exists():
            bak.write_bytes(old.read_bytes())       # نسخة احتياطية من القديم تبقى كما هي
        _mem_save(rows)
        return rows


def memory_add(text, auto=False, kind="fact", reason="", source="زاجل"):
    text = _clean(text)
    if len(text) < 4:
        raise ValueError("النص قصير.")
    if is_secret(text) or is_secret(reason):
        raise ValueError("لا تُحفظ كلمات المرور ولا المفاتيح في الذاكرة.")
    kind = kind if kind in KINDS else "fact"
    with LOCK:
        m = memory_list()
        for r in m:
            if r["text"] == text:
                return r
        now = time.time()
        row = _norm({"id": uuid.uuid4().hex[:8], "text": text, "kind": kind, "reason": reason if kind == "decision" else "", "auto": bool(auto),
                     "source": source, "t": now, "last_used": now})
        m.append(row)
        if len(m) > MAX_MEMORY:      # عند الامتلاء يُحذف أقدم غير مثبّت أقلّه استعمالًا ولا يمسّ المقيَّم إيجابًا
            drop = sorted((r for r in m if not r["pinned"] and r["rating"] <= 0 and r is not row), key=lambda r: (r["uses"], r["last_used"]))
            if drop:
                m.remove(drop[0])
        _mem_save(m)
        return row


def memory_update(mid, text):
    text = _clean(text)
    if len(text) < 4 or is_secret(text):
        raise ValueError("نص غير صالح.")
    with LOCK:
        m = memory_list()
        for r in m:
            if r["id"] == mid and not r["pinned"]:
                r["text"] = text
                r["last_used"] = time.time()
                _mem_save(m)
                return r
    raise ValueError("العنصر غير موجود أو مثبّت.")


def memory_pin(mid, pinned):
    with LOCK:
        m = memory_list()
        for r in m:
            if r["id"] == mid:
                r["pinned"] = bool(pinned)
        _mem_save(m)


def memory_rate(mid, rating):
    with LOCK:
        m = memory_list()
        for r in m:
            if r["id"] == mid:
                r["rating"] = max(-1, min(1, int(rating or 0)))
        _mem_save(m)


def memory_delete(mid):
    with LOCK:
        _mem_save([r for r in memory_list() if r["id"] != mid])


def memory_gc():
    """تنظيف حتمي: يحذف المحفوظ تلقائيًا ولم يُستعمل منذ مدة طويلة وغير مثبّت ولا مقيَّم إيجابًا."""
    cut = time.time() - STALE_DAYS * 86400
    with LOCK:
        m = memory_list()
        keep = [r for r in m if r["pinned"] or r["rating"] > 0 or not r["auto"] or r["uses"] > 0 or r["last_used"] > cut]
        if len(keep) != len(m):
            _mem_save(keep)
        return len(m) - len(keep)


def _tokens(text):
    """كلمات الطلب مطبَّعة (همزات، تاء مربوطة، «ال» التعريف، بلا علامات ترقيم) لمقارنة التشابه."""
    import re
    out = set()
    for w in re.findall(r"[^\W\d_]+", str(text).lower()):
        w = w.translate(str.maketrans("أإآةى", "ااااي")).replace("\u0640", "")
        if w.startswith("ال") and len(w) > 4:
            w = w[2:]
        if len(w) >= 3:
            out.add(w)
    return out


def memory_apply_ops(ops):
    """يطبّق قرارات المنظِّم الذكي بحدود صارمة: ٦ إضافات كحد أقصى، ولا يُمسّ المثبّت."""
    done = {"add": 0, "update": 0, "delete": 0}
    if not isinstance(ops, dict):
        return done
    ids = {r["id"]: r for r in memory_list()}
    for mid in (ops.get("delete") or [])[:12]:
        r = ids.get(str(mid))
        if r and not r["pinned"]:
            memory_delete(r["id"]); done["delete"] += 1
    for u in (ops.get("update") or [])[:12]:
        try:
            memory_update(str(u.get("id")), u.get("text")); done["update"] += 1
        except (ValueError, AttributeError):
            pass
    for a in (ops.get("add") or [])[:6]:
        try:
            memory_add(a.get("text"), auto=True, kind=a.get("kind") or "fact", source="المنظِّم"); done["add"] += 1
        except (ValueError, AttributeError):
            pass
    return done


def _mem_line(r):
    tag = {"decision": "[قرار معتمد] ", "question": "[سؤال مفتوح] "}.get(r["kind"], "")
    why = f" (السبب: {r['reason']})" if r.get("reason") else ""
    return f"- [#{r['id']}] {tag}{r['text']}{why}"


def _mem_pick(query=""):
    """يملأ ميزانية الحقن بالترتيب: المثبّت، ثم القرارات، ثم الأقرب لطلبه، ثم المقيَّم، ثم الأكثر استعمالًا. المرفوض (تقييم سلبي) لا يدخل."""
    q = _tokens(query)
    rows = [r for r in memory_list() if r["rating"] >= 0]
    rows.sort(key=lambda r: (r["pinned"], r["kind"] == "decision", len(q & _tokens(r["text"])), r["rating"], r["uses"], r["last_used"]), reverse=True)
    pick, used = [], 0
    for r in rows:
        n = len(r["text"])
        if used + n > MEM_BUDGET:
            continue
        pick.append(r)
        used += n
    return pick, used


def memory_budget():
    return {"used": _mem_pick()[1], "limit": MEM_BUDGET}


def memory_prompt(query=""):
    """يختار الأنسب لهذا الطلب ضمن الميزانية ويسجّل الاستعمال."""
    pick, _ = _mem_pick(query)
    if not pick:
        return ""
    with LOCK:
        full = memory_list()
        ids = {x["id"] for x in pick}
        now = time.time()
        for r in full:
            if r["id"] in ids:
                r["uses"] += 1; r["last_used"] = now
        _mem_save(full)
    return "[ذاكرة المستخدم (حقائق وتفضيلات وقرارات تعلّمتها عنه؛ استفد منها):\n" + "\n".join(_mem_line(r) for r in pick) + "]\n"


# ---------- استيراد من ذاكرة وكيل (معاينة ثم حفظ) ----------
def _guess_kind(t):
    if any(w in t for w in ("قرار", "معتمد", "اعتمد")):
        return "decision"
    if any(w in t for w in ("يفضل", "يفضّل", "يريد", "يحب", "يكره", "لا تحذف", "لا يريد")):
        return "preference"
    if any(w in t for w in ("كل يوم", "كل صباح", "عادة", "قبل كل")):
        return "routine"
    if "؟" in t or t.endswith("?"):
        return "question"
    return "fact"


def _import_sources():
    return {"hermes": [Path.home() / ".hermes" / "memories" / "MEMORY.md", Path.home() / ".hermes" / "memories" / "USER.md"]}


def memory_import_scan(agent):
    """قراءة فقط: يقترح عناصر من ملفات ذاكرة الوكيل ويصنّفها (جديد/مكرر/سر) دون حفظ أي شيء."""
    files = _import_sources().get(agent)
    if files is None:
        raise ValueError("هذا المصدر غير مدعوم بعد.")
    existing = {frozenset(_tokens(r["text"])) for r in memory_list()}
    seen, out = set(), []
    for f in files:
        try:
            raw = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for part in re.split(r"(?m)^§|\n\s*\n", raw):
            for line in part.splitlines():
                t = _clean(re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line.replace("**", "")))
                if t.startswith("#") or len(t) < 8 or t.endswith(":"):
                    continue
                key = frozenset(_tokens(t))
                if not key or key in seen:
                    continue
                seen.add(key)
                st = "secret" if is_secret(t) else ("dup" if key in existing else "new")
                out.append({"text": t, "kind": _guess_kind(t), "source": "Hermes", "status": st})
    return out[:80]


def memory_import_commit(agent, texts):
    """يعيد الفحص على الخادم (سر/تكرار) ثم يحفظ المحدَّد فقط."""
    if agent not in _import_sources():
        raise ValueError("هذا المصدر غير مدعوم بعد.")
    allowed = {c["text"]: c for c in memory_import_scan(agent)}
    added = skipped = 0
    for t in (texts or [])[:80]:
        c = allowed.get(_clean(t))
        if not c or c["status"] != "new":
            skipped += 1
            continue
        try:
            memory_add(c["text"], kind=c["kind"], source=c["source"])
            added += 1
        except ValueError:
            skipped += 1
    return added, skipped


def similar_exchanges(query, exclude_cid="", n=2):
    """طلبات سابقة مشابهة (تشابه كلمات) مع خلاصة ما أُجيب به، تُعرض تلميحًا لا حقيقة."""
    q = _tokens(query)
    if len(q) < 2:
        return ""
    with LOCK:
        d = _load("assistant_chats.json", {})
    best = []
    for cid, c in d.items():
        msgs = c.get("messages", [])
        for i, m in enumerate(msgs):
            if m.get("role") != "user":
                continue
            t = _tokens(m.get("text", ""))
            if not t:
                continue
            sc = len(q & t) / max(1, len(q | t))
            if sc >= 0.34 and cid != exclude_cid:   # المحادثة الجارية سياقها حاضر أصلًا
                ans = next((x for x in msgs[i + 1:i + 3] if x.get("role") == "assistant" and x.get("state") == "done" and x.get("text")), None)
                if ans:
                    best.append((sc, m.get("t", 0), m["text"][:140], ans["text"][:260]))
    best = sorted(best, reverse=True)[:n]
    if not best:
        return ""
    return "[طلبات سابقة مشابهة (تلميح فقط؛ تحقق من الواقع الحالي بالأدوات قبل الاعتماد):\n" + "\n".join(f"- «{a}» ← أُجيب بنحو: {b}" for _, _, a, b in best) + "]\n"


# ---------- الأوامر الجاهزة ----------
def prompts_list():
    return _load("assistant_prompts.json", [])


def prompt_save(pid, title, text):
    title, text = str(title or "").strip()[:40], str(text or "").strip()[:1500]
    if not title or not text:
        raise ValueError("الاسم والنص مطلوبان.")
    with LOCK:
        d = _load("assistant_prompts.json", [])
        for r in d:
            if pid and r["id"] == pid:
                r["title"], r["text"] = title, text
                break
        else:
            d.append({"id": uuid.uuid4().hex[:8], "title": title, "text": text})
        _save("assistant_prompts.json", d[-MAX_PROMPTS:])
        return d


def prompt_delete(pid):
    with LOCK:
        _save("assistant_prompts.json", [r for r in _load("assistant_prompts.json", []) if r["id"] != pid])


KIND_AR = {"decision": "قرارات معتمدة", "question": "أسئلة مفتوحة", "preference": "تفضيلات وقواعد", "fact": "حقائق", "alias": "أسماء مختصرة", "place": "أماكن", "routine": "عادات وروتين"}


def memory_export(fmt="md"):
    """يصدّر الذاكرة بترتيبها الحالي (بعد تنظيم المساعد): المثبّت أولًا ثم الأنواع، وفي كل نوع الأكثر استعمالًا. يعيد (نص، امتداد)."""
    rows = memory_list()
    order = list(KIND_AR)
    rows.sort(key=lambda r: (not r.get("pinned"), order.index(r.get("kind", "fact")) if r.get("kind", "fact") in order else 9, -r.get("uses", 0)))
    if fmt == "json":
        return json.dumps([{k: r.get(k) for k in ("text", "kind", "pinned", "uses", "auto", "created")} for r in rows], ensure_ascii=False, indent=1), "json"
    out = ["# ذاكرة مساعد زاجل", "", f"عدد العناصر: {len(rows)} · تاريخ التصدير: {time.strftime('%Y-%m-%d %H:%M')}", ""]
    pinned = [r for r in rows if r.get("pinned")]
    if pinned:
        out += ["## 📌 المثبّت", ""] + [f"- {r['text']}" for r in pinned] + [""]
    for k in order:
        grp = [r for r in rows if not r.get("pinned") and r.get("kind", "fact") == k]
        if grp:
            out += [f"## {KIND_AR[k]}", ""] + [f"- {r['text']}" + (f"  _(استُعمل {r['uses']} مرة)_" if r.get("uses") else "") for r in grp] + [""]
    return "\n".join(out), "md"
