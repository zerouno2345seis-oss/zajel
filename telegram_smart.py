"""الموظف الذكي في تيليجرام: تعطيه رؤوس أقلام، فيسألك أسئلة قليلة، ثم يخطّط أين يبحث في قنوات تيليجرام ويبحث بنفسه ضمن حدود ثابتة.

القاعدة: النموذج يقترح فقط (أسئلة وخطة بحث بصيغة JSON)، والتنفيذ كله بالشيفرة وبسقوف لا يتجاوزها:
- لا اشتراك ولا انضمام ولا قنوات خاصة؛ بحث في قنوات عامة فقط.
- حدّ أقصى للقنوات وللطلبات في كل مهمة، وفواصل بشرية (من telegram_account).
- لا تحميل ولا حفظ ولا حذف إلا بزر منك.
"""
import json
import re
import threading
import time

import telegram_account as A

MAX_QUESTIONS = 3
MAX_CHANNELS = 30
MAX_QUERIES = 5
MAX_KNOWN = 8

SM = {}     # محادثة ← {"brief","qs","ans","i","plan","stage"}

# ================= خبرة الموظف: أين يُوجَد ماذا =================
KNOWLEDGE = """
You are a very experienced research librarian and "channel scout" for Telegram, working for an Arabic-speaking user (Sunni Islamic studies student/researcher, also general books, courses, films, documentaries).
Your value is knowing WHERE things live on Telegram and HOW they are named there. Use this field knowledge:
- Islamic/Arabic scholarly books: channels of digital libraries (مكتبة, الشاملة, وقفية, خزانة, كتب PDF, مكتبة الكتب, تراث). Books are posted as PDF/DOCX files with the title in the file name and caption; classical works appear under the title and often the author's name (مثل «المغني لابن قدامة»). Editions matter: «تحقيق» + muhaqqiq name, «ط. دار …». Search BOTH the title alone and title+author. Arabic variants: hamza (أ/إ/ا), ta marbuta (ة/ه), alef maqsura (ى/ي), with/without tashkeel, with/without «ال».
- Audio lessons/lectures (دروس صوتية, شرح, محاضرات): posted as MP3/voice; names are «شرح كتاب X للشيخ Y» — search the book title plus «شرح», and the scholar name. Sheikh-named channels are the main source; discover channels by the scholar's name.
- Academic (theses, papers, journals): channels named «رسائل جامعية», «أبحاث», «مجلات محكّمة», «PDF علمية»; files named by the title; Latin-script works by English title/DOI/author surname.
- Spanish/English books: channels named «Libros PDF», «Descargar libros», «Biblioteca», «Ebooks»; files named «Title - Author.pdf»; search the author's name AND the title, and transliteration/misspelling variants (the user may spell foreign names by ear).
- Films/series/documentaries: channels named «Películas», «Movies», «Cine», «أفلام», «وثائقيات»; titles are posted in the original language and sometimes in Arabic translation; include year when known; Spanish/English/Arabic title variants.
- Courses/tutorials: channels named «Cursos», «Courses», «دورات», «Udemy», «Coursera»; look for the course title and instructor.
General rules: a result channel is only useful if it hosts FILES (documents/video/audio), not just chatter. Prefer big, active channels. Include translations of the topic word into the likely languages of the channels (Arabic/Spanish/English), because Telegram search is word-matching.
Public channels only. Never invent channel usernames you are not reasonably sure of: put guesses in known_channels only if you genuinely recall them; they will be verified automatically and dropped if they do not exist.
"""

INTAKE_PROMPT = KNOWLEDGE + """
TASK 1 (intake). The user gave rough bullet points of what they want. Decide what you still NEED to ask, like a smart employee who does not waste the boss's time.
Rules:
- Ask at most 3 questions, only things that change WHERE or HOW you will search and that you cannot infer: kind of material (book/audio/video/papers), language(s), specific author/edition/year, file format, how many results, scope (all known libraries or discover new channels).
- Never ask what the user already said. If the request is clear enough, ask nothing.
- Each question has 2-5 short Arabic options (the UI adds a free-text box).
- Write in Modern Standard Arabic.
Reply with JSON only, no code fences:
{"understood":"<one short Arabic sentence restating the goal>","questions":[{"q":"<Arabic question>","options":["..",".."]}]}
== User's bullet points ==
"""

