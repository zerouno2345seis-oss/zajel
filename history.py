"""سجلّ النتائج: يحفظ نتائج البحث والتنظيف المكتملة على القرص لتُستعاد لاحقًا من قائمة منسدلة بدل البدء من جديد."""
import json
import threading
import time
import uuid
from pathlib import Path

DIR = None
KEEP = 25                  # آخر كم نتيجة لكل نوع
MAX_BYTES = 20 << 20
LOCK = threading.RLock()
LABELS = {"search": "بحث", "clean": "تنظيف"}


def init(data_dir):
    global DIR
    DIR = Path(data_dir) / "history"
    try:
        DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        DIR = None


def _index():
    return sorted((p for p in (DIR.glob("*.json") if DIR else [])), key=lambda p: p.stat().st_mtime, reverse=True)


def save(kind, title, meta, payload):
    """يحفظ نتيجة مكتملة. يعيد معرّف السجل أو None."""
    if not DIR:
        return None
    try:
        rid = uuid.uuid4().hex[:10]
        blob = json.dumps({"id": rid, "kind": kind, "title": title, "time": time.time(), "meta": meta, "payload": payload}, ensure_ascii=False, default=list)
        if len(blob) > MAX_BYTES:
            return None
        with LOCK:
            tmp = DIR / (rid + ".tmp")
            tmp.write_text(blob, encoding="utf-8")
            tmp.replace(DIR / (kind + "_" + rid + ".json"))
            (DIR / (kind + "_" + rid + ".meta")).write_text(json.dumps({"id": rid, "title": title, "time": time.time(), "meta": meta}, ensure_ascii=False), encoding="utf-8")
            old = [p for p in _index() if p.name.startswith(kind + "_")][KEEP:]
            for p in old:
                p.unlink(missing_ok=True)
                p.with_suffix(".meta").unlink(missing_ok=True)
        return rid
    except (OSError, TypeError, ValueError):
        return None


def listing(kind):
    out = []
    for p in _index():
        if not p.name.startswith(kind + "_"):
            continue
        try:
            out.append(json.loads(p.with_suffix(".meta").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def load(rid):
    for p in _index():
        if p.name.endswith("_" + str(rid) + ".json"):
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
    return None


def delete(rid):
    for p in _index():
        if p.name.endswith("_" + str(rid) + ".json"):
            p.unlink(missing_ok=True)
            p.with_suffix(".meta").unlink(missing_ok=True)
            return True
    return False


def watch(kind, job, title, meta, build):
    """يراقب مهمة جارية؛ إذا اكتملت (done) يحفظ build(job) في السجل."""
    def run():
        while job.get("state") == "running":
            time.sleep(1)
        if job.get("state") == "done":
            try:
                payload = build(job)
                if payload:
                    save(kind, title(job) if callable(title) else title, meta(job) if callable(meta) else meta, payload)
            except Exception:
                pass
    threading.Thread(target=run, daemon=True).start()
