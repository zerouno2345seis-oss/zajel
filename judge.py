"""أسئلة عدة وكلاء + محكِّم يتحقق من الإحالات ويلخّص + بحث متعمق + تقرير Word موحّد.
«الجولة» = سؤال واحد يُرسل لعدة وكلاء في الطرفية؛ حالتها في PB_DATA/rounds/<id>.json، وخيط مراقبة لكل جولة.
- لا منطق طرفية هنا: كل شيء عبر terminal (broadcast / last_answer / state_of) حتى يُستبدل في الاختبارات بـ T وهمي.
- أجوبة الوكلاء تُعطى للمحكِّم في ملف (answers.md) لا لصقًا في الطرفية."""
import json
import html
import random
import re
import threading
import time
from pathlib import Path

DATA = None            # PB_DATA؛ إن لم يُضبط أُخذ من terminal.DATA
T = None               # وحدة الطرفية (تُستبدل في الاختبارات)
POLL = 2.0             # ثوانٍ بين قراءتين لأجوبة الوكلاء
STABLE_POLLS = 3       # قراءات متتالية بلا تغيّر (والوكيل هادئ) = انتهى الجواب
ANSWER_STABLE = 8      # أجوبة الوكلاء: ١٦ ثانية بلا تغيّر والوكيل هادئ
FINAL_SILENCE = 45     # المحكِّم والتعميق: ٩٠ ثانية بلا تغيّر إن لم تظهر «الخلاصة الموحدة»
DONE_MARK = "الخلاصة الموحدة"
TIMEOUT_MIN = 10
DEEP_TIMEOUT_MIN = 30
JUDGE_WAIT = 25 * 60   # أقصى انتظار لجواب المحكِّم (والتعميق)
SEND_WAIT = 90         # أقصى انتظار لوصول الرسالة إلى الطرفية
MAX_TERM = 9           # حد terminal.broadcast (MAX_BROADCAST)
PERPLEXITY = "perplexity"
FINAL = ("done", "timeout", "error")
LETTERS = ["أ", "ب", "ج", "د", "هـ", "و", "ز", "ح", "ط"]

CITE_NOTE = ("\n\n(وثّق كل معلومة بمصدرها: ضع بعدها رقمًا بين معقوفين مثل [1]، واختم الجواب بقسم «المصادر» فيه كل رقم ومصدره كاملًا: "
             "المؤلف، الكتاب، الجزء والصفحة، والرابط إن وجد، والنص المنقول حرفيًا بين «».)")
DEEP_NOTE = ("\n\n[بحث متعمق] قسّم السؤال إلى أسئلة فرعية وأجب عن كل واحد. ابحث في الإنترنت وفي المكتبة الشاملة معًا، واعتمد ما لا يقل عن ٨ مصادر مختلفة. "
             "افتح المصادر الأصلية واقرأها بنفسك ولا تكتفِ بالملخصات، وتحقق من كل نص تنقله قبل أن تكتبه. اذكر مواضع الخلاف بين المصادر والأقوال صراحة. "
             "لا تتعجل؛ لك وقت طويل.")

_LOCK = threading.RLock()
_WATCHING = set()      # الجولات التي يراقبها خيط الآن
ROUNDS = {}            # معرّف ← حالة الجولة (الحقيقة في الذاكرة، تُحفظ على القرص عند كل تغيير)


# ---------- مساعدات ----------
def _t():
    global T
    if T is None:
        import terminal
        T = terminal
    return T


def _data():
    return Path(DATA) if DATA else Path(getattr(_t(), "DATA", Path.home()))


def _dir():
    d = _data() / "rounds"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save(r):
    try:
        p = _dir() / (r["round_id"] + ".json")
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _same_q(seen, question):
    """هل آخر سؤال في سجلّ الوكيل هو سؤال هذه الجولة؟ (يمنع التقاط جواب قديم)"""
    a, b = _norm(seen), _norm(question)[:60]
    return bool(a) and bool(b) and b in a


def _name(aid):
    if aid == PERPLEXITY:
        return "Perplexity"
    if aid == "deep":
        return "بحث متعمق"
    try:
        return _t().BY_ID[aid]["name"]
    except Exception:
        return aid


def _get(rid):
    with _LOCK:
        r = ROUNDS.get(rid)
        if r:
            return r
    p = _dir() / (str(rid) + ".json") if re.fullmatch(r"r_[0-9_a-f]+", str(rid)) else None
    if not p or not p.is_file():
        raise ValueError("جولة غير معروفة.")
    try:
        r = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("جولة غير معروفة.")
    # جولة من جلسة سابقة: لا خيط يراقبها الآن، فلا تبقى «تعمل» إلى الأبد
    for ag in r.get("agents", {}).values():
        if ag.get("state") not in FINAL:
            ag["state"] = "timeout" if ag.get("answer") else "error"
            ag["note"] = ag.get("note") or "انقطعت المراقبة بإعادة تشغيل زاجل"
    if r.get("judge_state") in ("waiting_answers", "running", "needs_input", "web_pending"):
        r["judge_state"] = "error"
    if r.get("deep_state") in ("running", "needs_input"):
        r["deep_state"] = "error"
    with _LOCK:
        ROUNDS[rid] = r
    return r


def round_status(round_id):
    with _LOCK:
        return json.loads(json.dumps(_get(round_id)))


