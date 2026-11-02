"""وحدة إدارة المرفقات والوسائط لمساعد زاجل:
- حفظ المرفقات المرفوعة وفحص أمانها
- قراءة محتوى مختلف أنواع الملفات (نصوص، مستندات، جداول، عروض، صور مع OCR، صوتيات وفيديوهات)
- التفريغ الصوتي عبر faster-whisper في بيئة منفصلة مع تخزين مؤقت (Cache)
- تحويل صيغ الوسائط والمستندات (مع دعم الوثائق العربية في docx)
- البحث في محتوى الوسائط مع تطبيع للنصوص العربية
"""
from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

# استيراد محتمل لوحدة الوثائق العربية
OPENCODE_SCRIPTS = str(Path.home() / ".opencode" / "scripts")
if OPENCODE_SCRIPTS not in sys.path:
    sys.path.append(OPENCODE_SCRIPTS)
try:
    from arabic_docx import ArabicDoc
except Exception:
    ArabicDoc = None

# الثوابت ومسارات العمل
DATA = None
UPLOAD_DIR = None
TRANSCRIPTS_DIR = None
CONVERTED_DIR = None
OCR_CACHE_FILE = None
OCR_CACHE = {}

JOBS = {}           # مهام التفريغ الصوتي: id -> {id, path, state, progress, result, error, started, txt_path, srt_path}
CONVERT_JOBS = {}   # مهام التحويل الطويلة: id -> {id, src, dst, state, progress, error, started}
LOCK = threading.RLock()

# تصنيف اللواحق
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp", ".tif", ".tiff", ".dng", ".svg", ".ico", ".jp2", ".avif", ".jfif", ".psd", ".pbm", ".ppm", ".pgm", ".tga", ".exr", ".cr2", ".nef", ".arw", ".raw"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".opus", ".amr", ".caf", ".aiff", ".wma", ".3gp", ".m4b", ".mid", ".midi", ".aif", ".mka", ".wv", ".ac3", ".dts", ".ra", ".spx"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".wmv", ".m4v", ".ts", ".mpg", ".mpeg", ".ogv", ".mts", ".m2ts", ".vob", ".f4v", ".3g2", ".asf"}
PDF_EXT = {".pdf"}
EBOOK_EXT = {".epub", ".mobi", ".azw3", ".azw", ".fb2", ".lit", ".djvu"}
ARCHIVE_EXT = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".apk", ".cbz", ".cbr"}
DOC_EXT = {".docx", ".odt", ".rtf", ".pages", ".doc", ".dot", ".dotx", ".docm", ".wpd", ".wps"} | EBOOK_EXT
SHEET_EXT = {".xlsx", ".csv", ".tsv", ".xls", ".ods", ".numbers", ".xlsm", ".xlsb", ".fods"}
SLIDES_EXT = {".pptx", ".ppt", ".odp", ".key", ".pptm", ".ppsx", ".pps"}
TEXT_EXT = {
    ".txt", ".md", ".json", ".html", ".xml", ".log", ".py", ".js", ".ts", ".css", ".sh",
    ".yaml", ".yml", ".ini", ".conf", ".toml", ".srt", ".vtt", ".c", ".cpp", ".h", ".java",
    ".swift", ".sql", ".rst", ".tex", ".zsh", ".bash", ".htm", ".jsonl", ".json5", ".vtt", ".ass", ".sub", ".org",
    ".adoc", ".latex", ".bib", ".rss", ".atom", ".plist", ".env", ".gradle", ".kt", ".go", ".rs", ".rb", ".php", ".cs", ".r",
    ".pl", ".lua", ".ps1", ".bat", ".textile"
}

EXTRA_PATH = [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".opencode/bin"), "/usr/bin", "/bin"]


def _env_path():
    return os.pathsep.join(EXTRA_PATH + [p for p in os.environ.get("PATH", "").split(os.pathsep) if p])


def _run_cmd(cmd, timeout=60, env=None, check=False):
    e = {"PATH": _env_path(), "HOME": str(Path.home()), "LANG": "en_US.UTF-8"} | (env or {})
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=e)
    if check and res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"Command failed: {cmd[0]}")
    return res.stdout


def _which(name):
    return shutil.which(name, path=_env_path())


def get_data_dir() -> Path:
    global DATA
    if DATA is not None:
        return DATA
    try:
        import agent_runner
        if agent_runner.DATA is not None:
            DATA = Path(agent_runner.DATA)
            return DATA
    except Exception:
        pass
    env_data = os.environ.get("PB_DATA")
    if env_data:
        DATA = Path(env_data)
        return DATA
    DATA = Path.home() / "Library" / "Application Support" / "Phone Backup"
    return DATA


def get_upload_dir() -> Path:
    global UPLOAD_DIR
    if UPLOAD_DIR is not None:
        return UPLOAD_DIR
    UPLOAD_DIR = get_data_dir() / "assistant_work" / "uploads"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def get_transcripts_dir() -> Path:
    global TRANSCRIPTS_DIR
    if TRANSCRIPTS_DIR is not None:
        return TRANSCRIPTS_DIR
    TRANSCRIPTS_DIR = get_data_dir() / "assistant_work" / "transcripts"
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    return TRANSCRIPTS_DIR


def get_converted_dir() -> Path:
    global CONVERTED_DIR
    if CONVERTED_DIR is not None:
        return CONVERTED_DIR
    CONVERTED_DIR = get_upload_dir() / "converted"
    CONVERTED_DIR.mkdir(parents=True, exist_ok=True)
    return CONVERTED_DIR


def _load_ocr_cache():
    global OCR_CACHE, OCR_CACHE_FILE
    if OCR_CACHE_FILE is None:
        OCR_CACHE_FILE = get_data_dir() / "assistant_work" / "ocr_cache.json"
    if OCR_CACHE_FILE.is_file():
        try:
            with open(OCR_CACHE_FILE, "r", encoding="utf-8") as f:
                OCR_CACHE = json.load(f)
        except Exception:
            OCR_CACHE = {}


def _save_ocr_cache():
    global OCR_CACHE, OCR_CACHE_FILE
    if OCR_CACHE_FILE is None:
        OCR_CACHE_FILE = get_data_dir() / "assistant_work" / "ocr_cache.json"
    try:
        OCR_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = OCR_CACHE_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(OCR_CACHE, f, ensure_ascii=False, indent=1)
        os.replace(tmp, OCR_CACHE_FILE)
    except Exception:
        pass


def init(data_dir):
    global DATA, UPLOAD_DIR, TRANSCRIPTS_DIR, CONVERTED_DIR, OCR_CACHE_FILE
    DATA = Path(data_dir)
    UPLOAD_DIR = DATA / "assistant_work" / "uploads"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR = DATA / "assistant_work" / "transcripts"
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    CONVERTED_DIR = UPLOAD_DIR / "converted"
    CONVERTED_DIR.mkdir(parents=True, exist_ok=True)
    OCR_CACHE_FILE = DATA / "assistant_work" / "ocr_cache.json"
    _load_ocr_cache()


