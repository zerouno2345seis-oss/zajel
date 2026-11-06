"""Read-only macOS device health snapshot used by the full-clean screen."""
from __future__ import annotations

import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_command(command: list[str], timeout: float = 4.0) -> str:
    """Run one allowlisted diagnostic command and return its text output."""
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    if result.returncode:
        raise RuntimeError("command failed")
    return result.stdout


def parse_pmset_custom(text: str) -> dict:
    settings: dict[str, dict[str, int]] = {}
    current = ""
    for line in text.splitlines():
        if re.search(r"Battery Power", line, re.I):
            current = "battery"
            settings[current] = {}
        elif re.search(r"AC Power", line, re.I):
            current = "ac"
            settings[current] = {}
        elif current:
            match = re.match(r"\s*(standby|hibernatemode)\s+(\d+)", line)
            if match:
                settings[current][match.group(1)] = int(match.group(2))
    return settings


def parse_pmset_g(text: str) -> dict:
    match = re.search(r"\b(AC Power|Battery Power)\b", text, re.I)
    return {"power_source": {"ac power": "الشاحن", "battery power": "البطارية"}.get(match.group(1).lower()) if match else None}


def parse_wake_log(text: str) -> dict:
    """يعدّ أحداث النوم والاستيقاظ من عمود النوع في سجل pmset (لا من النص الحر)."""
    deep = normal = displays = sleeps = 0
    slow = []
    for line in text.splitlines():
        m = re.match(r"\s*\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}\s+(\S+)\s+(.*)", line)
        if not m:
            continue
        kind, rest = m.group(1), m.group(2)
        if kind in ("Wake", "DarkWake"):
            if re.search(r"Standby|Hibernat", rest, re.I):
                deep += 1
            else:
                normal += 1
        elif kind == "Sleep":
            sleeps += 1
        elif kind == "Notification" and re.search(r"Display is turned (?:off|on)", rest, re.I):
            displays += 1
        elif kind == "WakeTime":
            t = re.search(r"([\d.]+)\s*sec", rest)
            if t and float(t.group(1)) >= 3:
                slow.append(float(t.group(1)))
    return {"deep": deep, "normal": normal, "display": displays, "sleep": sleeps, "slow_wakes": slow,
            "display_only": displays > 0 and sleeps == 0 and deep + normal == 0}


def _relevant_log(text: str) -> str:
    keep = [ln for ln in text.splitlines() if re.match(r"\s*\d{4}-\S+ \S+ \S+\s+(Wake|DarkWake|Sleep|WakeTime|Notification)\b", ln)]
    return "\n".join(keep[-300:])


def parse_assertions(text: str) -> dict[str, int]:
    ignored = {"powerd", "WindowServer", "coreaudiod"}
    blockers: dict[str, int] = {}
    for line in text.splitlines():
        if not re.search(r"PreventUserIdleSystemSleep|NoIdleSleepAssertion", line, re.I):
            continue
        match = re.search(r"\bpid\s+\d+\(([^)]+)\)", line, re.I)
        if not match:
            continue
        name = match.group(1)
        if name not in ignored:
            blockers[name] = blockers.get(name, 0) + 1
    return blockers


def _bytes_value(value: str, unit: str) -> float:
    scale = {"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}
    return float(value) * scale[unit.lower()[0]]


def parse_swap(text: str) -> dict:
    match = re.search(r"used\s*=\s*([\d.]+)\s*([KMGT]?)", text, re.I)
    total = re.search(r"total\s*=\s*([\d.]+)\s*([KMGT]?)", text, re.I)
    if not match:
        raise ValueError("swap usage missing")
    used = _bytes_value(match.group(1), match.group(2) or "b")
    return {"used_bytes": int(used), "used_gb": used / 1024**3,
            "total_bytes": int(_bytes_value(total.group(1), total.group(2) or "b")) if total else None}


def parse_memory_pressure(text: str) -> int | None:
    match = re.search(r"free percentage:\s*(\d+)%", text, re.I)
    return int(match.group(1)) if match else None


def parse_uptime_days(text: str) -> float | None:
    match = re.search(r"\bup\s+(?:(\d+)\s+days?[, ]*)?(?:(\d+):)?(\d+)\s*(?:mins?|minutes?)?", text, re.I)
    if not match:
        return None
    days, hours, minutes = (int(value or 0) for value in match.groups())
    # `up 2 days, 03:15` has hours and minutes; `up 03:15` has no day group.
    if hours and days == 0:
        return (hours * 60 + minutes) / 1440
    return days + (hours * 60 + minutes) / 1440


def _process_lines(lines: str):
    for line in lines.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3 or parts[0].lower() == "rss":
            continue
        try:
            yield int(parts[0]), float(parts[1]), parts[2]
        except ValueError:
            continue


def group_rss(lines: str) -> list[dict]:
    totals: dict[str, int] = {}
    for rss, _cpu, command in _process_lines(lines):
        # Match the skill's awk: strip the path, then group by the first word.
        name = os.path.basename(command).split()[0]
        totals[name] = totals.get(name, 0) + rss
    return [{"name": name, "rss_mb": round(kb / 1024, 1)}
            for name, kb in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:10]]


