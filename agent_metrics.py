"""سجل قياسات الوكلاء: سطر لكل ردّ (وكيل، نموذج، ثواني، نتيجة، أحجام النص) في ملف نصي صغير داخل مجلد بيانات زاجل.
لا يُرسل شيئًا لأي نموذج: الأرقام كلها من ردود جرت أصلًا. التوكنات تقديرية (≈ ثلث عدد الأحرف) إلا إن توفّرت حقيقية."""
import json
import re
import statistics
import threading
import time

DATA = None
LOCK = threading.RLock()
FILE = "agent_metrics.jsonl"
MAX_LINES = 20000
RANGES = {24: (24, 3600), 168: (28, 6 * 3600), 720: (30, 86400)}     # ساعات المدى ← (عدد الخانات، طول الخانة بالثواني)


def init(data_dir):
    global DATA
    from pathlib import Path
    DATA = Path(data_dir)


def _p():
    return DATA / FILE


def record(agent, model, secs, state, error="", chars_in=0, chars_out=0, t=None):
    if DATA is None:
        return
    row = {"t": round(t or time.time(), 1), "agent": agent, "model": model or "", "secs": round(float(secs or 0), 1), "state": state,
           "err": re.sub(r"\s+", " ", str(error or ""))[:200], "cin": int(chars_in or 0), "cout": int(chars_out or 0)}
    with LOCK:
        with open(_p(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _rows():
    with LOCK:
        if not _p().exists():
            _backfill()
        try:
            lines = _p().read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
    if len(lines) > MAX_LINES:
        with LOCK:
            _p().write_text("\n".join(lines[-MAX_LINES // 2:]) + "\n", encoding="utf-8")
        lines = lines[-MAX_LINES // 2:]
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def _backfill():
    """مرة واحدة: يملأ الماضي من المحادثات المحفوظة (الردود التي لها زمن ونتيجة)."""
    try:
        chats = json.loads((DATA / "assistant_chats.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        chats = {}
    rows = []
    for c in chats.values():
        for m in c.get("messages", []):
            if m.get("role") == "assistant" and "secs" in m and m.get("state") in ("done", "error", "stopped"):
                rows.append({"t": round(m.get("t") or 0, 1), "agent": m.get("agent") or c.get("agent") or "?", "model": m.get("model") or "",
                             "secs": m.get("secs") or 0, "state": m["state"], "err": str(m.get("error") or "")[:200], "cin": 0, "cout": len(m.get("text") or "")})
    rows.sort(key=lambda r: r["t"])
    _p().write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _med(v):
    return round(statistics.median(v), 1) if v else None


def stats(hours=24, installed=None, names=None):
    hours = hours if hours in RANGES else 24
    n, step = RANGES[hours]
    now = time.time()
    start = now - n * step
    rows = [r for r in _rows() if r["t"] >= start]
    by = {}
    for r in rows:
        by.setdefault(r["agent"], []).append(r)
    ids = list(dict.fromkeys(list(names or []) + list(by)))
    agents, errors = [], []
    for a in ids:
        rs = by.get(a, [])
        real = [r for r in rs if r["state"] in ("done", "error")]      # الإيقاف اليدوي ليس فشلًا
        oks = [r for r in real if r["state"] == "done"]
        secs = [r["secs"] for r in oks]
        recent = real[-3:]
        status, why = "idle", "لم يُجرَّب في هذا المدى"
        if installed is not None and a in installed and not installed[a]:
            status, why = "down", "الأداة غير مثبّتة"
        elif len(recent) == 3 and all(r["state"] == "error" for r in recent):
            status, why = "down", "فشل آخر ثلاث محاولات"
        elif real:
            last5 = [r["secs"] for r in oks[-5:]]
            if len(secs) >= 5 and last5 and statistics.median(last5) > 1.8 * statistics.median(secs):
                status, why = "slow", "أبطأ من معتاده"
            else:
                status, why = "ok", "يعمل"
        series = []
        for i in range(n):
            lo, hi = start + i * step, start + (i + 1) * step
            series.append(_med([r["secs"] for r in oks if lo <= r["t"] < hi]))
        tok = sum((r["cin"] + r["cout"]) / 3 for r in rs)
        agents.append({"id": a, "status": status, "why": why, "count": len(real), "median": _med(secs), "p90": round(sorted(secs)[int(len(secs) * 0.9) - 1], 1) if len(secs) >= 5 else (max(secs) if secs else None),
                       "success": round(100 * len(oks) / len(real)) if real else None, "tokens": int(tok), "series": series})
        for r in real:
            if r["state"] == "error":
                errors.append({"t": r["t"], "agent": a, "error": r["err"] or "خطأ غير موصوف"})
    errors.sort(key=lambda e: -e["t"])
    return {"hours": hours, "step": step, "agents": agents, "errors": errors[:15], "total_tokens": sum(x["tokens"] for x in agents), "estimated": True}