# تهيئة المسارات الأولية
DATA = get_data_dir()
UPLOAD_DIR = get_upload_dir()
TRANSCRIPTS_DIR = get_transcripts_dir()
CONVERTED_DIR = get_converted_dir()
_load_ocr_cache()


# ---------- فحص وتحديد الأنواع ----------
def is_under_uploads(path) -> bool:
    """التحقق من أن مسارًا داخل uploads (resolve + حماية من الروابط)."""
    try:
        p = Path(path).resolve()
        up = Path(get_upload_dir()).resolve()
        return p == up or up in p.parents
    except Exception:
        return False


def _is_text_content(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(4096)
        if not chunk:
            return True
        if b"\x00" in chunk:
            return False
        for enc in ("utf-8", "utf-8-sig", "cp1256", "latin-1"):
            try:
                chunk.decode(enc)
                return True
            except UnicodeDecodeError:
                pass
    except Exception:
        pass
    return False


def kind_of(path) -> str:
    """تحديد نوع الملف:
    image / audio / video / pdf / doc / sheet / slides / text / other"""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in IMG_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    if ext in PDF_EXT:
        return "pdf"
    if ext in DOC_EXT:
        return "doc"
    if ext in SHEET_EXT:
        return "sheet"
    if ext in SLIDES_EXT:
        return "slides"
    if ext in ARCHIVE_EXT:
        return "archive"
    if ext in TEXT_EXT:
        return "text"
    if p.is_file() and _is_text_content(p):
        return "text"
    return "other"


def clean_filename(name: str) -> str:
    """تنظيف اسم الملف: منع فواصل المسارات ومسارات '..' والتحكم، مع إبقاء العربية واللاتينية."""
    n = posixpath.basename(str(name or "").replace("\\", "/")).strip()
    n = re.sub(r'[\x00-\x1f\x7f/\\:;*?"<>|]+', "", n)
    n = n.strip(". ")
    if not n:
        n = "upload.bin"
    return n


def get_unique_path(target_path: Path) -> Path:
    """ضمان عدم استبدال أي ملف بإضافة رقم تصاعدي."""
    p = Path(target_path)
    if not p.exists():
        return p
    stem = p.stem
    suffix = p.suffix
    parent = p.parent
    idx = 1
    while True:
        cand = parent / f"{stem}_{idx}{suffix}"
        if not cand.exists():
            return cand
        idx += 1


# ---------- حفظ الملفات المرفوعة ----------
def save_upload(stream_or_bytes, name: str, max_size: int | None = None) -> dict:
    """حفظ مرفق وارد:
    - ينظف الاسم مع إبقاء العربية
    - يحفظ في uploads/<YYYYMMDD>/<id8>-<name>
    - سقف 500MB (أو max_size محدد للاختبار)
    - لا يستبدل ملفًا أبدًا
    - يعيد {id, name, path, kind, size}
    """
    cleaned = clean_filename(name)
    limit = max_size if max_size is not None else int(os.environ.get("PB_MEDIA_MAX_UPLOAD") or (500 * 1024 * 1024))
    
    day_folder = time.strftime("%Y%m%d")
    target_dir = get_upload_dir() / day_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    id8 = uuid.uuid4().hex[:8]
    initial_target = target_dir / f"{id8}-{cleaned}"
    target = get_unique_path(initial_target)

    if isinstance(stream_or_bytes, (bytes, bytearray)):
        if len(stream_or_bytes) > limit:
            raise ValueError(f"حجم الملف يتجاوز الحد المسموح ({round(limit / (1024*1024))} ميغابايت).")
        with open(target, "wb") as f:
            f.write(stream_or_bytes)
        total_size = len(stream_or_bytes)
    else:
        # كائن تدفق (Stream) له دالة read
        total_size = 0
        try:
            with open(target, "wb") as f:
                while True:
                    chunk = stream_or_bytes.read(65536)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > limit:
                        raise ValueError(f"حجم الملف يتجاوز الحد المسموح ({round(limit / (1024*1024))} ميغابايت).")
                    f.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise

    k = kind_of(target)
    return {
        "id": id8,
        "name": cleaned,
        "path": str(target),
        "kind": k,
        "size": total_size
    }


# ---------- مفتاح الكاش والـ OCR ----------
def _file_hash_key(path: Path) -> str:
    p = Path(path).resolve()
    st = p.stat()
    raw = f"{p}_{st.st_size}_{int(st.st_mtime)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def ocr_image(path: Path) -> str:
    """استخراج النص من الصورة بـ tesseract مع حفظه بالكاش."""
    key = _file_hash_key(path)
    with LOCK:
        if key in OCR_CACHE:
            return OCR_CACHE[key]

    tmp_png = None
    target_img = path
    ext = path.suffix.lower()
    
    # تحويل heic/webp/tiff لصيغة يفهمها tesseract إن لزم
    if ext in (".heic", ".heif", ".webp"):
        tmp_dir = Path(tempfile.mkdtemp(prefix="pbocr_tmp_"))
        tmp_png = tmp_dir / "converted.png"
        sips_ok = False
        if _which("sips"):
            r = subprocess.run(["sips", "-s", "format", "png", str(path), "--out", str(tmp_png)], capture_output=True)
            sips_ok = r.returncode == 0 and tmp_png.exists()
        if not sips_ok and _which("ffmpeg"):
            subprocess.run(["ffmpeg", "-i", str(path), str(tmp_png), "-y"], capture_output=True)
        if tmp_png.exists():
            target_img = tmp_png

    text = ""
    if _which("tesseract"):
        # محاولة ara+eng أولاً ثم eng فقط
        try:
            out = _run_cmd(["tesseract", str(target_img), "stdout", "-l", "ara+eng"], timeout=60)
            text = out.strip()
        except Exception:
            try:
                out = _run_cmd(["tesseract", str(target_img), "stdout", "-l", "eng"], timeout=60)
                text = out.strip()
            except Exception:
                text = ""

    if tmp_png and tmp_png.parent.exists():
        shutil.rmtree(tmp_png.parent, ignore_errors=True)

    with LOCK:
        OCR_CACHE[key] = text
        _save_ocr_cache()

    return text


# ---------- قراءة مختلف أنواع الملفات ----------
def read_any(path, max_chars: int = 20000) -> dict:
    """قراءة محتوى أي ملف وإرجاع {kind, text, meta, truncated}."""
    p = Path(path).resolve()
    if not p.is_file():
        raise ValueError(f"الملف غير موجود: {p}")

    k = kind_of(p)
    text = ""
    meta = {}
    st = p.stat()
    meta["size_bytes"] = st.st_size

    if k == "text":
        data = p.read_bytes()
        detected_enc = "utf-8"
        for enc in ("utf-8", "utf-8-sig", "cp1256", "latin-1"):
            try:
                text = data.decode(enc)
                detected_enc = enc
                break
            except UnicodeDecodeError:
                pass
        meta["encoding"] = detected_enc

    elif k == "pdf":
        page_count = 0
        pdf_text = ""
        # 1. محاولة pdftotext
        pdftotext_bin = _which("pdftotext") or "/opt/homebrew/bin/pdftotext"
        if os.path.exists(pdftotext_bin):
            try:
                out = _run_cmd([pdftotext_bin, "-layout", str(p), "-"], timeout=30)
                pdf_text = out.strip()
                meta["engine"] = "pdftotext"
            except Exception:
                pdf_text = ""

        # 2. فحص النص، إن كان شبه فارغ نستعمل PyMuPDF fitz
        if len(pdf_text.strip()) < 30:
            try:
                import fitz
                doc = fitz.open(p)
                page_count = doc.page_count
                meta["page_count"] = page_count
                
                # فحص استخراج النص الداخلي أولاً
                fitz_texts = []
                for i in range(min(10, page_count)):
                    fitz_texts.append(doc[i].get_text())
                combined_fitz = "\n".join(fitz_texts).strip()
                
                if len(combined_fitz) >= 30:
                    pdf_text = combined_fitz
                    meta["engine"] = "fitz_text"
                else:
                    # تحويل أول 10 صفحات لصور وتطبيق OCR
                    ocr_pages = []
                    tmp_dir = Path(tempfile.mkdtemp(prefix="pbpdf_pix_"))
                    try:
                        for i in range(min(10, page_count)):
                            pix = doc[i].get_pixmap(dpi=150)
                            img_file = tmp_dir / f"p_{i+1}.png"
                            pix.save(str(img_file))
                            t = ocr_image(img_file)
                            if t.strip():
                                ocr_pages.append(f"--- صفحة {i+1} ---\n{t.strip()}")
                        pdf_text = "\n\n".join(ocr_pages)
                        meta["engine"] = "fitz_ocr"
                        meta["ocr_pages"] = min(10, page_count)
                    finally:
                        shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception as exc:
                if not pdf_text:
                    meta["error"] = str(exc)
        text = pdf_text

    elif k == "doc":
        ext = p.suffix.lower()
        if ext == ".docx":
            try:
                import docx
                doc = docx.Document(p)
                paras = [para.text for para in doc.paragraphs if para.text.strip()]
                tables = []
                for t in doc.tables:
                    for row in t.rows:
                        row_t = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                        if row_t:
                            tables.append(row_t)
                text = "\n".join(paras)
                if tables:
                    text += ("\n\n[الجداول:]\n" if text else "") + "\n".join(tables)
                meta["paragraphs"] = len(paras)
                meta["tables"] = len(doc.tables)
            except Exception:
                text = ""

        if not text:
            # تحويل بـ textutil (macOS)
            if _which("textutil"):
                try:
                    out = _run_cmd(["textutil", "-convert", "txt", str(p), "-stdout"], timeout=60)
                    text = out.strip()
                    meta["engine"] = "textutil"
                except Exception:
                    text = ""
        if not text and _which("soffice"):
            # تحويل بـ libreoffice
            tmp_dir = Path(tempfile.mkdtemp(prefix="pbsoffice_"))
            try:
                _run_cmd(["soffice", "--headless", "--convert-to", "txt:Text", str(p), "--outdir", str(tmp_dir)], timeout=60)
                gen_txt = tmp_dir / (p.stem + ".txt")
                if gen_txt.exists():
                    text = gen_txt.read_text(encoding="utf-8", errors="replace")
                    meta["engine"] = "soffice"
            except Exception:
                pass
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    elif k == "sheet":
        ext = p.suffix.lower()
        if ext in (".csv", ".tsv"):
            delim = "\t" if ext == ".tsv" else ","
            rows = []
            try:
                # محاولة اكتشاف الترميز
                raw = p.read_bytes()
                txt_content = ""
                for enc in ("utf-8", "utf-8-sig", "cp1256", "latin-1"):
                    try:
                        txt_content = raw.decode(enc)
                        break
                    except UnicodeDecodeError:
                        pass
                reader = csv.reader(txt_content.splitlines(), delimiter=delim)
                for idx, r in enumerate(reader):
                    if idx >= 200:
                        break
                    if any(r):
                        rows.append(" | ".join(r))
                text = "\n".join(rows)
                meta["rows_read"] = len(rows)
            except Exception as exc:
                meta["error"] = str(exc)
        else:
            # xlsx / ods
            used_openpyxl = False
            try:
                import openpyxl
                wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
                sheets_out = []
                total_r = 0
                for sname in wb.sheetnames:
                    ws = wb[sname]
                    srows = []
                    for r_idx, row in enumerate(ws.iter_rows(values_only=True)):
                        if r_idx >= 200:
                            break
                        cells = [str(c) if c is not None else "" for c in row]
                        if any(cells):
                            srows.append(" | ".join(cells))
                    if srows:
                        sheets_out.append(f"=== {sname} ===\n" + "\n".join(srows))
                        total_r += len(srows)
                text = "\n\n".join(sheets_out)
                meta["sheets"] = wb.sheetnames
                meta["rows_read"] = total_r
                used_openpyxl = True
            except Exception:
                pass

            if not used_openpyxl and _which("soffice"):
                tmp_dir = Path(tempfile.mkdtemp(prefix="pbsheet_"))
                try:
                    _run_cmd(["soffice", "--headless", "--convert-to", "csv", str(p), "--outdir", str(tmp_dir)], timeout=60)
                    gen_csv = tmp_dir / (p.stem + ".csv")
                    if gen_csv.exists():
                        text = gen_csv.read_text(encoding="utf-8", errors="replace")
                        meta["engine"] = "soffice_csv"
                except Exception:
                    pass
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)

    elif k == "slides":
        # استخراج نصوص الشرائح من pptx
        try:
            with zipfile.ZipFile(p, "r") as z:
                slide_names = [f for f in z.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", f)]
                slide_names.sort(key=lambda x: int(re.search(r"\d+", x).group()))
                all_slides = []
                for s_idx, sname in enumerate(slide_names, 1):
                    xml_bytes = z.read(sname)
                    tree = ET.fromstring(xml_bytes)
                    texts = [e.text for e in tree.iter() if e.tag.endswith("}t") and e.text]
                    if texts:
                        all_slides.append(f"--- شريحة {s_idx} ---\n" + "\n".join(texts))
                text = "\n\n".join(all_slides)
                meta["slides_count"] = len(slide_names)
        except Exception as exc:
            meta["error"] = str(exc)

    elif k == "image":
        # قراءة الأبعاد والبيانات الفوقية وتصنيف Vision
        if _which("mdls"):
            mdls_raw = _run_cmd(["mdls", "-name", "kMDItemContentCreationDate", "-name", "kMDItemPixelWidth", "-name", "kMDItemPixelHeight", "-name", "kMDItemAcquisitionModel", str(p)])
            for ln in mdls_raw.splitlines():
                if "=" in ln and "(null)" not in ln:
                    mk, mv = [x.strip() for x in ln.split("=", 1)]
                    mapping = {"kMDItemContentCreationDate": "taken", "kMDItemPixelWidth": "width", "kMDItemPixelHeight": "height", "kMDItemAcquisitionModel": "camera"}
                    if mk in mapping:
                        meta[mapping[mk]] = mv.strip('"')

        if "width" not in meta and _which("sips"):
            sips_raw = _run_cmd(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(p)])
            mw = re.search(r"pixelWidth:\s*(\d+)", sips_raw)
            mh = re.search(r"pixelHeight:\s*(\d+)", sips_raw)
            if mw: meta["width"] = int(mw.group(1))
            if mh: meta["height"] = int(mh.group(1))

        try:
            import vision
            if vision.available():
                van = vision.analyze([p]).get(str(p)) or {}
                if van:
                    labs = sorted((van.get("labels") or {}).items(), key=lambda kv: -kv[1])[:5]
                    meta["labels"] = [vk for vk, vv in labs if vv >= 0.35]
                    if van.get("screenshot"): meta["screenshot"] = True
                    if van.get("faces"): meta["faces"] = van["faces"]
        except Exception:
            pass

        text = ocr_image(p)
        meta["ocr"] = True

    elif k in ("audio", "video"):
        # استخراج المدة والوسوم بـ ffprobe
        if _which("ffprobe"):
            probe_out = _run_cmd(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(p)])
            try:
                pdata = json.loads(probe_out)
                fmt = pdata.get("format", {})
                if fmt.get("duration"):
                    meta["duration_sec"] = round(float(fmt["duration"]), 2)
                    meta["duration_min"] = round(float(fmt["duration"]) / 60, 2)
                tags = {tk.lower(): tv for tk, tv in (fmt.get("tags") or {}).items()}
                for ftag in ("title", "artist", "album", "date", "creation_time", "genre", "comment"):
                    if tags.get(ftag):
                        meta.setdefault("tags", {})[ftag] = str(tags[ftag])[:100]
            except Exception:
                pass

        # فحص الكاش للتفريغ الصوتي
        cached_t = get_transcript_cache(p)
        if cached_t:
            text = cached_t.get("text", "")
            meta["transcribed"] = True
            meta["language"] = cached_t.get("language")
        else:
            text = ""
            meta["transcribed"] = False
            meta["note"] = "التفريغ الصوتي غير متاح في الذاكرة المؤقتة؛ استعمل أداة transcribe_audio لتفريغ هذا الملف."

    if k == "archive":
        names = []
        try:
            import zipfile, tarfile
            if zipfile.is_zipfile(p):
                with zipfile.ZipFile(p) as zf:
                    names = zf.namelist()
            elif tarfile.is_tarfile(p):
                with tarfile.open(p) as tf:
                    names = tf.getnames()
            elif _which("7z"):
                names = _run_cmd(["7z", "l", "-ba", str(p)], timeout=60).splitlines()
            elif _which("bsdtar"):
                names = _run_cmd(["bsdtar", "-tf", str(p)], timeout=60).splitlines()
        except Exception as exc:
            meta["error"] = str(exc)
        meta["entries"] = len(names)
        text = "\n".join(names[:500])
    elif p.suffix.lower() in EBOOK_EXT and not text:
        tmpd = Path(tempfile.mkdtemp(prefix="pbebook_"))
        try:
            out_t = tmpd / "b.txt"
            if _which("ebook-convert"):
                subprocess.run(["ebook-convert", str(p), str(out_t)], capture_output=True, timeout=180)
            if not out_t.exists() and _which("pandoc") and p.suffix.lower() == ".epub":
                subprocess.run(["pandoc", str(p), "-t", "plain", "-o", str(out_t)], capture_output=True, timeout=120)
            if out_t.exists():
                text = out_t.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            meta["error"] = str(exc)
        finally:
            shutil.rmtree(tmpd, ignore_errors=True)
    elif k == "other" and not text:
        meta["file_type"] = _run_cmd(["file", "-b", str(p)], timeout=15).strip()[:200] if _which("file") else ""
        md = _run_cmd(["mdls", "-name", "kMDItemKind", "-name", "kMDItemContentType", str(p)], timeout=15) if _which("mdls") else ""
        if md.strip():
            meta["spotlight"] = md.strip()[:300]
        meta["note"] = "نوع غير معروف المحتوى؛ هذه معلوماته الوصفية فقط. يمكن تحويله إن كان له محوّل (list_conversions)."

    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = True

    return {
        "kind": k,
        "text": text,
        "meta": meta,
        "truncated": truncated
    }