def parse_cpu_hogs(lines: str) -> list[dict]:
    return [{"name": os.path.basename(command).split()[0], "cpu_percent": cpu}
            for _rss, cpu, command in _process_lines(lines) if cpu > 50]


def parse_sysctl(text: str) -> dict:
    facts = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if key == "hw.memsize":
            facts["ram_bytes"] = int(value)
        elif key == "hw.ncpu":
            facts["cpu_count"] = int(value)
        elif key == "machdep.cpu.brand_string":
            facts["cpu"] = value
        elif key == "vm.swapusage":
            facts["swap"] = parse_swap(value)
        elif key == "kern.boottime":
            found = re.search(r"sec\s*=\s*(\d+)", value)
            if found:
                facts["boot_epoch"] = int(found.group(1))
    return facts


def parse_disk(text: str) -> dict:
    rows = [line.split() for line in text.splitlines() if line.strip()]
    for row in reversed(rows):
        if len(row) >= 5 and row[-1] == "/":
            try:
                total, used, available = map(int, row[1:4])
                # في APFS عمود «المستعمل» لا يشمل بقية وحدات الحاوية، فالنسبة تُحسب من الحجم الكلي.
                return {"total_bytes": total * 1024, "used_bytes": used * 1024,
                        "free_bytes": available * 1024, "free_gb": available / 1024**2,
                        "free_percent": round(100 * available / total) if total else 0}
            except (ValueError, IndexError):
                break
    raise ValueError("disk line missing")


def parse_login_items(text: str) -> list[str]:
    text = text.strip()
    if not text or text.lower() in {"missing value", "{}"}:
        return []
    return [item.strip().strip('"') for item in re.split(r",\s*", text) if item.strip()]


def _card(card_id: str, title: str, summary: str, details=None, advice=None,
          commands=None, status="ok") -> dict:
    return {"id": card_id, "title": title, "status": status, "summary": summary,
            "details": details or [], "advice": advice or [], "commands": commands or []}


def _warn(card_id: str, title: str) -> dict:
    return _card(card_id, title, "تعذّر قراءة هذه المعلومة.",
                 ["قد تكون أداة الفحص غير متاحة أو انتهت مهلتها."], status="warn")