PLAN_PROMPT = KNOWLEDGE + """
TASK 2 (plan). Using the user's request and their answers, produce the search plan.
Fields:
- channel_queries: up to 8 short phrases to DISCOVER relevant public channels (by their NAME). Mix Arabic/Spanish/English as appropriate to the material. Include the scholar/author/topic name if channels are likely named after them.
- known_channels: up to 6 public channel usernames (without @) you genuinely know are relevant; empty list if unsure.
- search_queries: up to 5 queries to search INSIDE the channels' files/messages: the exact title, title+author, the Arabic/Latin spelling variants, translations, and common file-name forms. Most specific first.
- type: one of all, book, video, audio.
- summary: one short Arabic sentence telling the user what you will do (which kinds of channels, which spellings).
Reply with JSON only, no code fences:
{"summary":"..","channel_queries":[".."],"known_channels":[".."],"search_queries":[".."],"type":"all"}
== Request and answers ==
"""

REFINE_PROMPT = KNOWLEDGE + """
TASK 3 (refine). The first search found little or nothing. You are given the request, the previous plan and the channels already searched.
Produce a NEW plan that differs: other languages, other spellings, other channel-name ideas (by author/publisher/genre), broader or narrower titles. Do NOT repeat previous queries.
Same JSON format as TASK 2. JSON only.
== Context ==
"""


# ================= استدعاء النموذج =================
def _agents():
    """بالسرعة: claude أولًا (ثوانٍ) ثم agy (قد يستغرق دقائق)."""
    import agent_runner
    out = []
    for a in ("claude", "agy"):
        spec = agent_runner.AGENTS.get(a)
        if spec and agent_runner._which(spec["bin"]):
            out.append(a)
    return out


def llm(prompt, model="sonnet"):
    """يجرّب الوكلاء بالترتيب ويعيد أول ردّ غير فارغ. بلا أدوات (locked). model يخص claude فقط."""
    import agent_runner
    err = ""
    for a in _agents():
        try:
            out, e = agent_runner._oneshot(a, prompt, "tgsmart", locked=True, model=model)
        except Exception as ex:
            err = str(ex)[:100]
            continue
        if (out or "").strip():
            return out
        err = (e or "")[:100]
    raise ValueError("تعذّر الوصول إلى النموذج" + (": " + err if err else ""))


def parse_json(text):
    a, b = (text or "").find("{"), (text or "").rfind("}")
    if a < 0 or b <= a:
        raise ValueError("ردّ غير مفهوم")
    return json.loads(text[a:b + 1])


def clean_intake(d):
    qs = []
    for q in (d.get("questions") or [])[:MAX_QUESTIONS]:
        txt = str(q.get("q") or "").strip()
        opts = [str(o).strip()[:30] for o in (q.get("options") or []) if str(o).strip()][:5]
        if txt:
            qs.append({"q": txt[:200], "options": opts})
    return {"understood": str(d.get("understood") or "").strip()[:200], "questions": qs}


def _usernames(items):
    out = []
    for u in items or []:
        u = str(u).strip().lstrip("@")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", u) and u.lower() not in [x.lower() for x in out]:
            out.append(u)
    return out[:MAX_KNOWN]


def _clean_list(items, n, maxlen=60):
    out = []
    for x in items or []:
        x = re.sub(r"\s+", " ", str(x)).strip()[:maxlen]
        if len(x) >= 2 and x.lower() not in [o.lower() for o in out]:
            out.append(x)
    return out[:n]


def clean_plan(d, brief=""):
    sq = _clean_list(d.get("search_queries"), MAX_QUERIES)
    if not sq and brief:
        sq = [brief[:60]]
    t = d.get("type") if d.get("type") in ("all", "book", "video", "audio") else "all"
    return {"summary": str(d.get("summary") or "").strip()[:300], "channel_queries": _clean_list(d.get("channel_queries"), 8),
            "known_channels": _usernames(d.get("known_channels")), "search_queries": sq, "type": t}


# ================= التنفيذ بحدود الصلاحيات =================
def discover_many(queries, exclude=(), n=MAX_CHANNELS):
    """قنوات عامة من عدة عبارات بحث (بالاسم)، الأكبر مشتركين أولًا، بلا اشتراك."""
    async def go():
        from telethon import functions
        c = await A.client()
        out, seen = [], set(exclude)
        for qq in queries[:8]:
            if len(out) >= n * 2:
                break
            r = await A.call(lambda qq=qq: c(functions.contacts.SearchRequest(q=qq, limit=20)))
            for ch in r.chats:
                if ch.id in seen or not getattr(ch, "broadcast", False) or not getattr(ch, "username", None):
                    continue
                seen.add(ch.id)
                out.append({"id": ch.id, "name": ch.title, "username": ch.username, "count": getattr(ch, "participants_count", 0) or 0})
        return out

    res = A.run(go(), 300)
    res.sort(key=lambda x: -x["count"])
    return res[:n]