def last_round():
    files = sorted(_dir().glob("r_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files:
        try:
            return round_status(p.stem)
        except ValueError:
            continue
    return None


# ---------- المحكِّم الافتراضي ----------
def get_default_judge():
    try:
        return str(json.loads((_data() / "judge.json").read_text(encoding="utf-8")).get("judge") or "")
    except (OSError, ValueError):
        return ""


def set_default_judge(agent_id):
    agent_id = str(agent_id or "").strip()
    if agent_id and agent_id != PERPLEXITY and agent_id not in getattr(_t(), "BY_ID", {}):
        raise ValueError("وكيل غير معروف.")
    d = _data()
    d.mkdir(parents=True, exist_ok=True)
    (d / "judge.json").write_text(json.dumps({"judge": agent_id}, ensure_ascii=False), encoding="utf-8")
    return agent_id


# ---------- بدء جولة ----------
def start_round(question, answerers, judge="", auto_judge=False, deep=False, timeout_min=None, deep_agents=None, judge_may_answer=False, length=""):
    """deep=True: كل المجيبين يبحثون بحثًا متعمقًا؛ deep_agents: من يبحث منهم فقط (مثل Perplexity وحده)."""
    question = str(question or "").strip()
    if not question:
        raise ValueError("اكتب السؤال أولًا.")
    by_id = getattr(_t(), "BY_ID", {})
    ans = []
    for a in answerers or []:
        a = str(a)
        if a in ans:
            continue
        if a != PERPLEXITY and not (a in by_id and by_id[a].get("cmd")):
            raise ValueError(f"وكيل غير معروف: {a}")
        ans.append(a)
    if not ans:
        raise ValueError("اختر وكيلًا واحدًا على الأقل ليجيب.")
    terms = [a for a in ans if a != PERPLEXITY]
    if len(terms) > MAX_TERM:
        raise ValueError(f"أكثر من {MAX_TERM} وكلاء في الطرفية دفعة واحدة غير مدعوم.")
    judge = str(judge or "").strip() or get_default_judge()
    if judge and judge not in by_id and judge != PERPLEXITY:
        raise ValueError("محكِّم غير معروف.")
    if not judge:
        judge = "claude" if "claude" in by_id else (terms[0] if terms else "")
    if length not in ("", "موجز", "متوسط", "مفصّل"):
        raise ValueError("حجم الجواب غير معروف.")
    if judge and not judge_may_answer:
        ans = [a for a in ans if a != judge]
    if not ans:
        raise ValueError("اختر مجيبًا آخر أو اسمح للمحكّم بالإجابة.")
    terms = [a for a in ans if a != PERPLEXITY]
    deep_set = set(ans) if deep else {str(a) for a in (deep_agents or []) if str(a) in ans}
    tmo = int(timeout_min) if timeout_min else (DEEP_TIMEOUT_MIN if deep_set else TIMEOUT_MIN)
    rid = "r_%s_%04x" % (time.strftime("%Y%m%d_%H%M%S"), random.randint(0, 0xFFFF))
    r = {"round_id": rid, "question": question, "length": length, "deep": bool(deep_set), "deep_agents": sorted(deep_set), "auto_judge": bool(auto_judge), "judge": judge,
         "judge_also_answers": bool(judge and judge in ans), "created": time.time(), "timeout_min": tmo,
         "agents": {a: {"name": _name(a), "state": "waiting", "selected": True, "answer": "", "note": "", "deep": a in deep_set} for a in ans},
         "judge_state": "idle", "verdict": "", "deep_state": "idle", "deep_answer": "", "deep_agent": "", "judge_note": "", "deep_note": ""}
    if terms:
        plain, deeper = [a for a in terms if a not in deep_set], [a for a in terms if a in deep_set]
        if plain:
            _t().broadcast(plain, question + _length_note(length) + CITE_NOTE)
        if deeper:
            _t().broadcast(deeper, question + _length_note(length) + CITE_NOTE + DEEP_NOTE)
    with _LOCK:
        ROUNDS[rid] = r
        _save(r)
    threading.Thread(target=_watch, args=(rid,), daemon=True).start()
    return round_status(rid)


def _length_note(length):
    return f"\n\n(حجم الجواب المطلوب: {length}.)" if length else ""


def reask(round_id, agent_id, deep=False):
    """يعيد سؤال الجولة نفسه على وكيل واحد: يُمسح جوابه السابق ويُنتظر الجديد (وتمتد مهلة الجولة).
    deep: «عمّق» لهذا الوكيل — السؤال نفسه مع تعليمات البحث المتعمق، والجواب الأعمق يحل محل جوابه في شاشته."""
    with _LOCK:
        r = _get(round_id)
        ag = r["agents"].get(agent_id)
        if not ag or agent_id == PERPLEXITY:
            raise ValueError("لا يمكن إعادة السؤال على هذا الوكيل.")
        if deep:
            ag["deep"] = True
            r["timeout_min"] = max(r["timeout_min"], DEEP_TIMEOUT_MIN)
        ag["asks"] = ag.get("asks", 1) + 1
        mark = f"⟦إعادة {ag['asks']}⟧"          # يميّز السؤال المُعاد: قد يأتي الجواب الجديد بالنص نفسه حرفًا بحرف
        ag.update(state="waiting", answer="", note="يعمّق جوابه" if deep else "أُعيد السؤال", mark=mark)
        r["created"] = time.time()                 # مهلة جديدة للجولة كلها
        if r["judge_state"] in ("done", "error"):
            r["judge_state"] = "idle"
        watching = rid_watching(round_id)
        _save(r)
    getattr(_t(), "BROADCAST_STATE", {}).pop(agent_id, None)
    _t().broadcast([agent_id], r["question"] + _length_note(r.get("length", "")) + CITE_NOTE + (DEEP_NOTE if ag.get("deep") else "")
                   + ("\n\n(أعد الجواب أعمق وأوثق مما كتبته في المرة السابقة.)" if deep else "") + "\n" + ag["mark"])
    if not watching:
        threading.Thread(target=_watch, args=(round_id,), daemon=True).start()
    return round_status(round_id)


def rid_watching(rid):
    return rid in _WATCHING


def web_answer(round_id, question, answer):
    """جواب Perplexity (نافذة ويب) تقدّمه الواجهة."""
    answer = _strip_notes(html.unescape(str(answer or "")))      # الويب يعيد الاقتباس &gt; مرمّزًا؛ الطرفية لا تُفكّ لئلا يفسد شرح الأكواد
    if not answer:
        raise ValueError("لا جواب لحفظه.")
    with _LOCK:
        r = _get(round_id)
        ag = r["agents"].get(PERPLEXITY)
        if not ag:
            ag = r["agents"][PERPLEXITY] = {"name": "Perplexity", "state": "waiting", "selected": True, "answer": "", "note": ""}
        ag.update(answer=answer, state="done", note="")
        _save(r)
    return round_status(round_id)


def set_selected(round_id, agent_id, selected):
    with _LOCK:
        r = _get(round_id)
        if agent_id not in r["agents"]:
            raise ValueError("وكيل ليس في هذه الجولة.")
        r["agents"][agent_id]["selected"] = bool(selected)
        _save(r)
    return round_status(round_id)


# ---------- مراقبة أجوبة الوكلاء ----------
def _strip_notes(t):
    """بعض الوكلاء (Hermes من شاشته) يعيدون تعليمات التوثيق أو التعميق الملحقة بالسؤال في أول الجواب: تُحذف."""
    t = str(t or "").strip()
    t = re.sub(r"(?im)^[ \t]*[○●◦▸▹]?[ \t]*\(?Thought for\s+\d[^\n]*(?:\n|$)", "", t).strip()
    for note in (CITE_NOTE, DEEP_NOTE):
        head = _norm(note)[:25]
        if head and _norm(t[:400]).startswith(head):
            end = t.find(")") if note is CITE_NOTE else t.find("\n\n")
            t = t[end + 1:].strip() if 0 <= end < 1500 else t
    parts = re.split(r"\n\s*\n", t, maxsplit=1)
    if len(parts) == 2 and len(parts[0]) <= 180 and re.match(r"^(?:سأ(?:ذكر|تحقق|بحث|جيب|عرض|وضح|قدم|ستعرض)|سوف\s+(?:أذكر|أتحقق|أبحث|أجيب)|Let me\s+(?:check|look|find|answer|verify))\b", parts[0], re.I) and not re.search(r"[«»\[\]\d٠-٩:]|\b(?:أن|هو|هي|حكمه|واجب|حرام)\b", parts[0]):
        t = parts[1].strip()
    return _unfence(t)


def clean_verdict(t):
    """نص الحكم الملتقط من الشاشة يبدأ أحيانًا بتعليماتنا نفسها (يردّدها الوكيل) ويلحقه ضجيج واجهة («Thought for …»): يُقصّ من العنوان الحقيقي."""
    t = str(t or "").strip()
    heads = list(re.finditer(r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?الخلاصة الموحدة[ \t]*$", t))
    if heads:
        t = t[heads[-1].start():]
    t = re.sub(r"(?m)^[ \t]*[○●◦▸▹]\s*Thought for .*$", "", t)
    t = re.sub(r"(?m)^[ \t]*\(?Thought for \d.*$", "", t)
    return t.strip()


def _unfence(t):
    """Hermes يبدأ جوابه أحيانًا بسطر ``` فارغ (ويختمه بآخر): تُنزع الكتلة المحيطة بكل الجواب فقط، وكتل الكود الحقيقية في الوسط تبقى."""
    lines = t.split("\n")
    if not lines or lines[0].strip() != "```":
        return t
    fences = sum(1 for ln in lines if ln.strip().startswith("```"))
    if fences % 2 == 1:
        return "\n".join(lines[1:]).strip()           # فتح بلا إغلاق
    if lines[-1].strip() == "```" and fences == 2:
        return "\n".join(lines[1:-1]).strip()          # الجواب كله داخل كتلة واحدة
    return t


def _poll_agent(r, aid, ag, probe):
    """يحدّث ag بحسب ما في الطرفية. probe: حالة ثابتة بين القراءات (عدّاد الثبات)."""
    T_ = _t()
    bs = getattr(T_, "BROADCAST_STATE", {}).get(aid) or {}
    bst = bs.get("state")
    if bst in ("skipped", "error") and not ag["answer"]:
        ag.update(state="error", note=bs.get("note") or "تعذّر الإرسال إلى الوكيل")
        return
    if bst in ("queued", "starting") and not ag["answer"]:
        ag.update(state="waiting", note=bs.get("note") or "")
        return
    try:
        res = T_.last_answer(aid)
    except Exception:
        return
    text = _strip_notes(str(res.get("answer") or "")) if _same_q(res.get("question"), r["question"]) else ""
    if text and ag.get("mark") and ag["mark"] not in str(res.get("question") or ""):
        text = ""                                 # بعد «أعد السؤال»: هذا جواب السؤال السابق لا المُعاد
    try:
        st = T_.state_of(aid)[0]
    except Exception:
        st = "idle"
    if st == "waiting":
        if text:
            ag["answer"] = text
        ag.update(state="needs_input", note="ينتظر ردّك في الطرفية")
        probe["stable"] = 0
        return
    if not text:
        ag.update(state="waiting", note="")
        return
    if text != ag["answer"]:
        ag.update(answer=text, state="writing", note="")
        probe["stable"] = 0
        return
    probe["stable"] = probe.get("stable", 0) + 1
    if probe["stable"] >= ANSWER_STABLE and st != "working":        # أطول من ثلاث قراءات: الوكيل قد يكتب تمهيدًا ثم يبحث
        ag.update(state="done", note="")
    else:
        ag.update(state="writing", note="")


def _watch(rid):
    _WATCHING.add(rid)
    try:
        _watch_loop(rid)
    finally:
        _WATCHING.discard(rid)


def _watch_loop(rid):
    probes = {}
    while True:
        time.sleep(POLL)
        with _LOCK:
            r = ROUNDS.get(rid)
            if not r:
                return
            deadline = r["created"] + r["timeout_min"] * 60
            todo = [(a, ag) for a, ag in r["agents"].items() if ag["state"] not in FINAL and a != PERPLEXITY]
        changed = False
        for aid, ag in todo:
            before = (ag["state"], ag["answer"])
            _poll_agent(r, aid, ag, probes.setdefault(aid, {}))        # قراءة الطرفية خارج القفل
            changed |= before != (ag["state"], ag["answer"])
        with _LOCK:
            expired = time.time() > deadline
            if expired:
                for ag in r["agents"].values():
                    if ag["state"] not in FINAL:
                        ag["state"] = "timeout"
                        ag["note"] = "انتهت المهلة" + (" (هذا ما كتبه حتى الآن)" if ag["answer"] else "")
                        changed = True
            alldone = all(ag["state"] in FINAL for ag in r["agents"].values())
            if changed or alldone:
                _save(r)
        if alldone:
            break
    with _LOCK:
        go = r["auto_judge"] and r["judge_state"] == "idle" and any(ag["selected"] and ag["answer"].strip() for ag in r["agents"].values())
    if go:
        run_judge(rid)


# ---------- المحكِّم ----------
_SELF = [
    r"(?:as|I am|I'm|this is)\s+(?:an?\s+)?(?:Claude|ChatGPT|GPT[-\w.]*|Codex|Gemini|Hermes|Nemotron|OpenCode|Antigravity|Perplexity|an AI(?: assistant| language model)?)[^.\n]*[.،,]?",
    r"(?:أنا|بصفتي|بوصفي|هنا)\s+(?:نموذج\s+)?(?:Claude|كلود|ChatGPT|Codex|Gemini|جيميني|Hermes|Perplexity|مساعد ذكاء اصطناعي)[^.\n]*[.،]?",
]
_MODEL_NAMES = r"\b(Claude|Anthropic|ChatGPT|OpenAI|GPT-?\d[\w.]*|Codex|Gemini|Google|Hermes|Nemotron|OpenCode|Antigravity|Perplexity)\b|كلود|جيميني"


def anonymize(text, names=()):
    """يزيل ما يدل على صاحب الجواب: عبارات التعريف بالنفس وأسماء النماذج والوكلاء."""
    t = str(text or "")
    for p in _SELF:
        t = re.sub(p, "", t, flags=re.I)
    t = re.sub(_MODEL_NAMES, "[وكيل]", t, flags=re.I)
    for n in names:
        if n and len(str(n)) > 2:
            t = re.sub(re.escape(str(n)), "[وكيل]", t, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def build_answers_file(r, only=None):
    """يكتب answers.md ويعيد (المسار، مفتاح الرموز {حرف: معرّف}). الأجوبة المختارة وحدها (وفي only إن أُعطي)."""
    items = [(a, ag) for a, ag in r["agents"].items() if ag["selected"] and ag["answer"].strip() and (only is None or a in only)]
    key = {}
    out = ["# أجوبة الوكلاء عن السؤال", "", "## السؤال", r["question"], ""]
    if r.get("judge_also_answers"):
        random.shuffle(items)
        names = [ag["name"] for _, ag in items] + [a for a, _ in items]
        for n, (a, ag) in enumerate(items):
            L = LETTERS[n]
            key[L] = a
            out += [f"## الجواب ({L})", anonymize(ag["answer"], names), ""]
    else:
        for a, ag in items:
            key[ag["name"]] = a
            out += [f"## جواب {ag['name']}", ag["answer"].strip(), ""]
    import citation_check
    refs = []
    for index, (label, aid) in enumerate(key.items()):
        answer = next(ag["answer"] for a, ag in items if a == aid)
        if r.get("judge_also_answers"):
            answer = anonymize(answer, [ag["name"] for _, ag in items] + [a for a, _ in items])
        refs.extend(dict(ref, answer_label=label) for ref in citation_check.extract_citations(answer, f"ج{index + 1}-"))
    refs = citation_check.check_citations(refs)
    r["citation_ids"] = [ref["id"] for ref in refs]
    out += ["## فهرس الإحالات والتحقق الآلي", ""]
    for ref in refs:
        out.append(f"- {ref['id']} | {ref['status']} | {ref['reason']} | {ref['source']} | الجواب: {ref['answer_label']}")
    if not refs:
        out.append("لم تُستخرج إحالات قابلة للفهرسة.")
    d = _dir() / r["round_id"]
    d.mkdir(parents=True, exist_ok=True)
    p = d / "answers.md"
    p.write_text("\n".join(out), encoding="utf-8")
    return p, key


OUTPUT_ORDER = ("اكتب تقريرك بهذا الترتيب بالضبط، وبعناوين ## بهذه الأسماء حرفيًا:\n"
                "١. ## الخلاصة الموحدة — فقرة أو فقرتان متماسكتان تعتمدان على المصادر الموسومة ✅ وحدها.\n"
                "٢. ## جدول الاتفاق والاختلاف — أعمدته: المسألة | ما اتفقت عليه الأجوبة | مواضع الاختلاف.\n"
                "٣. ## تقييم كل جواب — لكل جواب اكتب الدقة: ٨ من ١٠، والتوثيق: ٨ من ١٠، والشمول: ٨ من ١٠ مع سبب لكل معيار، ثم الدرجة الكلية من ٣٠.\n"
                "٤. ## جدول التحقق من الإحالات — أعمدته: الجواب | الإحالة | الحالة | ملاحظة. الحالات: ✅ موثّق (وجدت النص في المصدر) · ⚠️ فيه خلل (المصدر موجود لكن النص أو الصفحة أو العزو مختلف) · ❌ غير موجود · ❓ تعذّر التحقق.\n"
                "٥. ## تنبيهات — أخطاء وتناقضات وملاحظات منهجية.\n"
                "٦. ## ما يحتاج تحقق المستخدم — ما لم تستطع حسمه بنفسك.\n")

STYLE_RULES = ("قواعد الكتابة (إلزامية):\n"
               "- المتن نظيف: جمل الحكم والخلاصة وحدها. لا أقواس توضيحية ولا استدراكات ولا أسماء كتب ولا أرقام صفحات داخل المتن، ولا عبارات من نوع «ويُلاحظ أن» أو «علمًا بأن».\n"
               "- اكتب التنبيهات وما يحتاج تحقق المستخدم بجمل كاملة في المتن، ولا تُخفِ مضمون القسمين في الحواشي. الحواشي للمصادر والتوضيح فقط.\n"
               "- الحواشي بصيغة Markdown: ضع بعد الكلمة مباشرة علامة مثل [^1] (بلا أقواس حولها)، وأرقامها متسلسلة تبدأ من 1 بترتيب ظهورها في التقرير، بلا تكرار ولا قفز، والعلامة نفسها لا تُستعمل لحاشيتين. "
               "وفي آخر التقرير اكتب تعريف كل حاشية في سطر واحد كامل لا ينكسر: [^1]: المؤلف، الكتاب، الجزء والصفحة (أو الرابط) — ثم توضيحك إن لزم. لا تكتب قسمًا اسمه «المصادر».\n"
               "- الجداول جداول Markdown حقيقية: سطر العناوين ثم سطر الفاصل |---|---|، ثم صف لكل سطر. كل خلية عبارة قصيرة (نحو ١٥ كلمة على الأكثر) بلا قوائم ولا أسطر داخلها، ولا علامات حواشٍ داخل الجداول (ضع المصدر في عمود الملاحظة مختصرًا).\n"
               "- لا تعد كتابة تعليماتي ولا عناوينها في التقرير، ولا تضف جملة افتتاحية أو ختامية خارج الأقسام الستة.\n")


VERIFY_PROTO = ("بروتوكول التحقق (إلزامي):\n"
                "- استخدم كل معرّف في فهرس الإحالات حرفيًا مرة واحدة في جدول التحقق، ولا تضف معرّفات أو تكررها. ابحث بنفسك فقط عما بقي ❓ ولا تغير ✅ أو ❌ الآلية إلا بدليل واضح.\n"
                "- افتح بنفسك كل مصدر استشهد به أي جواب. للكتب الشرعية استعمل أدوات المكتبة الشاملة إن وُجدت عندك (مثل shamela_verify_quote وshamela_get_page) وإلا فافتح الرابط على الويب.\n"
                "- لا تضف أي مصدر من عندك ولا تستشهد بما لم يرد في الأجوبة؛ ما لم تفتحه فلا تدّعِ أنك تحققت منه (علّمه ❓).\n"
                "- الخلاصة الموحدة لا تعتمد إلا على المصادر ✅، وما عداها يُذكر بعلامته ولا يُبنى عليه حكم.\n")


def judge_prompt(r, answers_path, vpath=None):
    p = [f"⟦حكم:{r['round_id']}⟧ أنت محكِّم محايد. اقرأ الملف {answers_path} (فيه السؤال وأجوبة عدة وكلاء) ثم حكّم بينها.", VERIFY_PROTO]
    if r["judge_also_answers"]:
        p.append("تنبيه: أحد الأجوبة كتبه المحكِّم نفسه (أنت)، وقد أُخفيت الأسماء ورُتّبت الأجوبة عشوائيًا بالرموز أ ب ج. لا تجامل جوابًا لظنك أنه جوابك؛ "
                 "ولا بد من درجة لكل معيار مع سبب مكتوب لكل جواب بلا استثناء. اذكر في التقرير: «المحكِّم شارك بالجواب (رمزه)» إن عرفته.")
    p.append(OUTPUT_ORDER)
    p.append(STYLE_RULES)
    if r.get("length"):
        p.append(f"حجم الجواب المطلوب: {r['length']}؛ قيّم الشمول على أساسه.")
    p.append("حدّد حكمك بما تحققت منه فقط: التزام الجواب بصيغة السؤال (كالإيجاز المطلوب) يُحسب له أو عليه، ولا تُدخل في الخلاصة ما لم يثبت ✅.")
    if vpath:
        p.append(f"التسليم: اكتب تقريرك النهائي كاملًا بصيغة Markdown في الملف {vpath} (أنشئه أو استبدل ما فيه)، ثم اكتب في المحادثة سطرًا واحدًا فقط: «تم حفظ التقرير». لا تلصق التقرير في المحادثة.")
    return "\n".join(p)


def _after_send(aid, wait=SEND_WAIT):
    """ينتظر حتى تُحسم حالة broadcast. يعيد (ok، ملاحظة)."""
    bs_ = getattr(_t(), "BROADCAST_STATE", {})
    t0 = time.time()
    while time.time() - t0 < wait:
        s = bs_.get(aid) or {}
        if s.get("state") == "sent":
            return True, ""
        if s.get("state") in ("skipped", "error"):
            return False, s.get("note") or "تعذّر الإرسال"
        time.sleep(min(POLL, 0.5))
    return False, "لم تصل الرسالة إلى الوكيل في الوقت المناسب"


def _approve_report_write(T_, aid, out_file):
    """بعض المحكِّمين (Antigravity) يطلبون إذنًا لإنشاء ملف التقرير لأنه خارج مجلدهم المسموح فيتوقف التحكيم: نوافق على هذا الإذن وحده،
    أي سؤالٌ يذكر مسار ملف تقرير الجولة نفسه وعبارة إنشاء/كتابة، وأي سؤال آخر يبقى للمستخدم."""
    try:
        tail = T_._tail(aid, 14)
    except Exception:
        return False
    full = str(out_file)
    # شاشة Antigravity تقطع المسار الطويل (يظهر منه رأسه فقط): يكفي أن يكون سطر المسار الظاهر بداية مسار ملف التقرير وطوله معقول
    shown = [ln.strip() for ln in tail.splitlines() if ln.strip().startswith("/") and len(ln.strip()) >= 25]
    if full not in tail and not any(full.startswith(x) for x in shown):
        return False
    if not re.search(r"(allow (creation|this|once)|yes, allow|allow .{0,20}(file|write|edit))", tail, re.I):
        return False
    if re.search(r"(delete|remove|rm |sudo|network|install|execute|run command)", tail, re.I):
        return False
    try:
        T_.send(aid, "", keys=["Enter"])
        return True
    except Exception:
        return False


def _ask_agent(aid, prompt, marker, set_state, wait=JUDGE_WAIT, out_file=None):
    """يرسل prompt إلى وكيل ويقرأ جوابه (السؤال المحتوي marker). set_state(state, text, note). يعيد (state, text)."""
    T_ = _t()
    getattr(T_, "BROADCAST_STATE", {}).pop(aid, None)      # لا نقرأ حالة إرسال قديمة
    try:
        T_.broadcast([aid], prompt)
    except ValueError as e:
        set_state("error", "", str(e))
        return "error", ""
    ok, note = _after_send(aid)
    if not ok:
        set_state("error", "", note)
        return "error", ""
    text, prev, stable, t0 = "", None, 0, time.time()
    fprev, fstable, approvals = None, 0, 0
    while time.time() - t0 < wait:
        time.sleep(POLL)
        if out_file:      # التقرير المكتوب في ملف Markdown حقيقي أنظف من نص الشاشة (جداول سليمة، سطور غير مكسورة، بلا ضجيج الواجهة)
            try:
                ftxt = Path(out_file).read_text(encoding="utf-8").strip()
            except OSError:
                ftxt = ""
            if ftxt:
                fstable = fstable + 1 if ftxt == fprev else 0
                fprev = ftxt
                set_state("running", ftxt, "")
                if fstable >= 3 and DONE_MARK in ftxt:
                    return "done", ftxt
        try:
            res = T_.last_answer(aid)
            st = T_.state_of(aid)[0]
        except Exception:
            continue
        cur = str(res.get("answer") or "").strip() if marker in str(res.get("question") or "") else ""
        if st == "waiting":
            if out_file and approvals < 3 and _approve_report_write(T_, aid, out_file):
                approvals += 1
                continue
            set_state("needs_input", fprev or cur, "ينتظر ردّك في الطرفية")
            stable = 0
            continue
        if not cur:
            if not fprev:
                set_state("running", "", "")
            continue
        if cur != prev:
            prev, stable = cur, 0
            if not fprev:
                set_state("running", cur, "")
            continue
        stable += 1
        # المحكِّم يتوقف بين خطواته (قراءة ملف، فتح مصدر) فيبدو منتهيًا بعد جملته الأولى: لا يُعدّ منتهيًا إلا وفي جوابه
        # الخلاصة الموحدة، أو بعد ثبات طويل (FINAL_SILENCE) إن كتب بغير هذه العناوين
        if st != "working" and ((stable >= STABLE_POLLS and DONE_MARK in cur) or stable >= FINAL_SILENCE):
            return "done", (fprev if out_file and fprev and DONE_MARK in fprev else cur)
    set_state("error", prev or "", "انتهت مهلة انتظار الجواب")
    return "error", prev or ""


def run_judge(round_id, judge="", deep_verify=True):
    with _LOCK:
        r = _get(round_id)
        if r["judge_state"] in ("running", "waiting_answers", "needs_input", "web_pending"):
            return round_status(round_id)
        if judge:
            if judge not in _t().BY_ID and judge != PERPLEXITY:
                raise ValueError("محكِّم غير معروف.")
            r["judge"] = judge
            r["judge_also_answers"] = judge in r["agents"]
        if not r["judge"]:
            raise ValueError("اختر محكِّمًا.")
        r["judge_state"], r["verdict"], r["judge_note"] = "waiting_answers", "", ""
        _save(r)
    threading.Thread(target=_judge_thread, args=(round_id, bool(deep_verify)), daemon=True).start()
    return round_status(round_id)


def _judge_thread(rid, deep_verify):
    r = _get(rid)

    def st(state, text="", note=""):
        with _LOCK:
            r["judge_state"], r["judge_note"] = state, note
            if text:
                r["verdict"] = text
            _save(r)
    # يحكّم بالأجوبة المكتملة الآن ولا ينتظر المتأخرين (طلب المستخدم)؛ ما زال يُكتب لا يدخل
    with _LOCK:
        ready = {a for a, ag in r["agents"].items() if ag["selected"] and ag["answer"].strip() and ag["state"] in FINAL}
        if not ready:
            st("error", "", "لا جواب مكتمل بعد يُحكَّم فيه")
            return
        late = [ag["name"] for a, ag in r["agents"].items() if ag["selected"] and a not in ready]
    path, key = build_answers_file(r, only=ready)       # يجلب مصادر الإحالات من الشبكة: خارج القفل العام كي لا يتجمد استطلاع الواجهة
    with _LOCK:
        vpath = path.parent / "verdict.md"
        try:
            vpath.unlink()
        except OSError:
            pass
        prompt = judge_prompt(r, path, vpath) + ("" if deep_verify else "\nالتحقق السريع مقبول هذه المرة: تحقق من الاستشهادات الجوهرية وعلّم الباقي ❓.")
        judge = r["judge"]
        if judge == PERPLEXITY:     # نافذة ويب بلا ملفات: الواجهة تنفّذ البروتوكول (web_verdict)، وهنا مراقب المهلة فقط
            r["web_judge"] = {"messages": web_judge_messages(r, path.read_text(encoding="utf-8"), deep_verify), "attempt": 1,
                              "parts": [], "continues": 0, "late": late, "key": key, "started": time.time()}
            r["judge_state"], r["verdict"] = "web_pending", ""
            r["judge_note"] = "يرسل المادة إلى نافذة Perplexity" + (("؛ لم يدخل (لم يكتمل): " + "، ".join(late)) if late else "")
            _save(r)
    if judge == PERPLEXITY:
        t0 = time.time()
        while time.time() - t0 < JUDGE_WAIT:
            time.sleep(POLL * 5)
            if r["judge_state"] not in ("web_pending", "running"):
                return
        with _LOCK:
            if r["judge_state"] in ("web_pending", "running"):
                st("error", "", "انتهت مهلة انتظار حكم Perplexity (هل نافذة الطرفيات مفتوحة؟)")
        return
    st("running", "", ("لم يدخل التحكيم (لم يكتمل): " + "، ".join(late)) if late else "")
    state, text = _ask_agent(judge, prompt, f"⟦حكم:{rid}⟧", st, out_file=vpath)
    if state == "done":
        st("done", _finish_verdict(r, clean_verdict(text), late, key, judge))


def _finish_verdict(r, text, late, key, judge):
    """ملحقات الحكم المشتركة بين المحكِّمين: من لم يدخل التحكيم، ومفتاح الرموز إن شارك المحكِّم بالجواب."""
    text = _correct_scores(text)
    ids = r.get("citation_ids", [])
    if ids:
        section = re.search(r"(?ms)^#{1,6}\s*جدول التحقق من الإحالات[^\n]*\n(.*?)(?=^#{1,6}\s|\Z)", text)
        table = section.group(1) if section else ""
        counts = {i: len(re.findall(r"(?<![\w-])" + re.escape(i) + r"(?![\w-])", table)) for i in ids}
        bad = [i for i, n in counts.items() if n != 1]
        extra = sorted(set(re.findall(r"(?<![\w-])ج\d+-[٠-٩]+(?![\w-])", table)) - set(ids))
        if bad or extra:
            detail = [f"{i} ({counts[i]})" for i in bad] + [f"{i} (غير موجود في الفهرس)" for i in extra]
            text = text.rstrip() + "\n\n⚠️ فهرس الإحالات غير مكتمل أو فيه تكرار أو معرّفات زائدة: " + "، ".join(detail) + "."
    if late:
        text = text.rstrip() + "\n\n---\nلم تدخل هذا التحكيم لأنها لم تكتمل عند بدئه: " + "، ".join(late) + "."
    if r["judge_also_answers"]:
        mine = next((L for L, a in key.items() if a == judge), "")
        text = text.rstrip() + "\n\n---\n"
        if mine and f"المحكِّم شارك بالجواب ({mine})" not in text:
            text += f"المحكِّم شارك بالجواب ({mine}).\n"
        text += "⚠️ تحيّز محتمل: شارك المحكّم بالإجابة؛ فُحصت الإحالات المستخرجة من جوابه آليًا مع بقية الأجوبة.\n"
        text += "مفتاح الرموز: " + "، ".join(f"{L} = {_name(a)}" for L, a in sorted(key.items())) + "\n"
    return text


def _correct_scores(text):
    """تصحيح المجموع عند وجود المعايير الثلاثة بوضوح داخل تقييم جواب واحد."""
    digits = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    gap = r"[^#]{0,600}?"          # لا يعبر عنوانًا (###) فلا يمتد من جواب إلى آخر
    pattern = re.compile(r"(?s)(الدقة\s*[:：]\s*([0-9٠-٩]+)\s*(?:من|/)\s*(?:10|١٠))" + gap + r"(التوثيق\s*[:：]\s*([0-9٠-٩]+)\s*(?:من|/)\s*(?:10|١٠))" + gap +
                         r"(الشمول\s*[:：]\s*([0-9٠-٩]+)\s*(?:من|/)\s*(?:10|١٠))" + gap + r"(الدرجة الكلية\s*[:：]\s*)([0-9٠-٩]+)")
    def fix(m):
        values = [int(m.group(2).translate(digits)), int(m.group(4).translate(digits)), int(m.group(6).translate(digits))]
        if any(n > 10 for n in values):
            return m.group()
        result = str(sum(values)).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
        return m.group()[:m.start(8)-m.start()] + result
    return pattern.sub(fix, text)


# ---------- Perplexity محكِّمًا ----------
WEB_PROTOCOL_DOC = """بروتوكول تحكيم Perplexity (نافذة ويب داخل زاجل، لا طرفية ولا ملفات ولا أدوات الشاملة، لكن عنده بحث الويب).

الأدوار: الخادم (هذه الدوال) يقرر كل خطوة ويحفظ الحالة في r["web_judge"]؛ الواجهة (driveWebJudge في terminal_ui.js)
تنفّذها في النافذة بحقن JavaScript (كتابة في مربع السؤال، قراءة آخر جواب) وتبلّغ النتيجة إلى /api/term/round/web_verdict.

١. التسليم: answers.md (الأجوبة المختارة، مجهَّلة إن شارك المحكِّم) يُقسَّم على حدود الأسطر إلى أجزاء ≤ WEB_CHUNK حرف
   (مربع Perplexity لا يتسع لنص طويل، ولا رفع ملفات بالحقن). إن اتسعت رسالة واحدة: التعليمات ثم المادة في رسالة واحدة.
   وإلا: رسالة لكل جزء «⟦حكم:…⟧ الجزء k من N … ردّ بسطر: استلمت الجزء k من N» والواجهة تنتظر ردّه قبل التالي،
   ثم رسالة أخيرة «انتهى الإرسال (N أجزاء)» فيها تعليمات الحكم. كل محاولة في محادثة جديدة.
٢. التعليمات: WEB_VERIFY (يتحقق من كل إحالة ببحث الويب ويفتح الصفحة الأصلية؛ ما لم يجده ❓؛ لا يضيف مصادر)
   + OUTPUT_ORDER + STYLE_RULES (متن نظيف، حواشٍ [^n] متسلسلة، جداول Markdown حقيقية) كبقية المحكِّمين.
٣. العلامتان: أول سطر في جوابه WEB_BEGIN وآخر سطر WEB_END. ما بينهما هو التقرير، ووجود WEB_END هو دليل الاكتمال
   (لا الثبات وحده). والتقرير نفسه داخل كتلة ```markdown: صفحة Perplexity تحوّل [^n] المكتوبة نصًّا إلى شارات مصادرها\n   وتبتلع تعريفاتها، أما داخل كتلة الكود فيبقى النص خامًا (جُرّب)؛ والأسوار تُنزع في web_verdict_parse.
   ثم يمر النص على clean_verdict و_finish_verdict كبقية المحكِّمين.
٤. الأعطال (web_verdict يعيد action):
   - wait: ما زال يكتب.
   - send + message: بدأ التقرير وتوقف بلا WEB_END ثابتًا WEB_STALL ث (انقطاع/حد الطول) ← WEB_CONTINUE «أكمل من حيث توقفت»
     حتى WEB_MAX_CONTINUE مرات؛ الأجزاء تُضمّ. بعدها يُقبل ناقصًا مع تنبيه ⚠️ في آخره.
   - restart: لا علامة بدء وثبت WEB_REFUSE_STALL ث (رفض أو جواب خارج الموضوع)، أو عطل في النافذة (لا مربع إدخال،
     لم يُرسل، الإدراج فشل) ← محادثة جديدة وإعادة التسليم كله، حتى WEB_MAX_ATTEMPTS محاولات.
   - fail: نفدت المحاولات، أو Perplexity يطلب تسجيل الدخول (لا يُسجَّل عنه) ← judge_state=error وملاحظة واضحة.
   - done: اكتمل (أو قُبل ناقصًا) ← judge_state=done.
   ومراقب في _judge_thread يُنهي الحالة بخطأ بعد JUDGE_WAIT إن لم تقدها الواجهة (نافذة الطرفيات مغلقة مثلًا)."""
WEB_BEGIN = "ZAJEL-VERDICT-BEGIN"
WEB_END = "ZAJEL-VERDICT-END"
WEB_CHUNK = 6000
WEB_STALL = 90
WEB_REFUSE_STALL = 40
WEB_MAX_CONTINUE = 2
WEB_MAX_ATTEMPTS = 2
WEB_VERIFY = ("بروتوكول التحقق (إلزامي؛ ليس عندك ملفات ولا أدوات المكتبة الشاملة، وعندك بحث الويب):\n"
              "- ابحث في الويب عن كل إحالة في الأجوبة وافتح الصفحة الأصلية (نسخة الكتاب على shamela.ws أو المكتبات الرقمية، أو الموقع المحال إليه) وقارن النص المنقول بها.\n"
              "- لا تضف أي مصدر من عندك ولا تستشهد بما لم يرد في الأجوبة؛ ما لم تصل إليه بالبحث فعلّمه ❓ ولا تدّعِ أنك تحققت منه.\n"
              "- الخلاصة الموحدة لا تعتمد إلا على المصادر ✅، وما عداها يُذكر بعلامته ولا يُبنى عليه حكم.\n")
WEB_CONTINUE = (f"توقف تقريرك قبل علامة النهاية. أكمل من الموضع الذي توقفت عنده تمامًا، دون تكرار ما كتبته ودون مقدمة، "
                f"وبالقواعد نفسها، واختم بسطر وحده: {WEB_END}")
_WEB_ERRORS = {"login": "Perplexity يطلب تسجيل الدخول: سجّل دخولك في نافذته (🔎 Perplexity) ثم أعد التحكيم",
               "noinput": "لم أجد مربع السؤال في صفحة Perplexity", "insert": "لم يقبل مربع Perplexity النص",
               "nosubmit": "لم تُرسل الرسالة في Perplexity", "nowindow": "نافذة Perplexity غير متاحة"}


def _web_split(text, size=WEB_CHUNK):
    """يقسم النص على حدود الأسطر إلى أجزاء ≤ size (السطر الأطول من size يُقطع)."""
    parts, cur = [], ""
    for line in str(text).split("\n"):
        while len(line) > size:
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(line[:size])
            line = line[size:]
        if cur and len(cur) + 1 + len(line) > size:
            parts.append(cur)
            cur = line
        else:
            cur = (cur + "\n" + line) if cur else line
    if cur.strip():
        parts.append(cur)
    return parts


def web_judge_prompt(r, deep_verify=True):
    p = [f"⟦حكم:{r['round_id']}⟧ أنت محكِّم محايد بين أجوبة عدة وكلاء عن سؤال واحد (المادة: السؤال ثم الأجوبة).", WEB_VERIFY, VERIFY_PROTO]
    if r["judge_also_answers"]:
        p.append("تنبيه: الأسماء مخفية والأجوبة مرتبة عشوائيًا بالرموز أ ب ج؛ لا بد من درجة لكل معيار مع سبب مكتوب لكل جواب بلا استثناء.")
    p += [OUTPUT_ORDER, STYLE_RULES,
          "حدّد حكمك بما تحققت منه فقط: التزام الجواب بصيغة السؤال (كالإيجاز المطلوب) يُحسب له أو عليه، ولا تُدخل في الخلاصة ما لم يثبت ✅."]
    if r.get("length"):
        p.append(f"حجم الجواب المطلوب: {r['length']}؛ قيّم الشمول على أساسه.")
    if not deep_verify:
        p.append("التحقق السريع مقبول هذه المرة: تحقق من الاستشهادات الجوهرية وعلّم الباقي ❓.")
    p.append(f"التسليم: اكتب في أول سطر من جوابك {WEB_BEGIN} وحده، ثم التقرير كاملًا داخل كتلة كود واحدة تبدأ بسطر ```markdown وتنتهي بسطر ``` "
             f"(حتى تبقى علامات الحواشي [^1] وتعريفاتها والجداول نصًّا خامًا كما كتبتها)، ثم في آخر سطر {WEB_END} وحده. "
             "لا تكتب شيئًا قبل علامة البدء ولا بعد علامة النهاية.")
    return "\n".join(p)


def web_judge_messages(r, answers_text, deep_verify=True, size=WEB_CHUNK):
    """رسائل التسليم بالترتيب (انظر WEB_PROTOCOL_DOC، البند ١)."""
    prompt = web_judge_prompt(r, deep_verify)
    if len(prompt) + len(answers_text) + 40 <= size:
        return [prompt + "\n\n===== المادة =====\n" + answers_text]
    chunks = _web_split(answers_text, size - 300)
    n = len(chunks)
    msgs = [f"⟦حكم:{r['round_id']}⟧ مادة تحكيم — الجزء {k} من {n}. لا تحلل ولا تبحث الآن؛ احفظ النص فقط، "
            f"وردّ بسطر واحد: «استلمت الجزء {k} من {n}».\n\n===== الجزء {k} =====\n{c}" for k, c in enumerate(chunks, 1)]
    msgs.append(f"انتهى الإرسال ({n} أجزاء). المادة هي الأجزاء من 1 إلى {n} أعلاه مجتمعة.\n\n" + prompt)
    return msgs


def web_verdict_parse(raw):
    """يعيد (النوع، النص): done (بين العلامتين)، partial (بعد البدء بلا نهاية)، tail (قبل النهاية بلا بدء: تكملة)، none."""
    t = str(raw or "")
    b = t.find(WEB_BEGIN)
    e = t.find(WEB_END, b + len(WEB_BEGIN) if b >= 0 else 0)
    if b >= 0 and e >= 0:
        return "done", _web_unfence(t[b + len(WEB_BEGIN):e])
    if b >= 0:
        return "partial", _web_unfence(t[b + len(WEB_BEGIN):])
    if e >= 0:
        return "tail", _web_unfence(t[:e])
    return "none", t.strip()


def _web_unfence(t):
    """التقرير يُطلب داخل كتلة ```markdown (صفحة Perplexity تحوّل [^n] خارجها إلى شارات مصادرها وتبتلع تعريفاتها): تُنزع الأسوار وحدها."""
    t = re.sub(r"^\s*```[\w-]*[ \t]*\n", "", str(t).strip())
    return re.sub(r"\n?```\s*$", "", t).strip()


def _web_fail_or_restart(r, wj, why):
    if why == "login" or wj["attempt"] >= WEB_MAX_ATTEMPTS:
        r["judge_state"], r["judge_note"] = "error", _WEB_ERRORS.get(why, why)
        return "fail"
    wj.update(attempt=wj["attempt"] + 1, parts=[], continues=0)
    r["judge_note"] = f"إعادة المحاولة {wj['attempt']} من {WEB_MAX_ATTEMPTS}: " + _WEB_ERRORS.get(why, why)
    return "restart"


def web_verdict(round_id, raw="", stable=0, error=""):
    """خطوة من بروتوكول Perplexity محكِّمًا: الواجهة تبلّغ آخر جواب في النافذة (أو عطلًا)، وتعود {action, message?, status}."""
    with _LOCK:
        r = _get(round_id)
        wj = r.get("web_judge")
        if r.get("judge") != PERPLEXITY or not wj or r["judge_state"] not in ("web_pending", "running"):
            return {"action": "stop", "status": round_status(round_id)}
        msg, stable = "", float(stable or 0)
        if error:
            action = _web_fail_or_restart(r, wj, str(error))
        else:
            kind, body = web_verdict_parse(raw)
            cont = bool(wj["parts"]) and kind in ("tail", "none")         # ردّ على «أكمل»: يُضمّ إلى ما سبق
            full = "\n".join(wj["parts"] + [body]) if cont else body
            complete = kind == "done" or (kind == "tail" and (cont or DONE_MARK in body))
            if complete:
                r["judge_state"], r["judge_note"] = "done", ""
                r["verdict"] = _finish_verdict(r, clean_verdict(full), wj.get("late") or [], wj.get("key") or {}, PERPLEXITY)
                action = "done"
            elif kind == "partial" or cont:
                r["judge_state"], r["verdict"] = "running", clean_verdict(full)
                r["judge_note"] = "Perplexity يكتب التقرير"
                action = "wait"
                if stable >= WEB_STALL:
                    if wj["continues"] < WEB_MAX_CONTINUE:
                        wj["parts"], wj["continues"] = [full], wj["continues"] + 1
                        action, msg = "send", WEB_CONTINUE
                        r["judge_note"] = f"توقف قبل علامة النهاية: طُلب منه الإكمال ({wj['continues']})"
                    else:
                        r["judge_state"], r["judge_note"] = "done", "التقرير ناقص: لم تصل علامة النهاية"
                        r["verdict"] = _finish_verdict(r, clean_verdict(full) + "\n\n---\n⚠️ التقرير ناقص: توقف Perplexity قبل علامة النهاية.",
                                                       wj.get("late") or [], wj.get("key") or {}, PERPLEXITY)
                        action = "done"
            elif body and DONE_MARK in body and stable >= WEB_STALL:     # كتب التقرير ونسي العلامتين
                r["judge_state"], r["judge_note"] = "done", "كتب Perplexity التقرير بلا علامتي البدء والنهاية"
                r["verdict"] = _finish_verdict(r, clean_verdict(body), wj.get("late") or [], wj.get("key") or {}, PERPLEXITY)
                action = "done"
            elif body and stable >= WEB_REFUSE_STALL and DONE_MARK not in body:
                action = _web_fail_or_restart(r, wj, "لم يبدأ التقرير (رفض أو جواب خارج المطلوب)")
            else:
                action = "wait"
        _save(r)
        out = {"action": action, "status": round_status(round_id)}
        if msg:
            out["message"] = msg
        return out


# ---------- التعميق ----------
def deepen(round_id, agent_id=""):
    with _LOCK:
        r = _get(round_id)
        if not agent_id and r["deep_state"] in ("running", "needs_input"):
            return round_status(round_id)
        if agent_id:
            if agent_id not in r["agents"] or agent_id == PERPLEXITY:
                raise ValueError("وكيل ليس في هذه الجولة.")
            own = True
        else:
            own = False
            if not any(ag["selected"] and ag["answer"].strip() for ag in r["agents"].values()):
                raise ValueError("اختر جوابًا واحدًا على الأقل ليُعمَّق منه.")
            target = r["judge"] or get_default_judge() or next(iter(r["agents"]))
    if own:
        return reask(round_id, agent_id, deep=True)       # تعميق وكيل واحد: جوابه الأعمق في شاشته
    with _LOCK:
        r.update(deep_state="running", deep_answer="", deep_agent=target, deep_note="")
        _save(r)
    threading.Thread(target=_deep_thread, args=(round_id, target, bool(agent_id)), daemon=True).start()
    return round_status(round_id)


def _deep_thread(rid, target, own):
    r = _get(rid)

    def st(state, text="", note=""):
        with _LOCK:
            r["deep_state"], r["deep_note"] = state, note
            if text:
                r["deep_answer"] = text
            _save(r)
    marker = f"⟦تعميق:{rid}⟧"
    if own:
        prompt = (f"{marker} أعد العمل على سؤالك السابق بعمق أكبر، وابدأ مما كتبته: «{r['question']}»." + DEEP_NOTE + CITE_NOTE)
    else:
        with _LOCK:
            sel = {k: v for k, v in r["agents"].items() if v["selected"] and v["answer"].strip()}
            body = "\n\n".join(f"## جواب {v['name']}\n{v['answer']}" for v in sel.values())
        d = _dir() / rid
        d.mkdir(parents=True, exist_ok=True)
        p = d / "deep_input.md"
        p.write_text(f"# السؤال\n{r['question']}\n\n{body}\n", encoding="utf-8")
        prompt = (f"{marker} ابدأ بحثًا متعمقًا عن السؤال: «{r['question']}». اقرأ الملف {p} فيه أجوبة سابقة اتخذها نقطة انطلاق: "
                  "تحقق منها، وسدّ ثغراتها، وزد عليها." + DEEP_NOTE + CITE_NOTE)
    state, text = _ask_agent(target, prompt, marker, st)
    if state == "done":
        st("done", text)


# ---------- التقرير ----------
def export_round(round_id, out_dir=None):
    import answer_export
    r = round_status(round_id)
    sel = [(ag["name"], ag["answer"]) for ag in r["agents"].values() if ag["selected"] and ag["answer"].strip()]
    missing = [ag["name"] for ag in r["agents"].values() if ag["selected"] and not ag["answer"].strip()]
    if not (sel or r["verdict"].strip() or r["deep_answer"].strip()):
        raise ValueError("لا شيء يُصدَّر بعد: لا أجوبة ولا حكم.")
    out = answer_export.export_round(r["question"], r["verdict"], sel, r["deep_answer"], out_dir=out_dir,
                                     judge=_name(r["judge"]) if r["verdict"] else "", also=r["judge_also_answers"])
    out["missing"] = missing
    return out
