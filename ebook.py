"""كتب إلكترونية عبر Calibre: غلاف للمعاينة وتحويل تلقائي إلى صيغة كيندل."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

APP = "/Applications/calibre.app/Contents/MacOS"
EXTS = {".azw", ".azw3", ".azw4", ".mobi", ".prc", ".kfx", ".epub", ".fb2", ".lit", ".cbz", ".djvu"}
# ما يقبله الكيندل كما هو؛ الباقي يُحوَّل إلى azw3 عند النسخ إلى قرص كيندل
KINDLE_NATIVE = {".azw", ".azw3", ".azw4", ".mobi", ".prc", ".kfx", ".pdf", ".txt", ".doc", ".docx", ".html", ".htm", ".rtf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".sdr", ".mp3", ".m4a", ".aax"}
CONVERTIBLE = {".epub", ".fb2", ".lit", ".cbz", ".odt", ".rtf", ".md", ".htmlz", ".txtz", ".fbz"}


def tool(name):
    p = os.path.join(APP, name)
    return p if os.path.exists(p) else None


def available():
    return tool("ebook-convert") is not None


def is_kindle_root(root):
    return "kindle" in str(root or "").lower()


def needs_convert(path):
    return os.path.splitext(path)[1].lower() in CONVERTIBLE and available()


def convert(src, dst_dir, check=lambda: None):
    """يحوّل src إلى azw3 داخل dst_dir ويعيد مسار الناتج."""
    out = Path(dst_dir) / (Path(src).stem + ".azw3")
    p = subprocess.Popen([tool("ebook-convert"), str(src), str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        while p.poll() is None:
            check()
            try:
                p.wait(1)
            except subprocess.TimeoutExpired:
                pass
    except BaseException:
        p.kill(); out.unlink(missing_ok=True)
        raise
    if p.returncode != 0 or not out.exists():
        raise ValueError("تعذّر تحويل الكتاب: " + (p.stderr.read() or "")[-200:].strip())
    return out


def cover(path, dest):
    """يستخرج غلاف الكتاب إلى dest (jpg). يعيد True عند النجاح."""
    meta = tool("ebook-meta")
    if not meta:
        return False
    try:
        subprocess.run([meta, str(path), f"--get-cover={dest}"], capture_output=True, timeout=60)
    except Exception:
        return False
    return os.path.exists(dest) and os.path.getsize(dest) > 0


def info(path):
    meta = tool("ebook-meta")
    out = {}
    if meta:
        try:
            for line in subprocess.run([meta, str(path)], capture_output=True, text=True, timeout=30).stdout.splitlines():
                k, _, v = line.partition(":")
                if v.strip() and k.strip() in ("Title", "Author(s)", "Languages", "Publisher"):
                    out[k.strip()] = v.strip()
        except Exception:
            pass
    return out


# ---------- اقتراح أسماء الكتب: من بيانات الكتاب نفسه، وإلا تنظيف الاسم الحالي ----------
import re as _re

PROTECTED = _re.compile(r"^(my clippings\.txt|fontcal\.azw3?|.*-jb\.azw3?|update.*\.bin)$", _re.I)
_BIDI = _re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]")

BOOK_EXT = EXTS | {".pdf", ".djvu", ".cbr", ".doc", ".docx", ".rtf"}

_JUNK = [r"noor[\s\-_]*book(\.com)?", r"www\.[\w\-.]+", r"[\w\-]+\.(com|net|org|info)\b", r"\(?z[\-\s]?lib(\.org)?\)?", r"\blibgen\b",
         r"\bkutub[\-_]?pdf\w*", r"_?archive\b", r"\bpdf\s*books?\b", r"\bebook\b", r"\[[^\]]{0,40}\]", r"\bcopy\b", r"نسخة\s*\d*"]
_BAD_TITLE = _re.compile(r"^(unknown|untitled|microsoft word|document\d*|book\d*|بدون عنوان)$|^[\d\W_]+$", _re.I)  # أو تاريخ/أرقام فقط


def _unhex(t):
    """عناوين PDF المرمّزة سداسيًّا (من Word القديم بالعربية): تُفكّ إلى نصها."""
    h = (t or "").strip().strip("<>")
    if _re.fullmatch(r"(?:[0-9A-Fa-f]{2}){8,}", h):
        b = bytes.fromhex(h)
        if b[:2] in (b"\xfe\xff", b"\xff\xfe"):
            return b.decode("utf-16")
        for enc in ("utf-8", "cp1256"):
            try:
                return b.decode(enc)
            except Exception:
                pass
    return t


def _clean(t):
    t = _BIDI.sub("", _unhex(t or ""))
    t = _re.sub(r"^microsoft\s+word\s*-\s*", "", t, flags=_re.I)
    t = _re.sub(r"\.(docx?|rtf|odt|pages)$", "", t, flags=_re.I)
    t = _re.sub(r"[\\/:*?\"<>|\x00-\x1f]", " ", t or "")
    for j in _JUNK:
        t = _re.sub(j, " ", t, flags=_re.I)
    t = _re.sub(r"[_]+", " ", t)
    t = _re.sub(r"(?<=\D)[\s\-]+\d{2,}$", "", t)  # أرقام لاحقة عشوائية: «الكتاب_831»
    t = _re.sub(r"\s*-\s*-+\s*", " - ", t)
    t = _re.sub(r"\s{2,}", " ", t).strip(" -.,_")
    return t[:150].strip()


def suggest(path, name):
    """{title, author, source, suggested} لملف كتاب محلي."""
    stem, ext = os.path.splitext(name)
    if name.startswith("._") or name.startswith("."):
        return {"skip": "ملف نظام مخفي"}
    if ext.lower() not in BOOK_EXT:
        return {"skip": "ليس كتابًا"}
    if PROTECTED.match(name):
        return {"skip": "ملف نظام للكيندل — لا يُسمّى"}
    meta = info(path) if available() and os.path.splitext(name)[1].lower() in BOOK_EXT else {}
    title = _clean(meta.get("Title", ""))
    authors = [a.strip() for a in _re.split(r"&|;|،|,", meta.get("Author(s)", "")) if a.strip()]
    author = _clean(_re.sub(r"\s*\[[^\]]*\]", "", authors[0])) if authors else ""
    if (_BAD_TITLE.search(author or "x") or author.lower() in ("unknown", "مجهول", "admin", "user", "owner")
            or _re.search(r"[@\d]|www|http|\.com", author)
            or (ext.lower() == ".pdf" and _re.fullmatch(r"[a-z][a-z0-9_.\-]*", author))):  # PDF: اسم حساب من صنع الملف لا مؤلف
        author = ""
    src = "meta"
    if not title or _BAD_TITLE.search(title) or len(title) < 2 or title.lower() == _clean(stem).lower():
        title, src, author = _clean(stem), "name", ""  # العنوان من اسم الملف: «المؤلف» في PDF غالبًا اسم جهاز من صنعه
    if author and author not in title:
        new = f"{title} - {author}"
    else:
        new = title
    new = (new or _clean(stem) or stem)[:180] + ext.lower()
    return {"title": title, "author": author, "source": src, "suggested": new}