def verify_known(usernames):
    """يتحقق من القنوات التي ذكرها النموذج: تبقى الموجودة العامة فقط."""
    async def go():
        c = await A.client()
        out = []
        for u in usernames:
            try:
                ent = await A.call(lambda u=u: c.get_entity(u))
            except ValueError:
                raise
            except Exception:
                continue
            if getattr(ent, "broadcast", False) and getattr(ent, "username", None):
                out.append({"id": ent.id, "name": ent.title, "username": ent.username, "count": getattr(ent, "participants_count", 0) or 0})
        return out
    return A.run(go(), 120) if usernames else []


def execute(plan, brief, progress=None, exclude=()):
    """ينفّذ الخطة: يكتشف ويتحقق ويبحث ويرتّب. يعيد {items, counts, libs, queries}."""
    known = verify_known(plan["known_channels"])
    found = discover_many(plan["channel_queries"] or [brief[:40]], exclude=set(exclude) | {k["id"] for k in known})
    chans = (known + found)[:MAX_CHANNELS]
    if not chans:
        raise ValueError("لم أجد قنوات عامة مناسبة بهذه الخطة.")
    libs = [{"id": x["id"], "name": x["name"], "username": x["username"], "list": "tmp", "on": True, "count": x["count"]} for x in chans]
    for l in libs:
        A.TMP_LIBS[l["id"]] = l
    items, seen = [], set()
    qs = plan["search_queries"][:MAX_QUERIES]
    for qi, q in enumerate(qs):
        def prog(i, n, name, qi=qi):
            if progress:
                progress(qi, len(qs), i, n, name)
        r = A.search(q, type_=plan["type"], per_lib=10, libs_override=libs, progress=prog, expand=False)
        for it in r["items"]:
            if it["ref"] not in seen:
                seen.add(it["ref"])
                items.append(it)
        if len(items) >= 40:
            break
    items = rank(items, qs)
    counts = {k: sum(1 for i in items if i["t"] == k) for k in A.TYPES if k != "all"}
    counts["all"] = len(items)
    return {"items": items, "counts": counts, "libs": libs, "queries": qs}


def rank(items, queries):
    """الأقرب لأي صيغة من صيغ البحث أولًا، ثم المشاهدات."""
    scored = []
    for it in items:
        sc = max((A.fuzzy_score(it, q) for q in queries), default=0.0)
        if sc >= 0.5:
            scored.append((sc, it))
    scored.sort(key=lambda x: (-round(x[0], 1), -int(x[1].get("views", 0) or 0)))
    return [i for _, i in scored]


# ================= الحوار في البوت =================
def _AB():
    import telegram_account_bot as AB
    return AB


def _fmt_ctx(st):
    lines = ["طلب المستخدم (رؤوس أقلام):", st["brief"]]
    if st.get("ans"):
        lines.append("إجابات المستخدم على أسئلتك:")
        lines += [f"- {q} → {a}" for q, a in st["ans"]]
    return "\n".join(lines)


def start(chat):
    AB = _AB()
    SM.pop(chat, None)
    AB.AWAIT[chat] = "smart_brief"
    AB.TL.send("🧠 الموظف الذكي\nأعطني رؤوس أقلام: ماذا تريد؟ اكتب كل ما يخطر لك في رسالة واحدة (مؤلف، عنوان، لغة، نوع…). سأسألك فقط عمّا يلزم ثم أبدأ البحث بنفسي في القنوات العامة.", chat, kb=[AB.HOME])


def pending(chat, what, text):
    AB = _AB()
    if what == "smart_brief":
        brief = text.strip()[:600]
        SM[chat] = {"brief": brief, "qs": [], "ans": [], "i": 0, "tried": []}
        threading.Thread(target=_intake, args=(chat,), daemon=True).start()
        return True
    if what == "smart_ans":
        _answer(chat, text.strip()[:200])
        return True
    return False


def _intake(chat):
    AB = _AB()
    st = SM[chat]
    note = AB.TL.send("أقرأ طلبك وأفكّر فيما أحتاج أن أسألك عنه…", chat)
    st["note"] = note
    try:
        d = clean_intake(parse_json(llm(INTAKE_PROMPT + st["brief"])))
    except Exception as e:
        AB.TL.edit(chat, note, "تعذّر فهم طلبك الآن (" + str(e)[:80] + ").", [[AB._b("بحث بسيط بنصّي", "ta:ss", "primary")], AB.HOME])
        return
    st["qs"], st["understood"] = d["questions"], d["understood"]
    if not d["questions"]:
        AB.TL.edit(chat, note, f"فهمتُ: {d['understood']}\nلا أحتاج أسئلة، سأبدأ.", [])
        _plan_and_run(chat)
    else:
        AB.TL.edit(chat, note, f"فهمتُ: {d['understood']}\nعندي {len(d['questions'])} أسئلة قصيرة.", [])
        _ask_next(chat)