# ---------- التفريغ الصوتي (Transcription) ----------
def get_transcript_cache(path: Path) -> dict | None:
    """استرجاع التفريغ الصوتي المخزن إن وجد للملف بالبصمة."""
    key = _file_hash_key(path)
    cf = get_transcripts_dir() / f"{key}.json"
    if cf.is_file():
        try:
            return json.loads(cf.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def get_media_python() -> str | None:
    """مسار بايثون في بيئة media_env المنفصلة."""
    candidates = [
        get_data_dir() / "media_env" / "bin" / "python",
        get_data_dir() / "media_env" / "bin" / "python3",
        Path.home() / "Library" / "Application Support" / "Phone Backup" / "media_env" / "bin" / "python",
        Path.home() / "Library" / "Application Support" / "Phone Backup" / "media_env" / "bin" / "python3",
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


def _format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _make_srt(segments: list) -> str:
    lines = []
    for i, s in enumerate(segments, 1):
        st = _format_srt_time(s.get("start", 0))
        en = _format_srt_time(s.get("end", 0))
        lines.append(f"{i}\n{st} --> {en}\n{s.get('text', '').strip()}\n")
    return "\n".join(lines)


def transcribe(path, lang: str | None = None, model: str = "small", wait_seconds: int = 0) -> dict:
    """بدء أو استرجاع تفريغ صوتي بمحرك faster-whisper.
    يعيد {error: ...} إن لم تكن البيئة مثبتة دون رمي استثناء."""
    p = Path(path).resolve()
    if not p.is_file():
        return {"error": "الملف غير موجود.", "hint": str(p)}

    # فحص الكاش أولاً
    cached = get_transcript_cache(p)
    key = _file_hash_key(p)
    txt_file = get_transcripts_dir() / f"{key}.txt"
    srt_file = get_transcripts_dir() / f"{key}.srt"
    if cached:
        return {
            "id": "cached",
            "state": "done",
            "language": cached.get("language"),
            "duration": cached.get("duration"),
            "segments": cached.get("segments", []),
            "text": cached.get("text", ""),
            "txt_path": str(txt_file) if txt_file.exists() else None,
            "srt_path": str(srt_file) if srt_file.exists() else None,
            "cached": True
        }

    py_bin = get_media_python()
    if not py_bin:
        return {
            "error": "محرّك التفريغ غير مثبّت",
            "hint": "تأكد من إنشاء بيئة media_env وتثبيت faster-whisper في ~/Library/Application Support/Phone Backup/media_env"
        }

    job_id = uuid.uuid4().hex[:10]
    job = {
        "id": job_id,
        "path": str(p),
        "state": "running",
        "progress": 0,
        "result": None,
        "error": None,
        "started": time.time(),
        "txt_path": None,
        "srt_path": None,
    }
    with LOCK:
        JOBS[job_id] = job

    def worker():
        tmp_dir = Path(tempfile.mkdtemp(prefix="pbtranscribe_"))
        try:
            audio_target = p
            # إذا كان فيديو، استخرج الصوت بـ ffmpeg إلى wav مؤقت 16k mono
            k = kind_of(p)
            if k == "video" or p.suffix.lower() not in (".wav", ".mp3"):
                extracted_wav = tmp_dir / "extracted.wav"
                if _which("ffmpeg"):
                    cmd = ["ffmpeg", "-i", str(p), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(extracted_wav), "-y"]
                    res = subprocess.run(cmd, capture_output=True)
                    if res.returncode == 0 and extracted_wav.exists():
                        audio_target = extracted_wav

            worker_script = Path(__file__).resolve().parent / "media_transcribe_worker.py"
            args = [py_bin, str(worker_script), str(audio_target), "--model", model]
            if lang:
                args += ["--lang", lang]

            proc = subprocess.run(args, capture_output=True, text=True, timeout=1200)
            if proc.returncode != 0:
                job["state"] = "error"
                job["error"] = proc.stderr.strip() or "فشل تفريغ الصوت."
                return

            try:
                res_data = json.loads(proc.stdout)
            except Exception:
                job["state"] = "error"
                job["error"] = "خطأ في قراءة ناتج التفريغ الصوتي."
                return

            # حفظ الكاش
            json_file = get_transcripts_dir() / f"{key}.json"
            json_file.write_text(json.dumps(res_data, ensure_ascii=False, indent=1), encoding="utf-8")
            
            txt_file.write_text(res_data.get("text", ""), encoding="utf-8")
            srt_content = _make_srt(res_data.get("segments", []))
            srt_file.write_text(srt_content, encoding="utf-8")

            job["state"] = "done"
            job["result"] = res_data
            job["txt_path"] = str(txt_file)
            job["srt_path"] = str(srt_file)
        except Exception as exc:
            job["state"] = "error"
            job["error"] = str(exc)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    if wait_seconds > 0:
        t.join(timeout=wait_seconds)
        if job["state"] == "done":
            res = dict(job["result"])
            res.update({
                "id": job_id,
                "state": "done",
                "txt_path": job["txt_path"],
                "srt_path": job["srt_path"]
            })
            return res
        if job["state"] == "error":
            return {"id": job_id, "state": "error", "error": job["error"]}

    return {
        "id": job_id,
        "state": "running",
        "progress": 0,
        "note": "التفريغ الصوتي يعمل في الخلفية؛ استعلم عن حالته بأداة transcribe_status."
    }


def transcribe_status(job_id: str, seconds: int = 5) -> dict:
    """الاستعلام عن حالة مهمة تفريغ صوتي والانتظار حتى seconds ثوانٍ."""
    job = JOBS.get(job_id)
    if not job:
        return {"error": "معرّف المهمة غير موجود."}
    
    if job["state"] == "running" and seconds > 0:
        end = time.time() + seconds
        while time.time() < end and job["state"] == "running":
            time.sleep(0.5)

    if job["state"] == "done":
        res = dict(job["result"] or {})
        res.update({
            "id": job_id,
            "state": "done",
            "txt_path": job["txt_path"],
            "srt_path": job["srt_path"]
        })
        return res
    if job["state"] == "error":
        return {"id": job_id, "state": "error", "error": job["error"]}
    return {
        "id": job_id,
        "state": "running",
        "elapsed_sec": round(time.time() - job["started"], 1)
    }


# ---------- التحويل بين الصيغ (Conversion) ----------
def supported_conversions() -> dict:
    img = sorted(e.lstrip(".") for e in IMG_EXT)
    av = sorted(e.lstrip(".") for e in (AUDIO_EXT | VIDEO_EXT))
    doc = sorted(e.lstrip(".") for e in (DOC_EXT | SHEET_EXT | SLIDES_EXT))
    return {
        "images": {"from": img + ["pdf", "svg"], "to": ["jpg", "jpeg", "png", "webp", "tiff", "bmp", "gif", "pdf", "ico", "jp2"],
                   "note": "الصور تتحول إلى بعضها وإلى PDF؛ وPDF أو مستند أو فيديو أو SVG إلى صور (ملف لكل صفحة)."},
        "audio_video": {"from": av, "to": av + ["gif", "png", "jpg"],
                        "note": "الصوت والفيديو إلى أي صيغة ffmpeg، واستخراج الصوت من الفيديو، ولقطة من الفيديو كصورة، وفيديو إلى GIF."},
        "documents": {"from": doc + ["html", "htm", "md", "txt", "tex", "rst", "org", "pdf", "csv", "tsv", "json"],
                      "to": ["pdf", "docx", "doc", "odt", "rtf", "html", "txt", "md", "epub", "tex", "rst", "xlsx", "xls", "ods", "csv", "pptx", "ppt", "odp", "png", "jpg", "json"],
                      "note": "عبر LibreOffice وpandoc وCalibre: Word وExcel وPowerPoint وOpenDocument وكتب EPUB وMOBI وAZW3 وPDF (PDF إلى Word تقريبي)."},
        "ocr_to_text": {"from": img + ["pdf"], "to": ["txt", "md", "docx", "odt", "rtf", "html"],
                        "note": "صورة أو PDF ممسوح إلى نص بالتعرّف على الكتابة (عربي وإنجليزي) ثم إلى أي مستند."},
        "speech_to_text": {"from": av, "to": ["txt", "srt", "json"], "note": "تفريغ محلي."},
        "subtitles": {"from": ["srt", "vtt", "ass"], "to": ["srt", "vtt", "ass"]},
        "text_to_speech": {"from": ["txt", "md"], "to": ["m4a", "mp3"]},
        "archives": {"from": sorted(e.lstrip(".") for e in ARCHIVE_EXT), "to": [], "note": "قراءة محتويات الأرشيف فقط (لا تحويل)."}
    }


def convert_status(job_id: str, seconds: int = 5) -> dict:
    job = CONVERT_JOBS.get(job_id)
    if not job:
        return {"error": "معرّف المهمة غير موجود."}
    if job["state"] == "running" and seconds > 0:
        end = time.time() + seconds
        while time.time() < end and job["state"] == "running":
            time.sleep(0.5)
    return dict(job)


def convert(src, target_ext: str, out_dir=None, options: dict | None = None) -> dict:
    """تحويل بين الصيغ:
    - لا يستبدل ملفًا موجودًا أبدًا (يضيف رقمًا)
    - المخرج افتراضيًا uploads/converted/ أو out_dir المحدد
    """
    src_p = Path(src).resolve()
    if not src_p.is_file():
        raise ValueError(f"الملف المصدر غير موجود: {src_p}")

    t_ext = "." + target_ext.lstrip(".").lower()
    src_ext = src_p.suffix.lower()

    if out_dir:
        dest_dir = Path(out_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
    else:
        dest_dir = get_converted_dir()

    target_name = f"{src_p.stem}{t_ext}"
    target_path = get_unique_path(dest_dir / target_name)

    # 1. صوت إلى نص (Transcribe)
    if src_ext in (AUDIO_EXT | VIDEO_EXT) and t_ext in (".txt", ".srt", ".json"):
        tr = transcribe(src_p, wait_seconds=30)
        if tr.get("error"):
            return tr
        if tr.get("state") == "done":
            if t_ext == ".txt":
                target_path.write_text(tr.get("text", ""), encoding="utf-8")
            elif t_ext == ".srt":
                srt_data = _make_srt(tr.get("segments", []))
                target_path.write_text(srt_data, encoding="utf-8")
            elif t_ext == ".json":
                target_path.write_text(json.dumps(tr, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}
        return tr

    # 2. صور ↔ صور
    if (src_ext in IMG_EXT) and (t_ext in IMG_EXT or t_ext == ".pdf"):
        # صور -> pdf بـ PIL أو fitz
        if t_ext == ".pdf":
            try:
                from PIL import Image
                im = Image.open(src_p)
                if im.mode in ("RGBA", "P"):
                    im = im.convert("RGB")
                im.save(target_path, "PDF")
                return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}
            except Exception:
                try:
                    import fitz
                    doc = fitz.open()
                    imgdoc = fitz.open(src_p)
                    pdfbytes = imgdoc.convert_to_pdf()
                    imgpdf = fitz.open("pdf", pdfbytes)
                    doc.insert_pdf(imgpdf)
                    doc.save(str(target_path))
                    return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}
                except Exception as exc:
                    raise RuntimeError(f"فشل التحويل إلى PDF: {exc}")

        # صورة إلى صورة بـ sips أو PIL
        sips_fmt = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "tif": "tiff", "tiff": "tiff", "bmp": "bmp", "gif": "gif"}.get(t_ext.lstrip("."))
        if sips_fmt and _which("sips"):
            res = subprocess.run(["sips", "-s", "format", sips_fmt, str(src_p), "--out", str(target_path)], capture_output=True)
            if res.returncode == 0 and target_path.exists():
                return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}

        try:
            from PIL import Image
            im = Image.open(src_p)
            if t_ext in (".jpg", ".jpeg") and im.mode in ("RGBA", "P"):
                im = im.convert("RGB")
            im.save(target_path)
            return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}
        except Exception:
            pass  # يكمل إلى المحوّل الشامل

    # 3. صوتيات وفيديو بـ ffmpeg
    if (src_ext in (AUDIO_EXT | VIDEO_EXT)) and (t_ext in (AUDIO_EXT | VIDEO_EXT | {".gif"})):
        if not _which("ffmpeg"):
            raise RuntimeError("ffmpeg غير متوفر في المسار.")
        
        # فيديو -> gif
        if t_ext == ".gif":
            cmd = ["ffmpeg", "-i", str(src_p), "-vf", "fps=10,scale=480:-1:flags=lanczos", "-y", str(target_path)]
        # استخراج أو تحويل صوت
        elif t_ext in AUDIO_EXT:
            cmd = ["ffmpeg", "-i", str(src_p), "-vn", "-y", str(target_path)]
        else:
            cmd = ["ffmpeg", "-i", str(src_p), "-y", str(target_path)]

        # تشغيل ffmpeg
        job_id = uuid.uuid4().hex[:10]
        job = {"id": job_id, "src": str(src_p), "dst": str(target_path), "state": "running", "started": time.time(), "error": None}
        CONVERT_JOBS[job_id] = job

        def run_ff():
            try:
                res = subprocess.run(cmd, capture_output=True, timeout=1800)
                if res.returncode == 0 and target_path.exists():
                    job["state"] = "done"
                    job["size"] = target_path.stat().st_size
                else:
                    job["state"] = "error"
                    job["error"] = res.stderr.decode("utf-8", errors="replace")[:300]
            except Exception as exc:
                job["state"] = "error"
                job["error"] = str(exc)

        # نحاول إنجازه خلال 5 ثوانٍ، فإن طال يبقى كـ job
        t = threading.Thread(target=run_ff, daemon=True)
        t.start()
        t.join(timeout=5)
        if job["state"] == "done":
            return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}
        if job["state"] == "error":
            raise RuntimeError(f"خطأ في التحويل: {job['error']}")
        return {"id": job_id, "state": "running", "note": "التحويل قيد التنفيذ في الخلفية؛ استعلم بـ convert_status."}

    # 4. مستندات
    # txt / md -> docx مع دعم العربية
    if src_ext in (".txt", ".md") and t_ext == ".docx":
        src_text = src_p.read_text(encoding="utf-8", errors="replace")
        has_arabic = bool(re.search(r"[\u0600-\u06ff]", src_text))
        if has_arabic and ArabicDoc:
            doc = ArabicDoc()
            for line in src_text.splitlines():
                if line.strip():
                    doc.add_para(line)
                else:
                    doc.add_blank()
            doc.save(str(target_path))
            return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size, "arabic_docx": True}
        if _which("pandoc"):
            _run_cmd(["pandoc", str(src_p), "-o", str(target_path)], check=True)
            return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}

    # docx / odt / rtf / html / md / txt / epub بـ pandoc
    if src_ext in (".docx", ".odt", ".rtf", ".html", ".md", ".txt", ".epub") and t_ext in (".docx", ".odt", ".rtf", ".html", ".md", ".txt", ".epub", ".pdf"):
        if t_ext != ".pdf" and _which("pandoc"):
            try:
                _run_cmd(["pandoc", str(src_p), "-o", str(target_path)], check=True)
                return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}
            except Exception:
                pass

    # تحويل مستندات إلى PDF بـ soffice
    if t_ext == ".pdf" and _which("soffice"):
        tmp_dir = Path(tempfile.mkdtemp(prefix="pbdoc_pdf_"))
        try:
            _run_cmd(["soffice", "--headless", "--convert-to", "pdf", str(src_p), "--outdir", str(tmp_dir)], timeout=90, check=True)
            produced = tmp_dir / (src_p.stem + ".pdf")
            if produced.exists():
                shutil.move(str(produced), str(target_path))
                return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # pdf -> txt بـ pdftotext
    if src_ext == ".pdf" and t_ext == ".txt":
        p2t = _which("pdftotext") or "/opt/homebrew/bin/pdftotext"
        if os.path.exists(p2t):
            _run_cmd([p2t, "-layout", str(src_p), str(target_path)], check=True)
            return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}

    # pdf -> png بـ fitz
    if src_ext == ".pdf" and t_ext == ".png":
        try:
            import fitz
            doc = fitz.open(src_p)
            if doc.page_count > 0:
                pix = doc[0].get_pixmap(dpi=150)
                pix.save(str(target_path))
                return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size, "page": 1}
        except Exception as exc:
            raise RuntimeError(f"فشل تحويل PDF إلى PNG: {exc}")

    # 5. نص -> صوت بـ say ثم ffmpeg
    if src_ext in (".txt", ".md") and t_ext in (".m4a", ".mp3"):
        if not _which("say"):
            raise RuntimeError("أمر say غير متوفر في نظام macOS.")
        txt_content = src_p.read_text(encoding="utf-8", errors="replace")
        tmp_aiff = dest_dir / f"tmp_voice_{uuid.uuid4().hex[:6]}.aiff"
        
        # البحث عن صوت عربي
        voices_out = _run_cmd(["say", "-v", "?"])
        arabic_voice = None
        for v in ("Maged", "Laila", "Tarik", "Majed"):
            if v.lower() in voices_out.lower():
                arabic_voice = v
                break
        
        say_cmd = ["say", "-o", str(tmp_aiff)]
        if arabic_voice:
            say_cmd += ["-v", arabic_voice]
        say_cmd += ["-f", str(src_p)]
        
        res = subprocess.run(say_cmd, capture_output=True)
        if res.returncode == 0 and tmp_aiff.exists():
            if _which("ffmpeg"):
                subprocess.run(["ffmpeg", "-i", str(tmp_aiff), str(target_path), "-y"], capture_output=True)
                tmp_aiff.unlink(missing_ok=True)
                if target_path.exists():
                    return {"ok": True, "path": str(target_path), "size": target_path.stat().st_size}
        tmp_aiff.unlink(missing_ok=True)

    res = _convert_universal(src_p, src_ext, t_ext, target_path, dest_dir)
    if res:
        return res
    raise ValueError(f"التحويل من {src_ext} إلى {t_ext} غير مدعوم حاليًا؛ اطلب list_conversions لمعرفة الصيغ المتاحة.")


