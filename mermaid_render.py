"""رسم مخططات mermaid صورًا PNG بأداة mmdc، مع ذاكرة مؤقتة. لا يرفع استثناءً أبدًا."""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

MMDC_PATHS = [str(Path.home() / ".local/bin/mmdc"), "/opt/homebrew/bin/mmdc", "/usr/local/bin/mmdc"]
_STARTS = ("graph", "flowchart", "sequenceDiagram", "classDiagram", "stateDiagram", "erDiagram", "gantt", "pie",
           "mindmap", "timeline", "journey", "quadrantChart", "xychart-beta", "sankey-beta", "gitGraph", "block-beta")


def find_mmdc() -> str:
    for p in MMDC_PATHS:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return ""


def is_mermaid(lang: str, code: str) -> bool:
    if (lang or "").strip().lower() == "mermaid":
        return True
    for ln in (code or "").splitlines():
        if ln.strip():
            return ln.strip().startswith(_STARTS)
    return False


def _cache_dir() -> Path:
    base = os.environ.get("PB_DATA") or str(Path.home() / "Library/Application Support/Phone Backup")
    return Path(base) / "mermaid_cache"


def render(code: str, scale: int = 2) -> Optional[Path]:
    try:
        code = (code or "").strip()
        if not code:
            return None
        d = _cache_dir()
        d.mkdir(parents=True, exist_ok=True)
        out = d / (hashlib.sha1(code.encode("utf-8")).hexdigest()[:16] + ".png")
        if out.exists() and out.stat().st_size > 0:
            return out
        mmdc = find_mmdc()
        if not mmdc:
            return None
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join([str(Path(mmdc).parent), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"])
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "in.mmd"
            src.write_text(code, encoding="utf-8")
            subprocess.run([mmdc, "-i", str(src), "-o", str(out), "-b", "white", "-s", str(scale), "-q"],
                           timeout=60, capture_output=True, env=env)
        if out.exists() and out.stat().st_size > 0:
            files = sorted(d.glob("*.png"), key=lambda f: f.stat().st_mtime)
            for f in files[:-200]:
                f.unlink(missing_ok=True)
            return out
        return None
    except Exception:
        return None
