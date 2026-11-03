"""تصدير جولة من «مجلس الوكلاء» إلى Markdown أو Word أو PDF (الإجابات كاملة مع حكم الوكيل الرئيسي)."""
import html
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
EXTRA_SCRIPTS = Path.home() / ".opencode" / "scripts"
OUT_DIR = Path.home() / "Downloads"


def to_markdown(rd, names):
    """نص Markdown للجولة: السؤال ← حكم الرئيسي ← إجابة كل وكيل كاملة."""
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(rd.get("created") or time.time()))
    out = ["# مجلس الوكلاء", "", f"**التاريخ:** {when}", "", "## السؤال", "", rd["question"].strip(), ""]
    ev = rd.get("eval") or {}
    if rd.get("main") and ev.get("answer"):
        out += [f"## حكم الوكيل الرئيسي ({names.get(rd['main'], rd['main'])})", "", ev["answer"].strip(), ""]
    out += ["## الإجابات كاملة", ""]
    for i in rd["delegates"]:
        e = rd["agents"].get(i, {})
        out += [f"### {names.get(i, i)}", "", (e.get("answer") or "").strip() or f"_لم تصل إجابة ({e.get('state')})_", ""]
    return "\n".join(out)


def _inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


def to_html(md):
    body, lst = [], False
    for ln in md.splitlines():
        m = re.match(r"^(#{1,4})\s+(.*)", ln)
        b = re.match(r"^\s*[-*•]\s+(.*)", ln) or re.match(r"^\s*\d+[.)]\s+(.*)", ln)
        if lst and not b:
            body.append("</ul>"); lst = False
        if m:
            body.append(f"<h{len(m.group(1))}>{_inline(m.group(2))}</h{len(m.group(1))}>")
        elif b:
            if not lst:
                body.append("<ul>"); lst = True
            body.append(f"<li>{_inline(b.group(1))}</li>")
        elif ln.strip():
            body.append(f"<p>{_inline(ln)}</p>")
    if lst:
        body.append("</ul>")
    css = ("body{font-family:'Geeza Pro','Helvetica Neue',sans-serif;line-height:1.9;margin:0;font-size:13pt}"
           "h1{font-size:24pt;border-bottom:3px solid #2563eb;padding-bottom:6px}h2{font-size:18pt;color:#1d4ed8;margin-top:26px}"
           "h3{font-size:15pt;background:#eff6ff;padding:6px 10px;border-right:4px solid #2563eb;margin-top:20px}"
           "code{background:#f1f5f9;padding:0 4px}")
    return f'<!doctype html><html dir="rtl" lang="ar"><meta charset="utf-8"><style>{css}</style><body>{"".join(body)}</body></html>'


def _docx(md, path):
    sys.path.insert(0, str(EXTRA_SCRIPTS))
    try:
        from arabic_docx import ArabicDoc
    except ImportError:
        raise ValueError("تصدير Word يحتاج python-docx وملف arabic_docx على هذا الجهاز.")
    d = ArabicDoc()
    for ln in md.splitlines():
        m = re.match(r"^(#{1,4})\s+(.*)", ln)
        if m:
            d.add_heading(m.group(2), level=min(len(m.group(1)), 3))
        elif ln.strip():
            d.add_para(re.sub(r"\*\*(.+?)\*\*", r"\1", ln).replace("`", ""))
    d.save(str(path))


def _pdf(md, path):
    if not Path(CHROME).exists():
        raise ValueError("تصدير PDF يحتاج متصفح Chrome على هذا الجهاز.")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "c.html"
        src.write_text(to_html(md), encoding="utf-8")
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={path}", src.as_uri()],
                           capture_output=True, text=True, timeout=60)
    if not Path(path).exists():
        raise ValueError("تعذّر إنشاء PDF.")


def export(rd, names, fmt):
    if fmt not in ("md", "docx", "pdf"):
        raise ValueError("الصيغة غير معروفة.")
    md = to_markdown(rd, names)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"مجلس-الوكلاء-{time.strftime('%Y%m%d-%H%M%S')}.{fmt}"
    if fmt == "md":
        path.write_text(md, encoding="utf-8")
    elif fmt == "docx":
        _docx(md, path)
    else:
        _pdf(md, path)
    return str(path)
