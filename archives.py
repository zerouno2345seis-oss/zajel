"""الأرشيفات كمجلدات. القراءة والاستخراج لكل الصيغ (ZIP وTAR وRAR و7z وISO وCAB)،
والكتابة (إضافة/حذف/إعادة تسمية/مجلد جديد) لـ ZIP وTAR فقط، بإعادة كتابة أرشيف مؤقت ثم استبداله ذرّيًا.
المسار الافتراضي لعنصر داخل أرشيف: «<مسار الأرشيف>::<المسار الداخلي>»."""
from __future__ import annotations

import os
import posixpath
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

BSDTAR = "/usr/bin/bsdtar"
COMPOUND = {".tar.gz": "tar", ".tar.bz2": "tar", ".tar.xz": "tar"}
SIMPLE = {".zip": "zip", ".tar": "tar", ".tgz": "tar", ".tbz2": "tar", ".txz": "tar", ".rar": "rar", ".7z": "7z", ".iso": "iso", ".cab": "cab"}
MAX_ENTRIES = 300_000
MAX_EXTRACT = 20 * 1024 ** 3
_cache: dict = {}


def kind_of(name: str):
    n = name.lower()
    for ext, k in COMPOUND.items():
        if n.endswith(ext):
            return k
    return SIMPLE.get(os.path.splitext(n)[1])


def is_archive_name(name: str) -> bool:
    return kind_of(name) is not None


def writable(path) -> bool:
    return kind_of(str(path)) in ("zip", "tar")


def split(rel: str):
    """('a/b.zip::x/y') → ('a/b.zip', 'x/y'). بلا «::» يعيد (rel, None)."""
    if "::" not in rel:
        return rel, None
    a, inner = rel.split("::", 1)
    return a, inner.strip("/")


def norm(name: str) -> str:
    name = name.replace("\\", "/")
    while name.startswith("./"):
        name = name[2:]
    return name.strip("/")