# ---------- المحوّل الشامل (احتياطي لكل ما لم تغطِّه الفروع السابقة) ----------
SOFFICE_IN = DOC_EXT | SHEET_EXT | SLIDES_EXT | {".html", ".htm", ".txt", ".md", ".pdf", ".xml", ".csv", ".tsv", ".rtf"}
SOFFICE_OUT = {".pdf", ".docx", ".doc", ".odt", ".rtf", ".html", ".txt", ".xlsx", ".xls", ".ods", ".csv", ".pptx", ".ppt", ".odp", ".png", ".jpg", ".epub"}
PANDOC_IN = {".md", ".html", ".htm", ".txt", ".docx", ".odt", ".rtf", ".epub", ".tex", ".latex", ".rst", ".org", ".textile", ".adoc"}
PANDOC_OUT = {".md": "gfm", ".html": "html", ".txt": "plain", ".docx": "docx", ".odt": "odt", ".rtf": "rtf", ".epub": "epub", ".tex": "latex", ".rst": "rst", ".org": "org", ".adoc": "asciidoc"}
SOFFICE_FILTER = {".txt": "txt:Text (encoded):UTF8", ".html": "html:XHTML Writer File:UTF8", ".csv": "csv:Text - txt - csv (StarCalc):44,34,76,1"}
SUBS_EXT = {".srt", ".vtt", ".ass"}