def _ask_next(chat):
    AB = _AB()
    st = SM[chat]
    i = st["i"]
    q = st["qs"][i]
    kb = [[AB._b(o, f"ta:sa:{k}")] for k, o in enumerate(q["options"])]
    kb.append([AB._b("ابدأ الآن بما عندك", "ta:sg", "success")])
    AB.AWAIT[chat] = "smart_ans"
    AB.TL.send(f"سؤال {i + 1} من {len(st['qs'])}: {q['q']}\n(اختر زرًّا أو اكتب إجابتك)", chat, kb=kb)


def _answer(chat, text):
    AB = _AB()
    st = SM.get(chat)
    if not st or st["i"] >= len(st["qs"]):
        return
    st["ans"].append((st["qs"][st["i"]]["q"], text))
    st["i"] += 1
    if st["i"] < len(st["qs"]):
        _ask_next(chat)
    else:
        AB.AWAIT.pop(chat, None)
        threading.Thread(target=_plan_and_run, args=(chat,), daemon=True).start()


def _plan_and_run(chat, refine=False):
    AB = _AB()
    st = SM[chat]
    AB.AWAIT.pop(chat, None)
    note = AB.TL.send("أضع خطة البحث: أي قنوات، وبأي صيغ وإملاءات…", chat)
    try:
        ctx = _fmt_ctx(st)
        if refine:
            ctx += "\nالخطة السابقة: " + json.dumps(st["plan"], ensure_ascii=False) + "\nقنوات بُحث فيها: " + "، ".join(l["name"][:30] for l in st.get("libs", [])[:30])
        plan = clean_plan(parse_json(llm((REFINE_PROMPT if refine else PLAN_PROMPT) + ctx)), st["brief"])
    except Exception as e:
        AB.TL.edit(chat, note, "تعذّر وضع الخطة (" + str(e)[:80] + ").", [[AB._b("بحث بسيط بنصّي", "ta:ss", "primary")], AB.HOME])
        return
    st["plan"] = plan
    head = "خطتي: " + (plan["summary"] or "بحث متعدد الصيغ") + "\nصيغ البحث: " + " | ".join(plan["search_queries"])
    last = [0.0]

    def prog(qi, nq, i, n, name):
        if time.time() - last[0] > 5:
            last[0] = time.time()
            AB.TL.edit(chat, note, f"{head}\n\nأبحث… صيغة {qi + 1}/{nq}، قناة {i}/{n}: {name[:30]}", [])
    AB.TL.edit(chat, note, head + "\n\nأكتشف القنوات وأتحقق منها…", [])
    try:
        r = execute(plan, st["brief"], progress=prog, exclude=[l["id"] for l in st.get("libs", [])] if refine else ())
    except Exception as e:
        AB.TL.edit(chat, note, head + "\n\nتوقف البحث: " + str(e)[:100], [[AB._b("🔄 أعد بخطة جديدة", "ta:sr", "success")], AB.HOME])
        return
    old = AB.RES.get(chat) if refine else None
    items = rank((old["items"] if old else []) + r["items"], plan["search_queries"] + ([] if not old else st.get("queries", []))) if old else r["items"]
    libs = (st.get("libs", []) if refine else []) + r["libs"]
    st["libs"], st["queries"] = libs, (st.get("queries", []) if refine else []) + r["queries"]
    counts = {k: sum(1 for i in items if i["t"] == k) for k in A.TYPES if k != "all"}
    counts["all"] = len(items)
    AB.RES[chat] = {"q": st["brief"][:40], "items": items, "counts": counts,
                    "scoped": {"topic": st["brief"][:20], "libs": libs, "discovered": True, "smart": True}}
    AB.TL.edit(chat, note, head + f"\nبحثتُ في {len(libs)} قناة عامة دون اشتراك.", [])
    AB.TL.send(*AB.screen_results(chat)[:1], chat, kb=AB.screen_results(chat)[1])


def on_cb(chat, act, arg):
    AB = _AB()
    if act == "sm":
        start(chat)
    elif act == "sa":
        st = SM.get(chat)
        if st and st["i"] < len(st["qs"]) and arg.isdigit() and int(arg) < len(st["qs"][st["i"]]["options"]):
            _answer(chat, st["qs"][st["i"]]["options"][int(arg)])
    elif act == "sg":
        if chat in SM:
            threading.Thread(target=_plan_and_run, args=(chat,), daemon=True).start()
    elif act == "sr":
        if chat in SM and SM[chat].get("plan"):
            threading.Thread(target=_plan_and_run, args=(chat, True), daemon=True).start()
    elif act == "ss":
        st = SM.get(chat)
        if st:
            AB.do_search(chat, st["brief"][:60], topic="كتب")
