"""تحديث زاجل من GitHub ومزامنة الإعدادات والذاكرة بين الأجهزة.
التحديث: ينزّل آخر شيفرة من المستودع العام، يتحقق منها، ويضعها في مجلد بيانات زاجل (لا يلمس ملفات البرنامج نفسه)،
ثم يعيد تشغيل الخادم على الشيفرة الجديدة. المزامنة: عبر مستودع خاص بحسابك، ولا يُرسل شيء إلا حين تضغط زر المزامنة."""
import io
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

REPO = "zerouno2345seis-oss/zajel"
BRANCH = "main"
DATA_REPO_NAME = "zajel-data"
DATA = None
ROOT = Path(__file__).resolve().parent
KEEP = ("*.py", "*.js", "*.html", "VERSION", "icon.icns", "icon.png")


def init(data_dir):
    global DATA
    DATA = Path(data_dir)


def _ver(text):
    try:
        return tuple(int(x) for x in str(text).strip().split("."))
    except ValueError:
        return (0,)


def local_version():
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0"


def check():
    latest, errs = "", []
    # بالترتيب: gh المسجَّل (بلا حدّ زيارات)، ثم واجهة GitHub العامة، ثم الرابط الخام (قد يتأخر ٥ دقائق)
    try:
        r = _run(["gh", "api", f"repos/{REPO}/contents/VERSION?ref={BRANCH}", "-H", "Accept: application/vnd.github.raw"], timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            latest = r.stdout.strip()
        else:
            errs.append("gh: " + r.stderr.strip()[:60])
    except Exception as exc:
        errs.append("gh: " + str(exc)[:60])
    for url, hdr in ((f"https://api.github.com/repos/{REPO}/contents/VERSION?ref={BRANCH}", {"Accept": "application/vnd.github.raw"}),
                     (f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/VERSION", {})):
        if latest:
            break
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "zajel", **hdr}), timeout=15) as resp:
                latest = resp.read().decode("utf-8").strip()
        except Exception as exc:
            errs.append(str(exc)[:80])
    if not latest:
        return {"current": local_version(), "latest": "", "available": False, "error": "تعذّر الوصول إلى GitHub: " + " | ".join(errs)}
    return {"current": local_version(), "latest": latest, "available": _ver(latest) > _ver(local_version())}


def apply():
    info = check()
    if info.get("error"):
        raise ValueError(info["error"])
    if not info["available"]:
        raise ValueError("أنت على آخر إصدار.")
    req = urllib.request.Request(f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}", headers={"User-Agent": "zajel"})
    with urllib.request.urlopen(req, timeout=60) as r:
        blob = r.read(60 * 1024 * 1024)
    tmp = Path(tempfile.mkdtemp(prefix="zajel_upd_"))
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for n in z.namelist():
                if n.startswith("/") or ".." in Path(n).parts:
                    raise ValueError("ملف التحديث غير سليم.")
            z.extractall(tmp)
        src = next((p for p in tmp.iterdir() if p.is_dir()), None)
        if not src or not (src / "samsung_backup_web.py").exists() or not (src / "VERSION").exists():
            raise ValueError("ملف التحديث ناقص.")
        for f in src.glob("*.py"):
            py_compile.compile(str(f), cfile=str(tmp / "x.pyc"), doraise=True)      # لا نستبدل الشيفرة بشيفرة معطوبة
        new = DATA / "code.new"
        shutil.rmtree(new, ignore_errors=True)
        new.mkdir(parents=True)
        for pat in KEEP:
            for f in src.glob(pat):
                shutil.copy2(f, new / f.name)
        if (src / "icons").is_dir():
            shutil.copytree(src / "icons", new / "icons")
        cur, prev = DATA / "code", DATA / "code.prev"
        shutil.rmtree(prev, ignore_errors=True)
        if cur.exists():
            cur.rename(prev)
        new.rename(cur)
        (cur / ".boots").write_text("0")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    threading.Thread(target=_restart, daemon=True).start()
    return {"ok": True, "restarting": True, "version": info["latest"]}


def _restart():
    time.sleep(1.5)
    script = DATA / "code" / "samsung_backup_web.py"
    os.environ["PB_OVERLAY_ACTIVE"] = "1"
    os.execv(sys.executable, [sys.executable, str(script)] + sys.argv[1:])


# ---------- المزامنة ----------
def _env():
    import agent_runner
    return {"PATH": agent_runner._env_path(), "HOME": str(Path.home()), "LANG": "en_US.UTF-8", "GIT_TERMINAL_PROMPT": "0"}


def _run(cmd, cwd=None, timeout=60):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=_env(), stdin=subprocess.DEVNULL)


def _state_file():
    return DATA / "sync_state.json"