def _fin(target_path):
    return {"ok": True, "path": str(target_path), "size": Path(target_path).stat().st_size}


def _convert_universal(src_p, src_ext, t_ext, target_path, dest_dir):
    tmp = Path(tempfile.mkdtemp(prefix="pbconv_"))
    try:
        # ترجمات: srt/vtt/ass
        if src_ext in SUBS_EXT and t_ext in SUBS_EXT and _which("ffmpeg"):
            subprocess.run(["ffmpeg", "-y", "-i", str(src_p), str(target_path)], capture_output=True, timeout=60)
            if target_path.exists():
                return _fin(target_path)

        # كتب إلكترونية
        if (src_ext in EBOOK_EXT or t_ext in EBOOK_EXT) and _which("ebook-convert") and src_ext != t_ext:
            subprocess.run(["ebook-convert", str(src_p), str(target_path)], capture_output=True, timeout=600)
            if target_path.exists():
                return _fin(target_path)

        # إلى صورة من pdf/svg/فيديو/مستند
        if t_ext in IMG_EXT:
            png_pages = []
            if src_ext in (".pdf", ".svg"):
                import fitz
                d = fitz.open(str(src_p))
                for i in range(min(d.page_count, 200)):
                    pp = tmp / f"p{i+1}.png"
                    d[i].get_pixmap(dpi=150).save(str(pp))
                    png_pages.append(pp)
            elif src_ext in VIDEO_EXT and _which("ffmpeg"):
                pp = tmp / "p1.png"
                subprocess.run(["ffmpeg", "-y", "-ss", "1", "-i", str(src_p), "-frames:v", "1", str(pp)], capture_output=True, timeout=120)
                if not pp.exists():
                    subprocess.run(["ffmpeg", "-y", "-i", str(src_p), "-frames:v", "1", str(pp)], capture_output=True, timeout=120)
                if pp.exists():
                    png_pages.append(pp)
            elif src_ext in (DOC_EXT | SHEET_EXT | SLIDES_EXT | {".html", ".htm", ".txt", ".md"}) and _which("soffice"):
                subprocess.run(["soffice", "--headless", "--convert-to", "pdf", str(src_p), "--outdir", str(tmp)], capture_output=True, timeout=120)
                pdfp = tmp / (src_p.stem + ".pdf")
                if pdfp.exists():
                    import fitz
                    d = fitz.open(str(pdfp))
                    for i in range(min(d.page_count, 200)):
                        pp = tmp / f"p{i+1}.png"
                        d[i].get_pixmap(dpi=150).save(str(pp))
                        png_pages.append(pp)
            if png_pages:
                outs = []
                for i, pp in enumerate(png_pages):
                    dst = target_path if i == 0 else get_unique_path(dest_dir / f"{src_p.stem}-p{i+1}{t_ext}")
                    if t_ext == ".png":
                        shutil.copy(str(pp), str(dst))
                    else:
                        r = convert(pp, t_ext.lstrip("."), out_dir=tmp / "o")
                        shutil.move(r["path"], str(dst))
                    outs.append(str(dst))
                res = _fin(target_path)
                if len(outs) > 1:
                    res["paths"] = outs
                    res["pages"] = len(outs)
                return res
            # صورة إلى صورة بالجسر عبر png (مثل heic إلى webp)
            if src_ext in IMG_EXT and t_ext != ".png":
                mid = tmp / "mid.png"
                if _which("sips"):
                    subprocess.run(["sips", "-s", "format", "png", str(src_p), "--out", str(mid)], capture_output=True)
                if mid.exists():
                    from PIL import Image
                    im = Image.open(mid)
                    if t_ext in (".jpg", ".jpeg", ".jfif") and im.mode in ("RGBA", "P", "LA"):
                        im = im.convert("RGB")
                    im.save(target_path)
                    return _fin(target_path)

        # صورة أو PDF ممسوح إلى نص / مستند (OCR)
        if (src_ext in IMG_EXT or src_ext == ".pdf") and t_ext in (".txt", ".md", ".docx", ".odt", ".rtf", ".html"):
            txt = read_any(src_p, max_chars=10 ** 7).get("text", "")
            if not txt.strip():
                raise ValueError("لم أجد كتابة في هذا الملف بالتعرّف على الكتابة، فلا نص أحوّله.")
            if txt.strip():
                if t_ext == ".txt":
                    target_path.write_text(txt, encoding="utf-8")
                    return _fin(target_path)
                tt = tmp / (src_p.stem + ".txt")
                tt.write_text(txt, encoding="utf-8")
                r = convert(tt, t_ext.lstrip("."), out_dir=tmp / "o")
                shutil.move(r["path"], str(target_path))
                return _fin(target_path)

        # pandoc بين صيغ النص والمستندات
        if src_ext in PANDOC_IN and t_ext in PANDOC_OUT and _which("pandoc"):
            r = subprocess.run(["pandoc", str(src_p), "-t", PANDOC_OUT[t_ext], "-o", str(target_path)], capture_output=True, timeout=180)
            if r.returncode == 0 and target_path.exists():
                return _fin(target_path)
        if src_ext in PANDOC_IN and t_ext == ".pdf" and _which("pandoc") and _which("soffice"):
            mid = tmp / (src_p.stem + ".docx")
            subprocess.run(["pandoc", str(src_p), "-o", str(mid)], capture_output=True, timeout=180)
            if mid.exists():
                subprocess.run(["soffice", "--headless", "--convert-to", "pdf", str(mid), "--outdir", str(tmp)], capture_output=True, timeout=120)
                if (tmp / (src_p.stem + ".pdf")).exists():
                    shutil.move(str(tmp / (src_p.stem + ".pdf")), str(target_path))
                    return _fin(target_path)

        # LibreOffice العام (مستندات وجداول وعروض، وPDF إلى docx/odt…)
        if src_ext in SOFFICE_IN and t_ext in SOFFICE_OUT and _which("soffice") and src_ext != t_ext:
            conv = SOFFICE_FILTER.get(t_ext, t_ext.lstrip("."))
            cmd = ["soffice", "--headless"]
            if src_ext == ".pdf" and t_ext in (".docx", ".odt", ".doc", ".rtf", ".html", ".txt"):
                cmd += ["--infilter=writer_pdf_import"]
            cmd += ["--convert-to", conv, str(src_p), "--outdir", str(tmp)]
            subprocess.run(cmd, capture_output=True, timeout=180)
            made = tmp / (src_p.stem + t_ext)
            if made.exists():
                shutil.move(str(made), str(target_path))
                return _fin(target_path)

        # csv/tsv/json
        if src_ext in (".csv", ".tsv") and t_ext == ".json":
            import csv
            with open(src_p, newline="", encoding="utf-8-sig", errors="replace") as fh:
                rows = list(csv.DictReader(fh, delimiter="\t" if src_ext == ".tsv" else ","))
            target_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            return _fin(target_path)
        if src_ext == ".json" and t_ext in (".csv", ".tsv"):
            import csv
            data = json.loads(src_p.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list) and data and isinstance(data[0], dict):
                cols = list({k: 0 for r in data for k in r})
                with open(target_path, "w", newline="", encoding="utf-8-sig") as fh:
                    w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t" if t_ext == ".tsv" else ",")
                    w.writeheader()
                    for r in data:
                        w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in r.items()})
                return _fin(target_path)

        # جسر عام: مستند/جدول/عرض إلى pdf ثم إلى الهدف (نص أو صورة)
        if src_ext in SOFFICE_IN and src_ext != ".pdf" and t_ext in (IMG_EXT | {".txt"}) and _which("soffice"):
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf", str(src_p), "--outdir", str(tmp)], capture_output=True, timeout=180)
            pdfp = tmp / (src_p.stem + ".pdf")
            if pdfp.exists():
                r = convert(pdfp, t_ext.lstrip("."), out_dir=tmp / "o")
                shutil.move(r["path"], str(target_path))
                return _fin(target_path)
    except ValueError:
        raise
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return None


