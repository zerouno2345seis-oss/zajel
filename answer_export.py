"""آخر سؤال وجوابه عند وكيل الطرفية ← مستند Word منسّق من اليمين، عنوانه السؤال مختصرًا واسم الوكيل.
المصدر سجلّ المحادثة الذي يحفظه الوكيل نفسه (Claude وCodex وHermes)، ففيه الجواب كاملًا؛
وإلا فنص الشاشة (Antigravity وغيره)، لأن بعض الوكلاء لا يُبقون على الشاشة إلا آخر الجواب."""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

HOME = Path.home()
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
FILLER = re.compile(r"^(?:(?:أريد|أريدك|اريد|أرجو|ارجو|من فضلك|لو سمحت)\s+(?:أن|ان)?\s*)?(?:تبحث|ابحث|اكتب|اشرح|لخص|لخّص|أعطني|اعطني|قل|حدثني|حدّثني)?\s*(?:لي)?\s*(?:عن|في)?\s*", re.U)


# ---------- المصادر ----------
def _read_jsonl(p):
    out = []
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def _text_of(content):
    """نص رسالة من صيغ المحتوى المختلفة (نص، أو قائمة أجزاء)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(c.get("text") or "") for c in content if isinstance(c, dict) and c.get("type") in ("text", "input_text", "output_text"))
    return ""


def _is_user_text(t):
    t = (t or "").strip()
    return bool(t) and not t.startswith("<") and "tool_use_id" not in t


def from_claude(cwd):
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(cwd or HOME))
    d = HOME / ".claude" / "projects" / slug
    files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []
    if not files:
        return None
    q, ans = "", []
    for r in _read_jsonl(files[0]):
        m = r.get("message") or {}
        if r.get("type") == "user" and not r.get("isMeta"):
            c = m.get("content")
            if isinstance(c, list) and any(isinstance(x, dict) and x.get("type") == "tool_result" for x in c):
                continue
            t = _text_of(c)
            if _is_user_text(t):
                q, ans = t.strip(), []
        elif r.get("type") == "assistant" and q:
            t = _text_of(m.get("content"))
            if t.strip():
                ans.append(t.strip())
    return (q, "\n\n".join(ans)) if q else None


def from_codex(cwd):
    root = HOME / ".codex" / "sessions"
    files = sorted(root.rglob("rollout-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:6] if root.is_dir() else []
    for f in files:
        rows = _read_jsonl(f)
        meta = next((r.get("payload") or {} for r in rows if r.get("type") == "session_meta"), {})
        if cwd and meta.get("cwd") and Path(meta["cwd"]) != Path(cwd) and f is not files[0]:
            continue
        q, ans = "", []
        for r in rows:
            p = r.get("payload") or {}
            if r.get("type") != "response_item" or p.get("type") != "message":
                continue
            t = _text_of(p.get("content"))
            if p.get("role") == "user" and _is_user_text(t):
                q, ans = t.strip(), []
            elif p.get("role") == "assistant" and q and t.strip():
                ans.append(t.strip())
        if q:
            return q, "\n\n".join(ans)
    return None


def from_hermes(_cwd):
    db = HOME / ".hermes" / "state.db"
    if not db.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=3)
        sid = con.execute("select session_id from messages where role='user' order by timestamp desc limit 1").fetchone()
        if not sid:
            return None
        rows = con.execute("select role, content from messages where session_id=? order by id", (sid[0],)).fetchall()
        con.close()
    except sqlite3.Error:
        return None
    q, ans = "", []
    for role, content in rows:
        if role == "user" and _is_user_text(content):
            q, ans = content.strip(), []
        elif role == "assistant" and q and (content or "").strip():
            ans.append(content.strip())
    return (q, "\n\n".join(ans)) if q else None


SOURCES = {"claude": from_claude, "codex": from_codex, "hermes": from_hermes}

# ---------- الشاشة (احتياط) ----------
USER_MARK = {"agy": r"^> (?!\d+\. )", "hermes": r"^● ", "codex": r"^› ", "claude": r"^[>❯] "}
NOISE = re.compile(r"(esc to (cancel|interrupt)|\? for shortcuts|ctrl\+[a-z] |shift\+tab|tab agents|for agents|Worked for|weekly limit|context left|tokens|auto mode|Gemini \d|GPT-|nemotron|☤|⏵|Allow calling this tool|Navigate ·|^\s*\d\. (Yes|No)\b)", re.I)
TOOL = re.compile(r"^\s*(● (Ran|Explored|Listed|Messaged|Read|Edited|Wrote|Searched|Fetched)\b|┊|⎿|⏺ [A-Z][A-Za-z]+\()")
PENDING = re.compile(r"(Allow calling this tool|Do you want to|\(y/n\)|\[Y/n\]|esc to interrupt|still thinking|msg=interrupt)", re.I)
BORDER = re.compile(r"^[\s─━═│┃╭╮╰╯┌┐└┘╹▀▄█]+$")


def from_screen(agent_id, text):
    lines = [ANSI.sub("", ln).rstrip() for ln in (text or "").splitlines()]
    mark = re.compile(USER_MARK.get(agent_id, r"^[>❯›] "))
    idx = [k for k, ln in enumerate(lines) if mark.match(ln) and len(ln.strip()) > 3 and not re.match(r"^[>❯›]\s*(Ask|Try|Research)\b", ln.strip())]
    if not idx:
        return None
    k = idx[-1]
    q = [re.sub(r"^[>❯›●]\s*", "", lines[k])]
    j = k + 1
    # تكملة السؤال: أسطر بمسافتين في أولها، وعند Hermes كل ما قبل الخط الفاصل
    while j < len(lines) and lines[j].strip() and not BORDER.match(lines[j]) and (lines[j].startswith("  ") or agent_id == "hermes"):
        q.append(lines[j].strip())
        j += 1
    if any(PENDING.search(ln) for ln in lines[j:]):
        return " ".join(q).strip(), ""        # الوكيل ينتظر موافقة أو ما زال يعمل: لا جواب بعد
    ans = []
    for ln in lines[j:]:
        s = re.sub(r"^\s*[│┃]\s?|\s?[│┃]\s*$", "", ln)
        if BORDER.match(s or " ") or NOISE.search(s) or TOOL.match(s):
            continue
        if re.match(r"^\s*[>❯›]\s*$", s) or mark.match(s):
            break       # سطر الكتابة التالي (فارغ أو فيه اقتراح الوكيل) نهاية الجواب
        ans.append(re.sub(r"^\s{0,2}[⏺●•]\s", "", s))
    a = "\n".join(ans).strip()
    return " ".join(q).strip(), (a if len(a) >= 40 else "")


def last_exchange(agent_id, text="", cwd=""):
    src = SOURCES.get(agent_id)
    r = src(cwd) if src else None
    if r and r[0] and r[1]:
        return r
    return from_screen(agent_id, text) or ("", "")


# ---------- العنوان ----------
def short_title(question, agent_name):
    q = re.sub(r"\s+", " ", question or "").strip()
    q = re.split(r"[\n،,.؟?!:؛]", q)[0].strip() or q
    q2 = FILLER.sub("", q).strip()
    words = (q2 or q).split()[:7]
    t = " ".join(words)[:60].strip(" -—،,")
    return (t + " " + agent_name).strip() if t else agent_name


# ---------- Word ----------
def _rtl(paragraph):
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    ppr = paragraph._p.get_or_add_pPr()
    b = OxmlElement("w:bidi")
    ppr.insert(0, b)
    for run in paragraph.runs:
        rpr = run._r.get_or_add_rPr()
        rpr.append(OxmlElement("w:rtl"))


def _font(run, name="Geeza Pro", size=14, bold=None, color=None):
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    run.font.name = name
    run._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:cs"), name)
    run.font.size = Pt(size)
    run._r.get_or_add_rPr().append(_szcs(size))
    if bold is not None:
        run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def _szcs(size):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    e = OxmlElement("w:szCs")
    e.set(qn("w:val"), str(int(size * 2)))
    return e


def _shade(paragraph, fill):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), fill)
    paragraph._p.get_or_add_pPr().append(sh)


def _latin(s):
    return not re.search(r"[\u0600-\u06FF]", s or "")


def _inline(par, text, size=14, base_bold=False):
    """**عريض** و`كود` داخل السطر."""
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            _font(par.add_run(part[2:-2]), size=size, bold=True)
        elif part.startswith("`") and part.endswith("`"):
            _font(par.add_run(part[1:-1]), name="Menlo", size=size - 3)
        else:
            _font(par.add_run(part), size=size, bold=base_bold or None)


def _para(doc, text, style=None, size=14, bold=False, ltr=False, color=None, center=False):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    p = doc.add_paragraph(style=style) if style else doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.4
    p.paragraph_format.space_after = Pt(6)
    _inline(p, text, size=size, base_bold=bold)
    if color:
        for r in p.runs:
            _font(r, size=size, bold=bold or None, color=color)
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif ltr:
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if not ltr:
        _rtl(p)
    return p


def _table(doc, rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows if not re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", r)]
    if not cells:
        return
    n = max(len(r) for r in cells)
    t = doc.add_table(rows=len(cells), cols=n)
    t.style = "Table Grid"
    from docx.oxml import OxmlElement
    t._tbl.tblPr.append(OxmlElement("w:bidiVisual"))
    for i, r in enumerate(cells):
        for j in range(n):
            cell = t.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            _inline(p, r[j] if j < len(r) else "", size=12, base_bold=(i == 0))
            _rtl(p)


def _body(doc, answer):
    lines = (answer or "").splitlines()
    i, buf = 0, []

    def flush():
        if buf:
            txt = " ".join(x.strip() for x in buf)
            _para(doc, txt, ltr=_latin(txt))
            buf.clear()
    while i < len(lines):
        ln = lines[i].rstrip()
        s = ln.strip()
        if s.startswith("```"):
            flush()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            p = _para(doc, "\n".join(code) or " ", size=11, ltr=True)
            for r in p.runs:
                _font(r, name="Menlo", size=10)
            _shade(p, "F2F5F9")
        elif s.startswith("|") and s.count("|") >= 2:
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            _table(doc, rows)
            continue
        elif re.match(r"^#{1,6}\s", s):
            flush()
            lvl = min(3, len(s.split()[0]))
            h = doc.add_heading(level=lvl)
            _inline(h, s.lstrip("#").strip(), size=17 - lvl, base_bold=True)
            for r in h.runs:
                _font(r, size=17 - lvl, bold=True, color="183478")
            _rtl(h)
        elif re.match(r"^([-•*·])\s+", s):
            flush()
            _para(doc, re.sub(r"^([-•*·])\s+", "", s), style="List Bullet")
        elif re.match(r"^\d+[.)]\s+", s):
            flush()
            _para(doc, re.sub(r"^\d+[.)]\s+", "", s), style="List Number")
        elif not s:
            flush()
        else:
            buf.append(s)
        i += 1
    flush()


def build_docx(title, question, answer, agent_name, out_path):
    from docx import Document
    from docx.shared import Cm, Pt
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(2.2))
    from docx.oxml import OxmlElement
    sec._sectPr.append(OxmlElement("w:bidi"))
    _para(doc, title, size=20, bold=True, color="183478", center=True)
    _para(doc, f"الوكيل: {agent_name} · التاريخ: {time.strftime('%Y-%m-%d %H:%M')}", size=10, color="6B7587", center=True)
    lab = _para(doc, "السؤال", size=12, bold=True, color="183478")
    _shade(lab, "F2F5F9")
    qp = _para(doc, question.strip(), size=13)
    _shade(qp, "F2F5F9")
    h = doc.add_heading(level=1)
    _font(h.add_run("الجواب"), size=16, bold=True, color="183478")
    _rtl(h)
    _body(doc, answer)
    fp = sec.footer.paragraphs[0]
    _font(fp.add_run(f"زاجل · {agent_name}"), size=9, color="8B95A7")
    _rtl(fp)
    doc.save(str(out_path))
    return out_path


def build_many(title, items, out_path):
    """مستند واحد فيه أجوبة عدة وكلاء: لكل وكيل عنوان باسمه، ثم سؤاله وجوابه."""
    from docx import Document
    from docx.shared import Cm
    from docx.oxml import OxmlElement
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(2.2))
    sec._sectPr.append(OxmlElement("w:bidi"))
    _para(doc, title, size=20, bold=True, color="183478", center=True)
    _para(doc, "الوكلاء: " + "، ".join(n for n, _, _ in items) + " · " + time.strftime("%Y-%m-%d %H:%M"), size=10, color="6B7587", center=True)
    same_q = len({q.strip() for _, q, _ in items}) == 1
    if same_q:
        lab = _para(doc, "السؤال", size=12, bold=True, color="183478")
        _shade(lab, "F2F5F9")
        _shade(_para(doc, items[0][1].strip(), size=13), "F2F5F9")
    for name, q, a in items:
        h = doc.add_heading(level=1)
        _font(h.add_run("جواب " + name), size=16, bold=True, color="183478")
        _rtl(h)
        if not same_q:
            _shade(_para(doc, q.strip(), size=12), "F2F5F9")
        _body(doc, a)
    fp = sec.footer.paragraphs[0]
    _font(fp.add_run("زاجل · " + "، ".join(n for n, _, _ in items)), size=9, color="8B95A7")
    _rtl(fp)
    doc.save(str(out_path))
    return out_path


def export_many(entries, out_dir=None):
    """entries: [(agent_id, agent_name, screen_text, cwd)]. يجمع ما اكتمل من أجوبة في ملف واحد ويذكر من لم يكتمل."""
    items, missing = [], []
    for aid, name, text, cwd in entries:
        q, a = last_exchange(aid, text, cwd)
        (items.append((name, q, a)) if q and a.strip() else missing.append(name))
    if not items:
        raise ValueError("لم يكتمل جواب أي وكيل من الوكلاء المعروضين بعد.")
    title = short_title(items[0][1], "").strip() + " — " + "، ".join(n for n, _, _ in items)
    out_dir = Path(out_dir or HOME / "Downloads")
    out_dir.mkdir(parents=True, exist_ok=True)
    base, n = _safe(title), 1
    path = out_dir / f"{base}.docx"
    while path.exists():
        n += 1
        path = out_dir / f"{base} ({n}).docx"
    build_many(title, items, path)
    return {"ok": True, "path": str(path), "title": title, "missing": missing}


def _safe(name):
    return re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", name).strip()[:90] or "جواب"


def export(agent_id, agent_name, text="", cwd="", out_dir=None):
    q, a = last_exchange(agent_id, text, cwd)
    if not q or not a.strip():
        raise ValueError("لم يكتمل جواب آخر سؤال عند هذا الوكيل بعد (ما زال يعمل أو ينتظر موافقتك)." if q else "لم أجد سؤالًا عند هذا الوكيل بعد.")
    title = short_title(q, agent_name)
    out_dir = Path(out_dir or HOME / "Downloads")
    out_dir.mkdir(parents=True, exist_ok=True)
    base, n = _safe(title), 1
    path = out_dir / f"{base}.docx"
    while path.exists():
        n += 1
        path = out_dir / f"{base} ({n}).docx"
    build_docx(title, q, a, agent_name, path)
    return {"ok": True, "path": str(path), "title": title}