def sync_status():
    try:
        st = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    try:
        ready = _run(["gh", "auth", "status"], timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ready = False
    return {"configured": bool(st.get("last")), "repo": st.get("repo") or DATA_REPO_NAME, "last": st.get("last", 0), "last_msg": st.get("msg", ""), "gh_ready": ready}


def _git_time(repo, rel):
    r = _run(["git", "log", "-1", "--format=%ct", "--", rel], cwd=repo)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def ensure_repo():
    """يجهّز النسخة المحلية من مستودع المزامنة الخاص (ينشئه إن لم يوجد) ويعيد مساره."""
    if not sync_status()["gh_ready"]:
        raise ValueError("سجّل الدخول إلى GitHub في الطرفية أولًا: gh auth login")
    # المالك ثابت (صاحب مستودع زاجل) لا الحساب المسجَّل على هذا الجهاز: وإلا صار لكل جهاز بحساب مختلف مستودع منفصل فلا يلتقيان
    owner = REPO.split("/")[0]
    me = _run(["gh", "api", "user", "-q", ".login"], timeout=20).stdout.strip()
    if me and me != owner and _run(["gh", "api", f"repos/{owner}/{DATA_REPO_NAME}", "-q", ".name"], timeout=20).returncode != 0:
        raise ValueError(f"هذا الجهاز مسجَّل في GitHub بحساب «{me}»، ومستودع المزامنة الخاص يملكه «{owner}». "
                         f"اقبل دعوة المشاركة في المستودع على هذا الجهاز، أو سجّل الدخول بحساب {owner}: gh auth login")
    repo = DATA / "sync_repo"
    full = f"{owner}/{DATA_REPO_NAME}"
    if (repo / ".git").exists():
        url = _run(["git", "remote", "get-url", "origin"], cwd=repo).stdout.strip()
        if f"/{full}" not in url and f":{full}" not in url:      # نسخة من مستودع حساب آخر (قبل تثبيت المالك): تُنحّى ويُنسخ الصحيح
            old = DATA / f"sync_repo.old.{int(time.time())}"
            repo.rename(old)
    if not (repo / ".git").exists():
        if _run(["gh", "repo", "clone", full, str(repo)], timeout=90).returncode != 0:
            c = _run(["gh", "repo", "create", full, "--private", "--description", "إعدادات وذاكرة زاجل (خاص)"], timeout=60)
            if c.returncode != 0:
                raise ValueError("تعذّر إنشاء مستودع المزامنة الخاص: " + c.stderr.strip()[:120])
            if _run(["gh", "repo", "clone", full, str(repo)], timeout=90).returncode != 0:
                raise ValueError("تعذّر نسخ مستودع المزامنة.")
    return repo


def sync_run():
    import assistant_store as S
    repo = ensure_repo()
    _run(["git", "pull", "--rebase", "--quiet"], cwd=repo, timeout=60)
    # الذاكرة: دمج بحسب الأحدث تحديثًا
    rm = repo / "assistant_memory.md"
    a = u = d = 0
    if rm.exists():
        a, u, d = S.memory_merge_remote(rm.read_text(encoding="utf-8"))
    rm.write_text(S.memory_dump_text(), encoding="utf-8")
    # الأوامر الجاهزة: اتحاد بالمعرّف
    rp, lp = repo / "assistant_prompts.json", DATA / "assistant_prompts.json"
    def _j(p, dflt):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return dflt
    merged = {str(x.get("id") or x.get("title")): x for x in _j(rp, []) + _j(lp, []) if isinstance(x, dict)}
    out = list(merged.values())
    rp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    lp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    # الأتمتة: تصل قواعد الجهاز الآخر إلى هنا موقوفة (مجلداته قد لا توجد هنا)، فتشغّلها أنت إن أردت
    import automation
    ra = repo / "automations.json"
    remote_rules = _j(ra, [])
    with automation.LOCK:
        local_rules = automation.rules_list()
        have = {r["id"] for r in local_rules}
        auto_new = 0
        for r in remote_rules:
            if isinstance(r, dict) and r.get("id") and r["id"] not in have:
                local_rules.append(dict(r, enabled=False, last_note="وصلت من جهاز آخر وهي موقوفة؛ شغّلها إن كانت مجلداتها موجودة هنا."))
                auto_new += 1
        if auto_new:
            automation._save("automations.json", local_rules)
    merged_rules = {r["id"]: r for r in remote_rules if isinstance(r, dict) and r.get("id")}
    for r in local_rules:
        merged_rules.setdefault(r["id"], dict(r, enabled=False))
    ra.write_text(json.dumps(list(merged_rules.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    # الإعدادات: الأحدث يفوز كاملةً
    rs, ls = repo / "assistant_settings.json", DATA / "assistant_settings.json"
    settings = "same"
    if rs.exists() and ls.exists() and rs.read_text(encoding="utf-8") != ls.read_text(encoding="utf-8"):
        if _git_time(repo, "assistant_settings.json") > ls.stat().st_mtime:
            ls.write_text(rs.read_text(encoding="utf-8"), encoding="utf-8"); settings = "pulled"
        else:
            rs.write_text(ls.read_text(encoding="utf-8"), encoding="utf-8"); settings = "pushed"
    elif ls.exists() and not rs.exists():
        rs.write_text(ls.read_text(encoding="utf-8"), encoding="utf-8"); settings = "pushed"
    elif rs.exists() and not ls.exists():
        ls.write_text(rs.read_text(encoding="utf-8"), encoding="utf-8"); settings = "pulled"
    _run(["git", "add", "-A"], cwd=repo)
    if _run(["git", "status", "--porcelain"], cwd=repo).stdout.strip():
        _run(["git", "-c", "user.name=zajel", "-c", "user.email=zajel@localhost", "commit", "-q", "-m", "مزامنة " + time.strftime("%Y-%m-%d %H:%M")], cwd=repo)
        p = _run(["git", "push", "--quiet"], cwd=repo, timeout=90)
        if p.returncode != 0:
            raise ValueError("تعذّر رفع المزامنة: " + p.stderr.strip()[:120])
    msg = f"أُضيف {a} وتحدّث {u} وحُذف {d} في الذاكرة" + (f"، ووصلت {auto_new} قاعدة أتمتة (موقوفة)" if auto_new else "")
    _state_file().write_text(json.dumps({"last": time.time(), "msg": msg, "repo": DATA_REPO_NAME}), encoding="utf-8")
    return {"ok": True, "memory_added": a, "memory_updated": u, "memory_removed": d, "settings": settings, "msg": msg}