# ---------- تطبيع العربية والبحث في الوسائط ----------
def normalize_arabic(text: str) -> str:
    """تطبيع النص العربي لمطابقة البحث:
    - إزالة التشكيل
    - إزالة التطويل
    - توحيد الهمزات والياء والألف المقصورة والتاء المربوطة
    """
    text = str(text or "")
    # إزالة التشكيل
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    # إزالة التطويل
    text = re.sub(r"ـ+", "", text)
    # توحيد الهمزات
    text = re.sub(r"[إأآٱ]", "ا", text)
    text = re.sub(r"ؤ", "و", text)
    text = re.sub(r"ئ", "ى", text)
    # توحيد التاء المربوطة والهاء
    text = re.sub(r"ة", "ه", text)
    # توحيد الألف المقصورة والياء
    text = re.sub(r"ى", "ي", text)
    return text.strip().lower()


def search_media(root_path, query: str, kinds=("image", "audio", "video", "pdf"), limit: int = 30, build: bool = False) -> dict:
    """يبحث داخل محتوى الوسائط:
    - نص OCR للصور
    - نص التفريغ المخزن للصوت (لا يفرغ تلقائيًا إلا إذا build=True وبحد 5 ملفات)
    - نص PDF
    يعيد {results: [{path, kind, snippet, score}], unindexed: [...]}
    """
    root = Path(root_path).resolve()
    if not root.exists():
        raise ValueError(f"المسار غير موجود: {root}")

    norm_q = normalize_arabic(query)
    if not norm_q:
        raise ValueError("حدد عبارة البحث.")

    allowed_kinds = set(kinds)
    results = []
    unindexed = []
    built_count = 0

    # تجميع الملفات
    files_to_check = []
    if root.is_file():
        files_to_check.append(root)
    else:
        for r, _, fnames in os.walk(root):
            for f in fnames:
                if f.startswith("."):
                    continue
                fp = Path(r) / f
                files_to_check.append(fp)

    for p in files_to_check:
        k = kind_of(p)
        if k not in allowed_kinds:
            continue

        content = ""
        key = _file_hash_key(p)

        if k == "image":
            with LOCK:
                cached_ocr = OCR_CACHE.get(key)
            if cached_ocr is not None:
                content = cached_ocr
            elif build and built_count < 5:
                content = ocr_image(p)
                built_count += 1
            else:
                unindexed.append(str(p))
                continue

        elif k in ("audio", "video"):
            tc = get_transcript_cache(p)
            if tc:
                content = tc.get("text", "")
            elif build and built_count < 5:
                tr = transcribe(p, wait_seconds=20)
                if tr.get("state") == "done":
                    content = tr.get("text", "")
                    built_count += 1
                else:
                    unindexed.append(str(p))
                    continue
            else:
                unindexed.append(str(p))
                continue

        elif k == "pdf":
            # استخراج سريع لنص PDF
            p2t = _which("pdftotext") or "/opt/homebrew/bin/pdftotext"
            if os.path.exists(p2t):
                try:
                    content = _run_cmd([p2t, "-layout", str(p), "-"], timeout=15)
                except Exception:
                    content = ""

        if not content:
            continue

        norm_content = normalize_arabic(content)
        if norm_q in norm_content:
            # استخراج مقتطف (Snippet) وحساب درجة المطابقة
            idx = norm_content.find(norm_q)
            start_pos = max(0, idx - 60)
            end_pos = min(len(content), idx + len(norm_q) + 60)
            snip = content[start_pos:end_pos].strip()
            score = norm_content.count(norm_q)
            results.append({
                "path": str(p),
                "kind": k,
                "snippet": ("..." if start_pos > 0 else "") + snip + ("..." if end_pos < len(content) else ""),
                "score": score
            })

    results.sort(key=lambda x: -x["score"])
    return {
        "results": results[:limit],
        "count": len(results),
        "unindexed": unindexed[:50],
        "unindexed_count": len(unindexed)
    }