def _scan() -> dict:
    """Collect a bounded, read-only health snapshot; individual failures become warnings."""
    specs = {
        "pmset": (["pmset", "-g", "batt"], 4),
        "custom": (["pmset", "-g", "custom"], 4),
        "log": (["pmset", "-g", "log"], 5),
        "assertions": (["pmset", "-g", "assertions"], 4),
        "sysctl": (["sysctl", "vm.swapusage", "hw.memsize", "hw.ncpu", "machdep.cpu.brand_string"], 4),
        "pressure": (["memory_pressure"], 4),
        "uptime": (["uptime"], 3),
        "boot": (["sysctl", "kern.boottime"], 3),
        "ps": (["ps", "-axo", "rss,pcpu,comm"], 5),
        "disk": (["df", "-k", "/"], 3),
        "login": (["osascript", "-e", 'tell application "System Events" to get the name of every login item'], 5),
    }
    results: dict[str, str | None] = {key: None for key in specs}
    if os.name == "posix" and __import__("platform").system() == "Darwin":
        with ThreadPoolExecutor(max_workers=len(specs)) as pool:
            futures = {pool.submit(run_command, cmd, timeout): key
                       for key, (cmd, timeout) in specs.items()}
            for future in as_completed(futures, timeout=7):
                key = futures[future]
                try:
                    output = future.result()
                    # The full log can be large; retain only the recent lines needed for wake analysis.
                    results[key] = _relevant_log(output) if key == "log" else output
                except Exception:
                    results[key] = None

    cards = []
    facts: dict = {}
    titles = {"sleep": "النوم والاستيقاظ", "awake_blockers": "تطبيقات تمنع النوم",
              "memory": "الذاكرة والرام", "top_apps": "أكثر التطبيقات استخدامًا للذاكرة",
              "cpu_hogs": "استخدام المعالج", "disk": "مساحة القرص", "login_items": "عناصر بدء التشغيل"}
    try:
        power = parse_pmset_g(results["pmset"] or "")
        custom = parse_pmset_custom(results["custom"] or "")
        log = parse_wake_log(results["log"] or "")
        battery = custom.get("battery", {})
        ac = custom.get("ac", {})
        details = [f"مصدر الطاقة الحالي: {power.get('power_source') or 'غير معروف'}.",
                   f"البطارية: وضع الاستعداد {battery.get('standby', 'غير معروف')}، والإسبات {battery.get('hibernatemode', 'غير معروف')}.",
                   f"الشاحن: وضع الاستعداد {ac.get('standby', 'غير معروف')}، والإسبات {ac.get('hibernatemode', 'غير معروف')}.",
                   f"استيقاظ عميق/عادي في السجل: {log['deep']} / {log['normal']}." ]
        if log["display_only"]:
            summary = "الشاشة انطفأت، لكن سجل الفحص لا يظهر نوم النظام؛ قد يكون البطء من ضغط المعالج."
        elif log["slow_wakes"] or (battery.get("standby") == 1 and log["deep"]):
            summary = "قد يستغرق الاستيقاظ وقتًا لأن الجهاز يحفظ نسخة من الرام على القرص."
        else:
            summary = "إعدادات النوم وسجل الاستيقاظ جاهزان للمراجعة."
        if log["slow_wakes"]:
            details.append(f"استيقاظات بطيئة (٣ ثوانٍ فأكثر): {len(log['slow_wakes'])}، أطولها {max(log['slow_wakes']):.0f} ث.")
        advice, commands = [], []
        if battery.get("standby") == 1:
            advice.append("«الاستعداد» يعني أن الجهاز بعد نوم طويل يحفظ ما في الرام على القرص ثم يطفئها، كمن يجمع أوراقه في الخزانة؛ فإذا فتحته انتظر حتى يعيدها. إيقافه على البطارية يجعل الاستيقاظ فوريًا مقابل استهلاك أكثر قليلًا للبطارية ليلًا.")
            commands.append({"label": "إيقاف الاستعداد على البطارية (يشغّله المستخدم بكلمة سر الجهاز)", "cmd": "sudo pmset -b standby 0"})
        elif battery.get("standby") == 0:
            advice.append("الاستعداد مُطفأ على البطارية، فالاستيقاظ لا ينتظر قراءة الرام من القرص.")
            commands.append({"label": "للتراجع وإعادته كما كان", "cmd": "sudo pmset -b standby 1"})
        if log["display_only"]:
            advice.append("إن كان البطء عند فتح الغطاء والجهاز لم ينم فعلًا، فالسبب انشغال المعالج: انظر بطاقة «استخدام المعالج».")
        cards.append(_card("sleep", titles["sleep"], summary, details, advice, commands,
                           "warn" if any(results[key] is None for key in ("pmset", "custom", "log")) else "ok"))
        facts["sleep"] = {"settings": custom, "wake_log": log}
    except Exception:
        cards.append(_warn("sleep", titles["sleep"]))
    try:
        if results["assertions"] is None:
            raise ValueError("assertions unavailable")
        blockers = parse_assertions(results["assertions"])
        detail = [f"{name}: {count} مانع" for name, count in sorted(blockers.items())]
        cards.append(_card("awake_blockers", titles["awake_blockers"],
                           "تطبيقات تمنع الجهاز من النوم." if blockers else "لا تظهر تطبيقات معروفة تمنع النوم.",
                           detail, ["أغلق خيار إبقاء الجهاز مستيقظًا من إعداد التطبيق إن لم تكن تحتاجه."] if blockers else [], status="ok"))
        facts["awake_blockers"] = blockers
    except Exception:
        cards.append(_warn("awake_blockers", titles["awake_blockers"]))

    try:
        sysfacts = parse_sysctl(results["sysctl"] or "")
        if results["boot"]:
            sysfacts.update(parse_sysctl(results["boot"]))
        swap = sysfacts.get("swap")
        if swap is None:
            raise ValueError("swap unavailable")
        free = parse_memory_pressure(results["pressure"] or "")
        uptime_days = (max(0, (time.time() - sysfacts["boot_epoch"]) / 86400)
                       if sysfacts.get("boot_epoch") else parse_uptime_days(results["uptime"] or ""))
        facts.update({"ram_bytes": sysfacts.get("ram_bytes"), "cpu_count": sysfacts.get("cpu_count"),
                      "cpu": sysfacts.get("cpu"), "swap": swap, "free_percent": free, "uptime_days": uptime_days})
        details = [f"الرام: {sysfacts.get('ram_bytes', 0) / 1024**3:.1f} غيغابايت." if sysfacts.get("ram_bytes") else "سعة الرام غير متاحة.",
                   f"الذاكرة الإضافية المستخدمة: {swap['used_gb']:.1f} غيغابايت.",
                   f"الذاكرة المتاحة: {free}% تقريبًا." if free is not None else "نسبة الذاكرة المتاحة غير متاحة.",
                   f"منذ آخر تشغيل: {uptime_days:.1f} يوم." if uptime_days is not None else "مدة التشغيل غير متاحة."]
        warn = swap["used_gb"] > 4 or (uptime_days is not None and uptime_days > 7)
        measurement_incomplete = (free is None or results["uptime"] is None or results["boot"] is None
                                  or sysfacts.get("ram_bytes") is None)
        cards.append(_card("memory", titles["memory"], "إعادة التشغيل الأسبوعية قد تريح الذاكرة إذا طال التشغيل." if warn else "استخدام الذاكرة ضمن الحدود المعتادة.", details,
                           ["أعد تشغيل الجهاز مرة أسبوعيًا؛ كأنك تبدأ صفحة جديدة لتفريغ الذاكرة المؤقتة."] if warn else [], status="warn" if warn or measurement_incomplete else "ok"))
    except Exception:
        cards.append(_warn("memory", titles["memory"]))
    try:
        if results["ps"] is None:
            raise ValueError("process list unavailable")
        apps = group_rss(results["ps"])
        ai_names = {"Claude", "ChatGPT", "Gemini", "Perplexity", "Codex", "Antigravity", "OpenCode", "Hermes"}
        ai_count = sum(1 for app in apps if app["name"] in ai_names)
        facts["top_apps"] = apps
        cards.append(_card("top_apps", titles["top_apps"], f"عدد تطبيقات الذكاء الاصطناعي المفتوحة: {ai_count}.",
                           [f"{app['name']}: {app['rss_mb']:.0f} ميغابايت" for app in apps],
                           ["أغلق التطبيقات التي لا تحتاجها عبر ⌘Q لتوفير الذاكرة."] if ai_count > 1 else []))
    except Exception:
        cards.append(_warn("top_apps", titles["top_apps"]))
    try:
        if results["ps"] is None:
            raise ValueError("process list unavailable")
        hogs = parse_cpu_hogs(results["ps"])
        details = []
        for proc in hogs:
            note = ("مزامنة سحابية تفحص الملفات." if proc["name"] in {"fileproviderd", "OneDrive"} else
                    "فهرسة Spotlight؛ غالبًا مؤقتة بعد إعادة التشغيل." if proc["name"] in {"mds", "mds_stores", "mdworker", "corespotlightd"} else
                    "آلة افتراضية خاصة بعزل Claude؛ اتركها تعمل." if proc["name"] == "com.apple.Virtualization.VirtualMachine" else "")
            details.append(f"{proc['name']}: {proc['cpu_percent']:.0f}%" + (f" — {note}" if note else ""))
        cards.append(_card("cpu_hogs", titles["cpu_hogs"], "عمليات تستخدم أكثر من نصف معالج واحد." if hogs else "لا توجد عملية تتجاوز 50% حاليًا.", details))
        facts["cpu_hogs"] = hogs
    except Exception:
        cards.append(_warn("cpu_hogs", titles["cpu_hogs"]))
    try:
        if results["disk"] is None:
            raise ValueError("disk unavailable")
        disk = parse_disk(results["disk"])
        warn = disk["free_gb"] < 100 or disk["free_percent"] < 15
        cards.append(_card("disk", titles["disk"], f"المتاح {disk['free_gb']:.1f} غيغابايت ({disk['free_percent']}%).",
                           advice=["حاول إبقاء 100 غيغابايت أو 15% على الأقل فارغة لتعمل التحديثات بسلاسة."] if warn else [], status="warn" if warn else "ok"))
        facts["disk"] = disk
    except Exception:
        cards.append(_warn("disk", titles["disk"]))
    try:
        if results["login"] is None:
            raise ValueError("login items unavailable")
        items = parse_login_items(results["login"])
        cards.append(_card("login_items", titles["login_items"], f"عدد التطبيقات التي تفتح عند تسجيل الدخول: {len(items)}.", items,
                           ["راجع القائمة من إعدادات النظام إذا كان بدء التشغيل بطيئًا."] if items else []))
        facts["login_items"] = items
    except Exception:
        cards.append(_warn("login_items", titles["login_items"]))
    return {"cards": cards, "facts": facts}


def scan() -> dict:
    """Never let a host-specific parsing or subprocess issue escape to the caller."""
    try:
        return _scan()
    except Exception:
        return {"cards": [_warn(card_id, title) for card_id, title in (
            ("sleep", "النوم والاستيقاظ"), ("awake_blockers", "تطبيقات تمنع النوم"),
            ("memory", "الذاكرة والرام"), ("top_apps", "أكثر التطبيقات استخدامًا للذاكرة"),
            ("cpu_hogs", "استخدام المعالج"), ("disk", "مساحة القرص"),
            ("login_items", "عناصر بدء التشغيل"))], "facts": {}}