def safe_rel(rel: str) -> str:
    """يرفض الأسماء الخطرة (.. أو مسار مطلق) داخل الأرشيف (zip-slip)."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts) or rel.startswith("/"):
        raise ValueError("اسم داخل الأرشيف غير آمن: " + rel)
    return "/".join(parts)


# ---------------- القراءة ----------------
def list_all(archive: Path) -> list[dict]:
    st = archive.stat()
    key = (str(archive), st.st_mtime, st.st_size)
    if key in _cache:
        return _cache[key]
    k = kind_of(archive.name)
    out: list[dict] = []
    if k == "zip":
        with zipfile.ZipFile(archive) as zf:
            for i in zf.infolist():
                if len(out) > MAX_ENTRIES:
                    raise ValueError("الأرشيف يحوي عناصر كثيرة جدًا.")
                n = norm(i.filename)
                if not n:
                    continue
                try:
                    mt = time.mktime(i.date_time + (0, 0, -1))
                except Exception:
                    mt = 0
                out.append({"name": n, "size": i.file_size, "mtime": mt, "is_dir": i.is_dir(), "enc": bool(i.flag_bits & 1)})
    elif k == "tar":
        with tarfile.open(archive, "r:*") as tf:
            for m in tf:
                if len(out) > MAX_ENTRIES:
                    raise ValueError("الأرشيف يحوي عناصر كثيرة جدًا.")
                if not (m.isfile() or m.isdir()):
                    continue
                n = norm(m.name)
                if n:
                    out.append({"name": n, "size": m.size, "mtime": m.mtime, "is_dir": m.isdir(), "enc": False})
    else:
        r = subprocess.run([BSDTAR, "-tvf", str(archive)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if r.returncode and not r.stdout:
            raise ValueError("تعذّرت قراءة الأرشيف (قد يكون تالفًا أو مشفّرًا): " + r.stderr.strip()[:150])
        pat = re.compile(r"^(\S+)\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\w{3})\s+(\d+)\s+([\d:]+)\s+(.*)$")
        for line in r.stdout.splitlines():
            m = pat.match(line)
            if not m:
                continue
            perm, size, mon, day, tm, name = m.groups()
            n = norm(name)
            if not n or len(out) > MAX_ENTRIES:
                continue
            try:
                yr = time.localtime().tm_year if ":" in tm else int(tm)
                mt = time.mktime(time.strptime(f"{yr} {mon} {day} {tm if ':' in tm else '00:00'}", "%Y %b %d %H:%M"))
            except Exception:
                mt = 0
            out.append({"name": n, "size": int(size), "mtime": mt, "is_dir": perm.startswith("d") or name.endswith("/"), "enc": False})
    out = [e for e in out if ".." not in e["name"].split("/") and not e["name"].startswith("/")]   # أخفِ الأسماء الخطرة
    if len(_cache) > 8:
        _cache.pop(next(iter(_cache)))
    _cache[key] = out
    return out


def browse(archive: Path, inner: str, rel_archive: str) -> list[dict]:
    inner = safe_rel(inner or "")
    prefix = inner + "/" if inner else ""
    children: dict[str, dict] = {}
    for e in list_all(archive):
        n = e["name"]
        if prefix and not n.startswith(prefix):
            continue
        rest = n[len(prefix):]
        if not rest:
            continue
        first, sep, tail = rest.partition("/")
        isdir = bool(sep) or e["is_dir"]
        c = children.get(first)
        if c is None:
            children[first] = {"name": first, "path": f"{rel_archive}::{prefix}{first}", "is_dir": isdir, "size": None if isdir else e["size"],
                               "mod": int(e["mtime"] * 1000), "chg": int(e["mtime"] * 1000), "is_archive": (not isdir) and is_archive_name(first)}
        elif isdir and not c["is_dir"]:
            c["is_dir"] = True
            c["size"] = None
    return list(children.values())


def entry(archive: Path, inner: str):
    inner = safe_rel(inner)
    for e in list_all(archive):
        if e["name"] == inner:
            return e
    prefix = inner + "/"
    if any(e["name"].startswith(prefix) for e in list_all(archive)):
        return {"name": inner, "size": 0, "mtime": 0, "is_dir": True, "enc": False}
    return None


# ---------------- الاستخراج ----------------
def _members(archive: Path, inner: str):
    inner = safe_rel(inner)
    prefix = inner + "/"
    return [e for e in list_all(archive) if e["name"] == inner or e["name"].startswith(prefix)]


def extract(archive: Path, inner: str, dest_dir: Path) -> Path:
    """يستخرج عنصرًا (ملفًا أو مجلدًا) إلى dest_dir/<اسمه>. يعيد المسار المستخرج."""
    inner = safe_rel(inner)
    if not inner:
        raise ValueError("اختر عنصرًا داخل الأرشيف.")
    members = _members(archive, inner)
    if not members:
        raise ValueError("العنصر غير موجود داخل الأرشيف.")
    total = sum(m["size"] for m in members)
    if total > MAX_EXTRACT:
        raise ValueError("حجم المستخرج أكبر من الحد المسموح (20 GB).")
    comp = max(1, archive.stat().st_size)
    if total > 2 * 1024 ** 3 and total / comp > 200:
        raise ValueError("نسبة الضغط مريبة (قد يكون قنبلة ضغط)؛ لم أستخرجه.")
    if any(m["enc"] for m in members):
        raise ValueError("الأرشيف مشفّر بكلمة مرور؛ غير مدعوم.")
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = dest_dir / posixpath.basename(inner)
    k = kind_of(archive.name)
    if k == "zip":
        with zipfile.ZipFile(archive) as zf:
            for i in zf.infolist():
                n = norm(i.filename)
                if n != inner and not n.startswith(inner + "/"):
                    continue
                target = _safe_target(base, n[len(inner):].lstrip("/"))
                if i.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(i) as s, open(target, "wb") as d:
                        shutil.copyfileobj(s, d)
                    _stamp(target, i.date_time)
    elif k == "tar":
        with tarfile.open(archive, "r:*") as tf:
            for m in tf:
                n = norm(m.name)
                if n != inner and not n.startswith(inner + "/"):
                    continue
                target = _safe_target(base, n[len(inner):].lstrip("/"))
                if m.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif m.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tf.extractfile(m) as s, open(target, "wb") as d:
                        shutil.copyfileobj(s, d)
                    os.utime(target, (m.mtime, m.mtime))
    else:
        tmp = Path(tempfile.mkdtemp(dir=dest_dir))
        try:
            r = subprocess.run([BSDTAR, "-xf", str(archive), "-C", str(tmp), "--no-same-owner", "--", inner], capture_output=True, text=True, timeout=3600)
            got = tmp / inner
            if r.returncode and not got.exists():
                raise ValueError("تعذّر الاستخراج: " + r.stderr.strip()[:150])
            for p in tmp.rglob("*"):
                if p.is_symlink():
                    p.unlink()
            if not got.exists():
                raise ValueError("لم يُستخرج شيء.")
            if base.exists():
                shutil.rmtree(base) if base.is_dir() else base.unlink()
            shutil.move(str(got), str(base))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if not base.exists():
        raise ValueError("لم يُستخرج شيء.")
    return base


def _safe_target(base: Path, rel: str) -> Path:
    rel = safe_rel(rel)
    t = (base / rel) if rel else base
    rb = base.resolve()
    rt = t.resolve() if t.exists() else (t.parent.resolve() / t.name)
    if rt != rb and rb not in rt.parents:
        raise ValueError("مسار خطر داخل الأرشيف: " + rel)
    return t


def _stamp(path: Path, dt):
    try:
        t = time.mktime(tuple(dt) + (0, 0, -1))
        os.utime(path, (t, t))
    except Exception:
        pass


# ---------------- الكتابة (ZIP وTAR) ----------------
def _check_writable(archive: Path):
    if not writable(archive):
        raise ValueError("هذا النوع من الأرشيفات للقراءة والاستخراج فقط. التعديل متاح لـ ZIP وTAR.")
    if any(e["enc"] for e in list_all(archive)):
        raise ValueError("الأرشيف مشفّر؛ لا يمكن تعديله.")


def _tar_mode(archive: Path):
    n = archive.name.lower()
    return "w:gz" if n.endswith((".tar.gz", ".tgz")) else "w:bz2" if n.endswith((".tar.bz2", ".tbz2")) else "w:xz" if n.endswith((".tar.xz", ".txz")) else "w"


def _unique(existing: set[str], name: str) -> str:
    if name not in existing:
        return name
    stem, ext = posixpath.splitext(name)
    i = 2
    while f"{stem} {i}{ext}" in existing:
        i += 1
    return f"{stem} {i}{ext}"


def _rewrite(archive: Path, transform, extra=None):
    """transform(name)->اسم جديد أو None للحذف. extra(writer) يضيف عناصر جديدة. يستبدل الأرشيف ذرّيًا."""
    _check_writable(archive)
    k = kind_of(archive.name)
    tmp = archive.with_name(f".{archive.name}.tmp{os.getpid()}")
    try:
        if k == "zip":
            with zipfile.ZipFile(archive) as old, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as new:
                for i in old.infolist():
                    n = norm(i.filename)
                    nn = transform(n)
                    if nn is None:
                        continue
                    zi = zipfile.ZipInfo(nn + ("/" if i.is_dir() else ""), date_time=i.date_time)
                    zi.compress_type = i.compress_type; zi.external_attr = i.external_attr
                    if i.is_dir():
                        new.writestr(zi, b"")
                    else:
                        with old.open(i) as s, new.open(zi, "w") as d:
                            shutil.copyfileobj(s, d)
                if extra:
                    extra(new)
        else:
            with tarfile.open(archive, "r:*") as old, tarfile.open(tmp, _tar_mode(archive)) as new:
                for m in old:
                    if not (m.isfile() or m.isdir()):
                        continue
                    nn = transform(norm(m.name))
                    if nn is None:
                        continue
                    m.name = nn
                    new.addfile(m, old.extractfile(m) if m.isfile() else None)
                if extra:
                    extra(new)
        os.replace(tmp, archive)
        _cache.clear()
    finally:
        if tmp.exists():
            tmp.unlink()


def delete(archive: Path, inner_paths: list[str]):
    targets = [safe_rel(p) for p in inner_paths]
    if not targets or any(not t for t in targets):
        raise ValueError("اختر عناصر داخل الأرشيف.")
    _rewrite(archive, lambda n: None if any(n == t or n.startswith(t + "/") for t in targets) else n)


def rename(archive: Path, inner: str, new_name: str):
    inner = safe_rel(inner)
    if not new_name or "/" in new_name or new_name in (".", ".."):
        raise ValueError("اسم غير صالح.")
    parent = posixpath.dirname(inner)
    new_full = (parent + "/" if parent else "") + new_name
    if any(e["name"] == new_full for e in list_all(archive)):
        raise ValueError("يوجد عنصر بهذا الاسم.")
    _rewrite(archive, lambda n: new_full + n[len(inner):] if (n == inner or n.startswith(inner + "/")) else n)


def move_within(archive: Path, pairs: list[tuple[str, str]]):
    pairs = [(safe_rel(a), safe_rel(b)) for a, b in pairs]
    def tr(n):
        for a, b in pairs:
            if n == a or n.startswith(a + "/"):
                return b + n[len(a):]
        return n
    _rewrite(archive, tr)


def mkdir(archive: Path, inner_dir: str, name: str) -> str:
    inner_dir = safe_rel(inner_dir or "")
    if not name or "/" in name or name in (".", ".."):
        raise ValueError("اسم غير صالح.")
    existing = {e["name"].rsplit("/", 1)[-1] for e in list_all(archive) if posixpath.dirname(e["name"]) == inner_dir}
    final = _unique(existing, name)
    full = (inner_dir + "/" if inner_dir else "") + final
    def extra(w):
        if isinstance(w, zipfile.ZipFile):
            zi = zipfile.ZipInfo(full + "/", date_time=time.localtime()[:6]); zi.external_attr = (0o40755 << 16) | 0x10
            w.writestr(zi, b"")
        else:
            ti = tarfile.TarInfo(full); ti.type = tarfile.DIRTYPE; ti.mode = 0o755; ti.mtime = time.time(); w.addfile(ti)
    _rewrite(archive, lambda n: n, extra)
    return final


def add(archive: Path, inner_dir: str, items: list[tuple[Path, str]], policy: str = "keep") -> str:
    """يضيف ملفات/مجلدات محلية إلى المجلد الداخلي. items = [(مسار محلي، الاسم في الأرشيف)]."""
    inner_dir = safe_rel(inner_dir or "")
    existing_top = {e["name"][len(inner_dir) + 1 if inner_dir else 0:].split("/")[0] for e in list_all(archive) if (not inner_dir or e["name"].startswith(inner_dir + "/")) and e["name"] != inner_dir}
    chosen = []
    drop = set()
    for src, name in items:
        if name in existing_top:
            if policy == "skip":
                continue
            if policy == "replace":
                drop.add((inner_dir + "/" if inner_dir else "") + name)
            else:
                name = _unique(existing_top, name)
        existing_top.add(name)
        chosen.append((src, name))
    if not chosen:
        return ""
    def extra(w):
        for src, name in chosen:
            base = (inner_dir + "/" if inner_dir else "") + name
            if src.is_dir():
                for dp, dns, fns in os.walk(src):
                    rel = os.path.relpath(dp, src)
                    arc = base if rel == "." else base + "/" + rel.replace(os.sep, "/")
                    if isinstance(w, zipfile.ZipFile):
                        zi = zipfile.ZipInfo(arc + "/", date_time=time.localtime()[:6]); zi.external_attr = (0o40755 << 16) | 0x10; w.writestr(zi, b"")
                    else:
                        w.add(dp, arc, recursive=False)
                    for f in fns:
                        fp = Path(dp) / f
                        if fp.is_symlink():
                            continue
                        w.write(fp, arc + "/" + f) if isinstance(w, zipfile.ZipFile) else w.add(fp, arc + "/" + f)
            else:
                w.write(src, base) if isinstance(w, zipfile.ZipFile) else w.add(src, base)
    _rewrite(archive, lambda n: None if any(n == d or n.startswith(d + "/") for d in drop) else n, extra)
    return chosen[0][1] if chosen else ""
