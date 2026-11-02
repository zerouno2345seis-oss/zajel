"""اختبار آلي لحارس مساعد زاجل: يشغّل الخادم على منفذ مؤقت وبيانات مؤقتة، ويعمل على مجلدات ~/__pb_qa* وحدها.
التشغيل: python3 test_agent.py"""
import json, os, shutil, stat, subprocess, sys, tempfile, time, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PORT = 8871
DATA = Path(tempfile.mkdtemp(prefix="pb_agent_data_"))
QA = Path.home() / "__pb_qa_agent"
BASE = f"http://127.0.0.1:{PORT}"
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print("  ✔", name)
    else:
        fail += 1; print("  ✘", name, extra)


def req(method, path, body=None, key=None, origin=True):
    h = {"Content-Type": "application/json"}
    if origin:
        h["Origin"] = BASE
    if key:
        h["X-Zajel-Key"] = key
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


shutil.rmtree(QA, ignore_errors=True)
(QA / "src").mkdir(parents=True); (QA / "dst").mkdir(); (QA / "mv").mkdir(); (QA / "other").mkdir()
(QA / "src" / "a.txt").write_text("hello"); (QA / "src" / "b.txt").write_text("world"); (QA / "src" / "tahqiq_note.txt").write_text("x")
rel = lambda *p: "__pb_qa_agent/" + "/".join(p)

env = dict(os.environ, PB_PORT=str(PORT), PB_DATA=str(DATA), PB_AGENT_EXPIRY="5", PB_AGENT_RED_LIMIT="200", PB_EXPORT_DIR=str(DATA / "exports"))
srv = subprocess.Popen([sys.executable, str(HERE / "samsung_backup_web.py"), "--no-browser"], env=env, cwd=str(HERE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=1); break
        except Exception:
            time.sleep(0.5)
    print("— المفتاح والمنفذ")
    kf = DATA / ".agent_key"
    key = kf.read_text()
    check("ملف المفتاح بصلاحية صاحبه وحده", stat.S_IMODE(kf.stat().st_mode) == 0o600)
    check("رقم المنفذ مكتوب", (DATA / ".zajel_port").read_text() == str(PORT))
    check("بلا مفتاح ← 401", req("GET", "/api/agent/tools")[0] == 401)
    check("مفتاح خاطئ ← 401", req("GET", "/api/agent/tools", key="x" * 43)[0] == 401)
    check("طلب call بلا مفتاح ← 401", req("POST", "/api/agent/call", {"tool": "places"})[0] == 401)
    c, d = req("GET", "/api/agent/tools", key=key)
    tiers = {t["name"]: t["tier"] for t in d["tools"]}
    check("القائمة بدرجاتها", c == 200 and tiers["search"] == "green" and tiers["copy_items"] == "yellow" and tiers["move_items"] == "red")
    check("لا أداة فرمتة ولا طرفية في القائمة", not any(n in tiers for n in ("format_disk", "run_command", "shell", "cloud_account")))
    call = lambda tool, args=None: req("POST", "/api/agent/call", {"tool": tool, "args": args or {}}, key=key, origin=False)[1]

    print("— أخضر")
    r = call("places")
    check("دليل الأماكن فيه مجلدات وأجهزة", r.get("ok") and r["result"]["folders"] and r["result"]["devices"])
    r = call("list_folder", {"place": "home", "path": rel("src")})
    check("عرض مجلد", r.get("ok") and r["result"]["count"] == 3, r)
    r = call("search", {"q": "tahqiq", "place": "home", "path": rel("")})
    check("بحث يجد الملف", r.get("ok") and r["result"]["count"] >= 1, r)
    check("حالة", call("status").get("ok"))
    check("قائمة العمليات", call("list_ops").get("ok"))

    print("— أصفر (ينفَّذ فورًا)")
    r = call("make_folder", {"place": "home", "parent": rel("dst"), "name": "جديد"})
    time.sleep(1)
    check("مجلد جديد", r.get("ok") and (QA / "dst" / "جديد").is_dir(), r)
    r = call("copy_items", {"from_place": "home", "paths": [rel("src", "a.txt")], "to_place": "home", "to_dir": rel("dst")})
    oid = r.get("result", {}).get("id")
    w = call("wait_op", {"id": oid, "seconds": 20}) if oid else {}
    check("نسخ ينفَّذ بلا موافقة", (QA / "dst" / "a.txt").exists() and (QA / "src" / "a.txt").exists(), (r, w))
    r = call("create_sync", {"name": "تجربة ١", "locations": [{"place": "home", "path": rel("dst")}, {"place": "home", "path": rel("other")}]})
    check("إنشاء مزامنة جديدة (أصفر)", r.get("ok"), r)

    print("— أحمر (لا يُنفَّذ بلا موافقة الواجهة)")
    r = call("move_items", {"from_place": "home", "paths": [rel("src", "b.txt")], "to_place": "home", "to_dir": rel("mv")})
    pid = r.get("id")
    check("النقل يعود معلّقًا برقم ومعاينة", r.get("pending") and pid and r["preview"]["count"] == 1 and r["preview"]["bytes"] == 5, r)
    time.sleep(1)
    check("الملف لم يتحرك", (QA / "src" / "b.txt").exists() and not (QA / "mv" / "b.txt").exists())
    check("الوكيل لا يستطيع الموافقة (طلب بمفتاحه ← 403)", req("POST", "/api/assistant/approve", {"id": pid}, key=key)[0] == 403)
    check("الموافقة بلا Origin ← 403", req("POST", "/api/assistant/approve", {"id": pid}, origin=False)[0] == 403)
    check("ما زال لم يتحرك", (QA / "src" / "b.txt").exists())
    c, d = req("GET", "/api/assistant/pending")
    check("الواجهة ترى المعلّق وصلاحيته", c == 200 and any(p["id"] == pid and 0 < p["expires_in"] <= 5 for p in d["pending"]), d)
    check("حالة الموافقة للوكيل: pending", call("approval_status", {"id": pid})["result"]["state"] == "pending")
    c, d = req("POST", "/api/assistant/approve", {"id": pid})
    oid = (d.get("result") or {}).get("id")
    if oid:
        call("wait_op", {"id": oid, "seconds": 20})
    check("بعد موافقة الواجهة ينتقل الملف", c == 200 and (QA / "mv" / "b.txt").exists() and not (QA / "src" / "b.txt").exists(), d)
    check("حالة الموافقة: approved", call("approval_status", {"id": pid})["result"]["state"] == "approved")
    check("لا يُوافَق مرتين", req("POST", "/api/assistant/approve", {"id": pid})[0] == 400)

    r = call("delete_items", {"place": "home", "paths": [rel("src", "tahqiq_note.txt")]})
    d2 = r.get("id")
    check("الحذف معلّق", r.get("pending") and (QA / "src" / "tahqiq_note.txt").exists())
    check("الرفض يُسقطه", req("POST", "/api/assistant/deny", {"id": d2})[0] == 200 and (QA / "src" / "tahqiq_note.txt").exists())
    r = call("rename_items", {"place": "home", "items": [{"path": rel("mv", "b.txt"), "new_name": "c.txt"}]})
    check("إعادة التسمية معلّقة", r.get("pending") and (QA / "mv" / "b.txt").exists())
    r = call("move_items", {"from_place": "home", "paths": [rel("mv", "b.txt")], "to_place": "home", "to_dir": rel("other")})
    ex = r.get("id")
    time.sleep(6)
    c, d = req("POST", "/api/assistant/approve", {"id": ex})
    check("انتهاء صلاحية المعلّق (بعد المهلة)", c == 400 and (QA / "mv" / "b.txt").exists() and call("approval_status", {"id": ex})["result"]["state"] == "expired", d)
    r = call("phone_delete", {"paths": ["/sdcard/__pb_qa_nonexistent_zzz"]})
    pp = r.get("id")
    c, d = req("POST", "/api/assistant/approve", {"id": pp})
    check("الحذف من الهاتف يطلب كلمة تأكيد", r.get("pending") and pp and c == 400 and "احذف" in d.get("error", ""), d)
    req("POST", "/api/assistant/deny", {"id": pp})

    print("— ممنوع")
    for name in ("format_disk", "cloud_account", "run_command"):
        r = call(name, {})
        check(f"{name} مرفوض", r.get("refused"), r)
    check("مجلد Library مرفوض", "error" in call("list_folder", {"place": "home", "path": "Library/Preferences"}))
    check("مجلد ssh مرفوض", "error" in call("delete_items", {"place": "home", "paths": [".ssh/id_rsa"]}))
    check("مسار فيه نقطتين مرفوض", "error" in call("list_folder", {"place": "home", "path": "../x"}))
    check("مسار نظام مطلق مرفوض", "error" in call("list_folder", {"place": "home", "path": "/System/Library"}))
    check("نقل إلى مجلد نظام مرفوض", "error" in call("move_items", {"from_place": "home", "paths": [rel("mv", "b.txt")], "to_place": "home", "to_dir": "Library"}))
    check("أداة مجهولة ← خطأ", "error" in call("nope"))
    check("المسارات المطلقة كمكان مرفوضة", "error" in call("list_folder", {"place": "/etc", "path": ""}))

    print("— حفظ مزامنة واحدة لا يمسح غيرها")
    call("create_sync", {"name": "تجربة ٢", "locations": [{"place": "home", "path": rel("src")}, {"place": "home", "path": rel("mv")}]})
    g = req("GET", "/api/sync")[1]["groups"]
    check("مزامنتان موجودتان", len(g) == 2, g)
    g1 = next(x for x in g if x["name"] == "تجربة ١")
    c, d = req("POST", "/api/sync/item", {"op": "upsert", "group": g1 | {"every": 77}})
    g = req("GET", "/api/sync")[1]["groups"]
    check("تعديل واحدة يبقي الأخرى", c == 200 and len(g) == 2 and next(x for x in g if x["id"] == g1["id"])["every"] == 77, g)
    r = call("create_sync", {"name": "خطرة", "deletes": True, "locations": [{"place": "home", "path": rel("dst")}, {"place": "home", "path": rel("other")}]})
    check("مزامنة تنقل الحذف ← حمراء معلّقة", r.get("pending") and len(req("GET", "/api/sync")[1]["groups"]) == 2, r)
    req("POST", "/api/assistant/deny", {"id": r["id"]})
    r = call("delete_sync", {"id": g1["id"]})
    check("حذف مزامنة ← معلّق", r.get("pending") and len(req("GET", "/api/sync")[1]["groups"]) == 2)
    req("POST", "/api/assistant/approve", {"id": r["id"]})
    g = req("GET", "/api/sync")[1]["groups"]
    check("بعد الموافقة تُحذف واحدة فقط", len(g) == 1 and g[0]["name"] == "تجربة ٢", g)
    c, d = req("POST", "/api/migrate/item", {"op": "delete", "id": "nope"})
    check("حذف قاعدة ترحيل غير موجودة ← خطأ بلا مسح", c == 400)

    print("— مصادر المساعد والنماذج")
    c, d = req("GET", "/api/assistant/agents")
    ag = {a["id"]: a for a in d.get("agents", [])}
    check("الأساسي هو Antigravity", ag.get("agy", {}).get("default") and set(ag) >= {"agy", "codex", "claude", "pi", "hermes", "opencode"}, list(ag))
    c, d = req("POST", "/api/assistant/settings", {"agent": "codex", "model": "bad model; rm -rf"})
    check("معرّف نموذج مشبوه مرفوض", c == 400)
    c, d = req("POST", "/api/assistant/settings", {"agent": "codex", "model": "gpt-6-luna", "effort": "high"})
    check("حفظ نموذج وجهد", c == 200 and d["settings"]["models"]["codex"] == "gpt-6-luna" and d["settings"]["efforts"]["codex"] == "high", d)
    c, d = req("POST", "/api/assistant/settings", {"default_agent": "claude"})
    check("تغيير المصدر الأساسي", d["settings"]["default_agent"] == "claude")
    req("POST", "/api/assistant/settings", {"default_agent": "agy"})
    check("إعدادات المساعد ترفض مفتاح الوكيل", req("POST", "/api/assistant/settings", {"default_agent": "agy"}, key="x")[0] == 403)
    c, d = req("POST", "/api/assistant/models/refresh", {"agent": "agy"})
    check("تحديث نماذج وكيل واحد", c == 200 and d["result"]["agy"]["ok"], d)
    c, d = req("POST", "/api/assistant/chat", {"agent": "agy", "text": "x", "model": "a b"})
    check("محادثة بنموذج غير صالح ← رفض", c == 400)

    print("— الذاكرة والمحادثات والأوامر الجاهزة")
    r = call("remember", {"text": "مجلد الرسالة هو المستندات/رسالة"})
    check("أداة remember تحفظ حقيقة", r.get("ok") and "الرسالة" in r["result"]["saved"], r)
    mem = req("GET", "/api/assistant/memory")[1]["memory"]
    check("الذاكرة تظهر وموسومة تلقائية", len(mem) == 1 and mem[0]["auto"])
    check("رفض حفظ كلمة مرور", req("POST", "/api/assistant/memory/add", {"text": "my password is 1234"})[0] == 400)
    m2 = req("POST", "/api/assistant/memory/add", {"text": "أفضّل الردود القصيرة جدًا"})[1]["memory"]
    req("POST", "/api/assistant/memory/delete", {"id": m2[-1]["id"]})
    check("حذف عنصر من الذاكرة", len(req("GET", "/api/assistant/memory")[1]["memory"]) == 1)
    pr = req("POST", "/api/assistant/prompts/save", {"title": "نسخة احتياطية", "text": "زامن الصور مع القرص"})[1]["prompts"]
    check("حفظ أمر جاهز", len(pr) == 1 and pr[0]["title"] == "نسخة احتياطية")
    req("POST", "/api/assistant/prompts/save", {"id": pr[0]["id"], "title": "نسخة", "text": "x y z w"})
    check("تعديل أمر جاهز", req("GET", "/api/assistant/prompts")[1]["prompts"][0]["title"] == "نسخة")
    check("حفظ أمر بلا نص مرفوض", req("POST", "/api/assistant/prompts/save", {"title": "a", "text": ""})[0] == 400)
    req("POST", "/api/assistant/prompts/delete", {"id": pr[0]["id"]})
    check("حذف أمر جاهز", req("GET", "/api/assistant/prompts")[1]["prompts"] == [])
    import importlib, assistant_store as _S
    _S.init(DATA)
    _S.chat_append("c1", "agy", "m", {"role": "user", "text": "ابحث عن ملف"})
    _S.chat_append("c1", "agy", "m", {"role": "assistant", "text": "وجدته"}, session="sess9", n=1)
    ch = req("GET", "/api/assistant/chats")[1]["chats"]
    check("المحادثة محفوظة بعنوانها", len(ch) == 1 and ch[0]["title"] == "ابحث عن ملف" and ch[0]["count"] == 2, ch)
    check("استرجاع محادثة بكامل رسائلها", len(req("GET", "/api/assistant/chat/get?id=c1")[1]["messages"]) == 2)
    check("جلسة الوكيل تُستعاد بعد إعادة التشغيل", _S.chat_session("c1")["session"] == "sess9")
    req("POST", "/api/assistant/chat/rename", {"id": "c1", "title": "بحثي"})
    check("إعادة تسمية", req("GET", "/api/assistant/chats")[1]["chats"][0]["title"] == "بحثي")
    req("POST", "/api/assistant/chat/delete", {"id": "c1"})
    check("حذف محادثة", req("GET", "/api/assistant/chats")[1]["chats"] == [])

    print("— فتح المجلد في زاجل")
    check("بداية قائمة الفتح فارغة", req("GET", "/api/assistant/nav?after=-1")[1]["seq"] == 0)
    r = call("open_in_zajel", {"place": "home", "path": rel("src")})
    check("أداة الفتح تنجح", r.get("ok") and r["result"]["opened"] == "zajel", r)
    nv = req("GET", "/api/assistant/nav?after=0")[1]
    check("الطلب يصل للواجهة بمكانه ومساره", nv["seq"] == 1 and nv["items"][0]["path"] == rel("src") and nv["items"][0]["place"] == "home", nv)
    check("لا يُعاد الطلب بعد التقاطه", req("GET", "/api/assistant/nav?after=1")[1]["items"] == [])
    check("فتح مجلد النظام مرفوض", "error" in call("open_in_zajel", {"place": "home", "path": "Library/Keychains"}))

    print("— ذاكرة تتعلم وتنظّف")
    for r in req("GET", "/api/assistant/memory")[1]["memory"]:
        req("POST", "/api/assistant/memory/delete", {"id": r["id"]})
    a1 = _S.memory_add("شهاداتي في ملفاتي/شهادات", auto=True, kind="alias")
    a2 = _S.memory_add("أفضّل الردود القصيرة", auto=True, kind="preference")
    a3 = _S.memory_add("معلومة قديمة غير مستعملة", auto=True)
    req("POST", "/api/assistant/memory/pin", {"id": a2["id"], "pinned": True})
    check("تثبيت عنصر", [r for r in _S.memory_list() if r["id"] == a2["id"]][0]["pinned"])
    d = _S.memory_apply_ops({"delete": [a2["id"], a3["id"]], "update": [{"id": a1["id"], "text": "شهاداتي في ملفاتي/شهادات (PDF)"}],
                             "add": [{"text": "my password is 123", "kind": "fact"}, {"text": "يفضّل البحث في كل السحابات", "kind": "preference"}]})
    texts = [r["text"] for r in _S.memory_list()]
    check("المنظِّم لا يحذف المثبّت", a2["text"] in texts and d["delete"] == 1, d)
    check("المنظِّم يعدّل ويضيف ويرفض كلمة المرور", d["update"] == 1 and d["add"] == 1 and not any("password" in t for t in texts), texts)
    pr = _S.memory_prompt("أين شهاداتي؟")
    check("الذاكرة المحقونة ترتّب بالصلة بالطلب", pr.index("شهاداتي") < pr.index("يفضّل البحث") if "يفضّل البحث" in pr else "شهاداتي" in pr, pr)
    _S.chat_append("old1", "agy", "m", {"role": "user", "text": "ابحث عن شهادة الميلاد في السحابة"})
    _S.chat_append("old1", "agy", "m", {"role": "assistant", "text": "وجدتها في drive/وثائق", "state": "done"})
    sim = _S.similar_exchanges("أين شهادة الميلاد؟", "other")
    check("استرجاع طلب سابق مشابه مع جوابه", "وثائق" in sim, sim)
    check("لا يسترجع من المحادثة نفسها", _S.similar_exchanges("أين شهادة الميلاد؟", "old1") == "")
    rows = _S.memory_list(); rows[0]["auto"] = True; rows[0]["pinned"] = False; rows[0]["uses"] = 0; rows[0]["last_used"] = 1
    _S._save("assistant_memory.json", rows)
    check("التنظيف الحتمي يحذف القديم غير المستعمل", _S.memory_gc() >= 1)
    req("POST", "/api/assistant/chat/delete", {"id": "old1"})

    print("— الأتمتة")
    old = time.time() - 600
    def mk(path, text="x", folder=False, age=600):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True) if folder else path.write_text(text)
        os.utime(path, (time.time() - age, time.time() - age))
    (QA / "watch").mkdir(); (QA / "arch").mkdir()
    W = rel("watch")
    mk(QA / "watch" / "old.txt")
    bad = call("create_automation", {"name": "x", "every_minutes": 1, "watch_place": "home", "watch_path": W})
    check("مدة أقل من الحد ← خطأ", "error" in bad, bad)
    bad = call("create_automation", {"name": "x", "every_minutes": 20, "watch_place": "home", "watch_path": W, "actions": [{"type": "delete"}]})
    check("لا إجراء حذف في الأتمتة", "error" in bad, bad)
    bad = call("create_automation", {"name": "x", "every_minutes": 20, "watch_place": "home", "watch_path": W, "actions": [{"type": "move", "to_place": "home", "to_path": rel("watch", "sub")}]})
    check("وجهة داخل المراقَب ← خطأ (منع الدوران)", "error" in bad, bad)
    r = call("create_automation", {"name": "نبّهني", "every_minutes": 20, "watch_place": "home", "watch_path": W})
    check("قاعدة إشعار فقط أصفر تُنشأ مباشرة", r.get("ok") and r["tier"] == "yellow", r)
    rid = r["result"]["id"]
    check("أول فحص خط أساس لا يعدّ الموجود جديدًا", "بدأت" in call("run_automation_now", {"id": rid})["result"]["note"])
    check("لا إشعار بعد خط الأساس", not req("GET", "/api/assistant/automations")[1]["notices"])
    mk(QA / "watch" / "new1.txt"); mk(QA / "watch" / "part.crdownload"); mk(QA / "watch" / "fresh.txt", age=5)
    note = call("run_automation_now", {"id": rid})["result"]["note"]
    d = req("GET", "/api/assistant/automations")[1]
    check("يلتقط الجديد المستقر فقط", "new1.txt" in note and "part" not in note and "fresh" not in note and len(d["notices"]) == 1, note)
    check("نفس العنصر لا يُبلَّغ مرتين", "لا جديد" in call("run_automation_now", {"id": rid})["result"]["note"])
    mk(QA / "watch" / "fresh.txt", age=600)
    check("الملف الذي استقر يُلتقط في الدورة التالية", "fresh.txt" in call("run_automation_now", {"id": rid})["result"]["note"])
    r = call("create_automation", {"name": "انقل", "every_minutes": 20, "watch_place": "home", "watch_path": W, "kind": "folders",
                                   "actions": [{"type": "notify"}, {"type": "move", "to_place": "home", "to_path": rel("arch")}]})
    check("قاعدة فيها نقل ← تنتظر موافقة بمعاينة", r.get("pending") and "نقل" in json.dumps(r["preview"], ensure_ascii=False), r)
    check("لم تُنشأ قبل الموافقة", len(req("GET", "/api/assistant/automations")[1]["rules"]) == 1)
    c, d = req("POST", "/api/assistant/approve", {"id": r["id"]})
    mid = d["result"]["id"]
    check("بعد الموافقة تُنشأ", c == 200 and len(req("GET", "/api/assistant/automations")[1]["rules"]) == 2, d)
    call("run_automation_now", {"id": mid})
    mk(QA / "watch" / "dirA", folder=True); mk(QA / "watch" / "late.txt")
    note = call("run_automation_now", {"id": mid})["result"]["note"]
    check("ينقل المجلد الجديد فقط (الملفات لا)", "dirA" in note and "late" not in note, note)
    time.sleep(3)
    check("المجلد وصل الوجهة وغاب من المصدر", (QA / "arch" / "dirA").exists() and not (QA / "watch" / "dirA").exists() and (QA / "watch" / "late.txt").exists())
    check("التعطيل", req("POST", "/api/assistant/automations/toggle", {"id": mid, "enabled": False})[0] == 200
          and not [x for x in req("GET", "/api/assistant/automations")[1]["rules"] if x["id"] == mid][0]["enabled"])
    r = call("delete_automation", {"id": mid})
    check("حذف القاعدة أحمر ينتظر موافقة", r.get("pending"), r)
    req("POST", "/api/assistant/deny", {"id": r["id"]})
    check("الإشعارات تُقرأ", req("POST", "/api/assistant/notices/read", {})[0] == 200 and all(n["read"] for n in req("GET", "/api/assistant/automations")[1]["notices"]))
    check("حالة الهاتف متاحة", "connected" in json.dumps(call("phone_status")) or call("phone_status").get("ok"))

    print("— السكربتات والتفويض")
    r = call("write_script", {"name": "../evil.py", "title": "عنوان اختبار", "code": "print(1)", "description": "x"})
    check("اسم سكربت بمسار ← خطأ", "error" in r, r)
    r = call("write_script", {"name": "bad.py", "title": "عنوان اختبار", "code": "def (:", "description": "x"})
    check("خطأ صياغة يُرفض عند الكتابة", "error" in r, r)
    r = call("write_script", {"name": "hello.py", "title": "عنوان اختبار", "code": "import sys, shutil\nprint('PBQA-OK', sys.argv[1:])\nshutil.rmtree('/nonexistent-qa', ignore_errors=True)\n", "description": "يطبع علامة اختبار"})
    check("كتابة السكربت أصفر ولا يشغّله ويرصد الخطر", r.get("ok") and r["tier"] == "yellow" and "حذف مجلدات (rmtree)" in r["result"]["flags"], r)
    check("القائمة تحتويه", any(x["name"] == "hello.py" for x in call("list_scripts")["result"]["scripts"]))
    r = call("run_script", {"name": "nope.py"})
    check("تشغيل غير موجود ← خطأ", "error" in r, r)
    r = call("run_script", {"name": "hello.py", "args": ["a1"]})
    check("تشغيل السكربت أحمر ومعاينته تعرض الكود والتنبيه", r.get("pending") and "PBQA-OK" in json.dumps(r["preview"], ensure_ascii=False) and r["preview"]["script"]["flags"], r)
    (DATA / "scripts" / "hello.py").write_text("print('TAMPERED')\n")
    c, d = req("POST", "/api/assistant/approve", {"id": r["id"]})
    check("تغيير النص بعد الطلب يُبطل الموافقة", c >= 400 and "تغيّر" in json.dumps(d, ensure_ascii=False), d)
    call("write_script", {"name": "hello.py", "title": "عنوان اختبار", "code": "import sys, os\nprint('PBQA-OK', sys.argv[1:], 'SER' if 'ZAJEL_ADB_SERIAL' in os.environ else 'NOSER')\n", "description": "يطبع علامة اختبار"})
    r = call("run_script", {"name": "hello.py", "args": ["a1"]})
    c, d = req("POST", "/api/assistant/approve", {"id": r["id"]})
    rid = d["result"]["run"]
    for _ in range(40):
        st = call("script_status", {"run": rid})["result"]
        if st["state"] != "running":
            break
        time.sleep(0.25)
    check("السكربت المعتمد يعمل ويحفظ ناتجه", st["state"] == "done" and "PBQA-OK ['a1'] SER" in st["output_tail"], st)
    time.sleep(0.3)
    check("انتهاء السكربت يظهر عملية مكتملة (رسالتها تكفي عن إشعار مكرر)", any(x["title"] == "سكربت: hello.py" and x["state"] == "done" for x in req("GET", "/api/ops/list")[1]["ops"]))
    code = "import time\nfor i in range(1, 4):\n    print(f'ZAJEL_PROGRESS {i}/3 ملف{i}', flush=True)\n    time.sleep(1.2)\nprint('ZAJEL_RESULT نُسخ 3 وفشل 0', flush=True)\n"
    call("write_script", {"name": "prog.py", "title": "عنوان اختبار", "code": code, "description": "اختبار التقدم"})
    r = call("run_script", {"name": "prog.py"})
    req("POST", "/api/assistant/approve", {"id": r["id"]})
    seen_prog = None
    for _ in range(30):
        ops = req("GET", "/api/ops/list")[1]["ops"]
        o = next((x for x in ops if x["title"] == "سكربت: prog.py"), None)
        if o and o["state"] == "running" and o["total"] == 3 and o["done"] >= 1:
            seen_prog = o
            break
        time.sleep(0.3)
    check("السكربت يظهر في لوحة العمليات بعدّاد حي", seen_prog and seen_prog["current"].startswith("ملف"), seen_prog)
    for _ in range(30):
        o = next(x for x in req("GET", "/api/ops/list")[1]["ops"] if x["title"] == "سكربت: prog.py")
        if o["state"] != "running":
            break
        time.sleep(0.3)
    check("تنتهي بخلاصة السكربت", o["state"] == "done" and "نُسخ 3" in o["detail"], o)
    call("write_script", {"name": "slow.py", "title": "عنوان اختبار", "code": "import time\nprint('ZAJEL_PROGRESS 0/5 بدأ', flush=True)\ntime.sleep(60)\n", "description": "بطيء"})
    r = call("run_script", {"name": "slow.py"})
    req("POST", "/api/assistant/approve", {"id": r["id"]})
    time.sleep(1.5)
    o = next(x for x in req("GET", "/api/ops/list")[1]["ops"] if x["title"] == "سكربت: slow.py")
    req("POST", "/api/ops/cancel", {"id": o["id"]})
    for _ in range(20):
        o = next(x for x in req("GET", "/api/ops/list")[1]["ops"] if x["title"] == "سكربت: slow.py")
        if o["state"] != "running":
            break
        time.sleep(0.3)
    check("زر الإلغاء يوقف السكربت", o["state"] == "cancelled", o)
    call("delete_script", {"name": "prog.py"}); call("delete_script", {"name": "slow.py"})
    r = call("write_script", {"name": "lib.py", "title": "نسخ صور السنة", "tags": ["صور", "نسخ"], "code": "print('LIB')\n", "description": "اختبار المكتبة"})
    check("سكربت بعنوان ووسوم", r.get("ok"), r)
    L = req("GET", "/api/assistant/scripts")[1]["scripts"]
    it = next((x for x in L if x["name"] == "lib.py"), None)
    check("المكتبة تعرض العنوان والوسوم", it and it["title"] == "نسخ صور السنة" and it["tags"] == ["صور", "نسخ"], L)
    check("write_script بلا عنوان ← خطأ", "error" in call("write_script", {"name": "x.py", "code": "print(1)", "description": "d"}))
    c, d = req("POST", "/api/assistant/scripts/meta", {"name": "lib.py", "title": "عنوان جديد", "description": "وصف", "tags": "أ، ب"})
    check("تعديل البيانات الوصفية", c == 200 and next(x for x in d["scripts"] if x["name"] == "lib.py")["title"] == "عنوان جديد" and next(x for x in d["scripts"] if x["name"] == "lib.py")["tags"] == ["أ", "ب"], d)
    g = req("GET", "/api/assistant/scripts/get?name=lib.py")[1]
    check("فتح السكربت يعيد الكود والبصمة", "LIB" in g["code"] and g["sha"])
    check("التشغيل من المكتبة بلا بصمة ← رفض", req("POST", "/api/assistant/scripts/run", {"name": "lib.py"})[0] >= 400)
    check("التشغيل من المكتبة بالمفتاح ← 403", req("POST", "/api/assistant/scripts/run", {"name": "lib.py", "sha": g["sha"]}, key=key, origin=False)[0] in (401, 403))
    c, d = req("POST", "/api/assistant/scripts/run", {"name": "lib.py", "sha": g["sha"]})
    check("التشغيل من المكتبة بعد رؤية الكود", c == 200 and d.get("run"), d)
    time.sleep(1.2)
    check("عدّاد التشغيل يزيد", next(x for x in req("GET", "/api/assistant/scripts")[1]["scripts"] if x["name"] == "lib.py")["runs"] == 1)
    check("حذف من المكتبة", req("POST", "/api/assistant/scripts/delete", {"name": "lib.py"})[0] == 200)
    print("— تعديل القواعد المحفوظة")
    import assistant_store as _S2, agent_runner as _R2
    _S2.init(DATA) if hasattr(_S2, "init") else None
    rule = req("POST", "/api/assistant/memory/add", {"text": "لا تحذف مجلد الصور القديمة أبدًا", "kind": "preference"})[1]
    mem = req("GET", "/api/assistant/memory")[1]["memory"]
    rid_ = next(x["id"] for x in mem if "الصور القديمة" in x["text"])
    check("list_memory يعرض القاعدة بمعرّفها", any(x["id"] == rid_ for x in call("list_memory")["result"]["memory"]))
    r = call("update_memory", {"id": rid_, "text": "لا تحذف الصور القديمة إلا بموافقتي"})
    check("تعديل القاعدة أحمر بمعاينة القديم والجديد", r.get("pending") and "بموافقتي" in json.dumps(r["preview"], ensure_ascii=False) and "الصور القديمة" in r["preview"]["target"], r)
    check("لا يتغير قبل الموافقة", any("أبدًا" in x["text"] for x in req("GET", "/api/assistant/memory")[1]["memory"]))
    req("POST", "/api/assistant/approve", {"id": r["id"]})
    check("بعد الموافقة يتغير النص", any("بموافقتي" in x["text"] for x in req("GET", "/api/assistant/memory")[1]["memory"]))
    r = call("forget_memory", {"id": rid_})
    check("نسيان القاعدة أحمر", r.get("pending"))
    req("POST", "/api/assistant/approve", {"id": r["id"]})
    check("بعد الموافقة تُحذف", not any(x["id"] == rid_ for x in req("GET", "/api/assistant/memory")[1]["memory"]))
    check("رسالة حدّ الخمس ساعات تنقل نصّ المصدر وتشرح اشتراك الحساب", "مشترك" in _R2.friendly("5-hour limit reached resets 4am") or "تشاركه" in _R2.friendly("5-hour limit reached resets 4am"))
    print("— الخوادم")
    TP = 8892
    tsrv = subprocess.Popen([sys.executable, "-m", "http.server", str(TP), "--bind", "127.0.0.1"], cwd=str(QA), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    rows = call("list_servers")["result"]["running"]
    mine = next((x for x in rows if TP in x["ports"]), None)
    check("يعرض الخادم الجاري بمنفذه وأمره", mine and "http.server" in mine["command"] and not mine["protected"], rows[:3])
    selfrow = next((x for x in rows if PORT in x["ports"]), None)
    check("زاجل نفسه محميّ", selfrow and selfrow["protected"], selfrow)
    r = call("stop_server", {"pid": selfrow["pid"]}) if selfrow else {}
    check("إيقاف زاجل نفسه مرفوض قبل أي بطاقة", "error" in r, r)
    r = call("stop_server", {"pid": 1})
    check("إيقاف عملية النظام مرفوض", "error" in r, r)
    r = call("stop_server", {"pid": mine["pid"]})
    check("إيقاف خادم أحمر بمعاينة الاسم والمنفذ والأمر", r.get("pending") and str(TP) in r["preview"]["target"] and "http.server" in r["preview"]["note"], r)
    check("لم يتوقف قبل الموافقة", tsrv.poll() is None)
    c, d = req("POST", "/api/assistant/approve", {"id": r["id"]})
    for _ in range(20):
        if tsrv.poll() is not None:
            break
        time.sleep(0.2)
    check("توقف بعد الموافقة وحُفظ أمره", c == 200 and tsrv.poll() is not None and any(x["port"] == TP for x in call("list_servers")["result"]["saved"]), d)
    sid = next(x["id"] for x in call("list_servers")["result"]["saved"] if x["port"] == TP)
    r = call("start_server", {"id": sid})
    check("إعادة التشغيل أحمر", r.get("pending"), r)
    c, d = req("POST", "/api/assistant/approve", {"id": r["id"]})
    time.sleep(1.0)
    check("عاد الخادم يستمع على المنفذ", c == 200 and any(TP in x["ports"] for x in call("list_servers")["result"]["running"]), d)
    again = next(x for x in call("list_servers")["result"]["running"] if TP in x["ports"])
    c, d = req("POST", "/api/assistant/servers/stop", {"pid": again["pid"]})
    check("الإيقاف من الواجهة", c == 200 and d.get("stopped"), d)
    check("الواجهة ترفض إيقاف زاجل", req("POST", "/api/assistant/servers/stop", {"pid": selfrow["pid"]})[0] >= 400)
    check("لا إيقاف من الواجهة بمفتاح الوكيل", req("POST", "/api/assistant/servers/stop", {"pid": 99999}, key=key, origin=False)[0] in (401, 403))
    req("POST", "/api/assistant/servers/forget", {"id": sid})
    try:
        tsrv.kill()
    except Exception:
        pass
    r = call("delegate_task", {"agent": "evil", "task": "x"})
    check("وكيل غير معروف للتفويض ← خطأ", "error" in r, r)
    r = call("delegate_task", {"agent": "agy", "task": "نظّم مجلد التنزيلات"})
    check("التفويض أحمر ينتظر موافقة بنصّ المهمة", r.get("pending") and "التنزيلات" in json.dumps(r["preview"], ensure_ascii=False), r)
    req("POST", "/api/assistant/deny", {"id": r["id"]})
    check("حذف السكربت", call("delete_script", {"name": "hello.py"}).get("ok") and not (DATA / "scripts" / "hello.py").exists())

    print("— معطيات السكربت وتصدير الذاكرة")
    call("write_script", {"name": "par.py", "title": "اختبار معطيات", "code": "import sys\nprint('ARGS', sys.argv[1:])\n", "description": "d",
                          "params": [{"name": "query", "label": "العبارة", "type": "text", "required": True}, {"name": "n", "label": "العدد", "type": "number", "default": "150"}]})
    gp = req("GET", "/api/assistant/scripts/get?name=par.py")[1]
    check("المعطيات المعلنة محفوظة", [q["name"] for q in gp["params"]] == ["query", "n"] and gp["params"][1]["default"] == "150", gp["params"])
    check("حقل مطلوب فارغ ← رفض", req("POST", "/api/assistant/scripts/run", {"name": "par.py", "sha": gp["sha"], "values": {"query": ""}})[0] >= 400)
    check("رقم غير صالح ← رفض", req("POST", "/api/assistant/scripts/run", {"name": "par.py", "sha": gp["sha"], "values": {"query": "اسم الله الوهاب", "n": "الله"}})[0] >= 400)
    c, d = req("POST", "/api/assistant/scripts/run", {"name": "par.py", "sha": gp["sha"], "values": {"query": "اسم الله الوهاب"}})
    time.sleep(1.2)
    import agent_scripts as _AS
    out = open(next(iter(sorted((DATA / "scripts" / "logs").glob("*par.py.log"), key=lambda f: f.stat().st_mtime, reverse=True))), encoding="utf-8").read()
    check("العبارة كاملة موضع واحد والعدد الافتراضي 150", c == 200 and "['اسم الله الوهاب', '150']" in out, out)
    call("delete_script", {"name": "par.py"})
    req("POST", "/api/assistant/memory/add", {"text": "أحب الشرح المختصر", "kind": "preference"})
    c, d = req("POST", "/api/assistant/memory/export", {"format": "md"})
    check("تصدير Markdown مقسّم بالأنواع", c == 200 and "## تفضيلات وقواعد" in d["text"] and Path(d["path"]).exists(), d)
    c, d = req("POST", "/api/assistant/memory/export", {"format": "json"})
    check("تصدير JSON", c == 200 and d["path"].endswith(".json") and json.loads(Path(d["path"]).read_text(encoding="utf-8")), d)

    print("— تحسين الطلب")
    c, d = req("POST", "/api/assistant/improve", {"text": "ab"})
    check("طلب قصير جدًا يُرفض", c == 400, d)
    c, d = req("POST", "/api/assistant/improve", {"text": "اكتب لي سكربت ينقل ملفات"})
    check("بدء التحسين يعيد معرّفًا", c == 200 and d.get("id"), d)
    c, d2 = req("GET", "/api/assistant/improve/get?id=" + str(d.get("id")))
    check("متابعة حالة التحسين", c == 200 and d2.get("state") in ("running", "done", "error"), d2)
    import agent_runner as _AR
    p = _AR.parse_improve('{"type":"script","ar":"أ","en":"a","missing":["كم؟"]}')
    check("تحليل ردّ منظّم", p["type"] == "script" and p["ar"] == "أ" and p["missing"] == ["كم؟"], p)
    check("ردّ غير منظّم لا يُفقد", _AR.parse_improve("نص حر")["ar"] == "نص حر")

    print("— أسئلة ما قبل الإرسال")
    c, d = req("POST", "/api/assistant/clarify", {"text": "تطوير تطبيق"})
    check("بدء قراءة الطلب", c == 200 and d.get("id"), d)
    c, d2 = req("GET", "/api/assistant/clarify/get?id=" + str(d.get("id")))
    check("متابعة حالة القراءة", c == 200 and d2.get("state") in ("running", "done"), d2)
    cp = _AR.parse_clarify('{"needs":true,"questions":[{"q":"أي منصة؟","options":["أندرويد","ويب"]},{"q":""}]}')
    check("تحليل الأسئلة يُسقط الفارغ", cp["needs"] and len(cp["questions"]) == 1, cp)
    check("بلا أسئلة = لا حاجة", not _AR.parse_clarify('{"needs":true,"questions":[]}')["needs"])

    print("— وصف الملفات للتسمية الذكية")
    d = call("describe_files", {"place": "phone", "paths": ["x"]})
    check("الوصف التفصيلي يرفض الهاتف برسالة", "error" in d or "refused" in d, d)
    d = call("describe_files", {"place": "home", "paths": ["../etc"]})
    check("وصف المسار الخارج مرفوض", "error" in d or "refused" in d, d)
    d = call("describe_files", {"place": "home", "paths": [rel("src")]})
    r = d.get("result") or {}
    check("وصف مجلد يعمل", r.get("count") == 1 and r["items"][0].get("is_dir"), d)

    print("— المرفقات والوسائط")
    import media
    # 1. save_upload
    clean_n = media.clean_filename("../../../bad:dir/evil*name?.txt")
    check("save_upload تنظيف الاسم", ".." not in clean_n and ":" not in clean_n and "*" not in clean_n and clean_n.endswith("name.txt"))
    s_err = False
    try:
        media.save_upload(b"1234567890", "small.txt", max_size=5)
    except ValueError:
        s_err = True
    check("save_upload رفض فوق سقف مصغر", s_err)
    u1 = media.save_upload(b"first content", "uniq.txt")
    u2 = media.save_upload(b"second content", "uniq.txt")
    check("save_upload عدم الاستبدال", u1["path"] != u2["path"] and Path(u1["path"]).exists() and Path(u2["path"]).exists())

    # 2. kind_of
    check("kind_of تحديد الأنواع", media.kind_of("f.png") == "image" and media.kind_of("f.mp3") == "audio" and media.kind_of("f.mp4") == "video" and media.kind_of("f.pdf") == "pdf" and media.kind_of("f.docx") == "doc" and media.kind_of("f.txt") == "text")

    # 3. read_any: نص، docx، pdf، وصورة
    t_file = QA / "src" / "test_read.txt"
    t_file.write_text("محتوى تجريبي لقراءة النصوص", encoding="utf-8")
    r_txt = media.read_any(t_file)
    check("read_any لنص", r_txt["kind"] == "text" and "محتوى تجريبي" in r_txt["text"])

    docx_file = QA / "src" / "test_doc.docx"
    try:
        from arabic_docx import ArabicDoc
        ad = ArabicDoc()
        ad.add_para("فقرة تجريبية في مستند وورد")
        ad.save(str(docx_file))
    except Exception:
        media.convert(t_file, "docx", out_dir=QA / "src")
        docx_file = QA / "src" / "test_read.docx"
    r_doc = media.read_any(docx_file)
    check("read_any لـ docx", r_doc["kind"] == "doc" and len(r_doc["text"]) > 0)

    pdf_file = QA / "src" / "test_sample.pdf"
    pdf_raw = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 55>>stream\nBT /F1 18 Tf 20 50 Td (Hello PDF World) Tj ET\nendstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000111 00000 n \n0000000212 00000 n \n0000000318 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n386\n%%EOF\n"
    )
    pdf_file.write_bytes(pdf_raw)
    r_pdf = media.read_any(pdf_file)
    check("read_any لـ pdf", r_pdf["kind"] == "pdf" and "Hello PDF World" in r_pdf["text"])

    img_file = QA / "src" / "test_img.png"
    created_img = False
    try:
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (300, 100), color=(255, 255, 255))
        draw = ImageDraw.Draw(im)
        draw.text((20, 30), "HELLO WORLD OCR", fill=(0, 0, 0))
        im.save(img_file)
        created_img = True
    except Exception:
        pass
    if not created_img and shutil.which("ffmpeg"):
        r_ff = subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "color=c=white:s=300x100:d=1", "-vf", "drawtext=text='HELLO WORLD OCR':fontcolor=black:fontsize=30:x=20:y=35", "-frames:v", "1", str(img_file), "-y"], capture_output=True)
        created_img = r_ff.returncode == 0 and img_file.exists()
    if not created_img and shutil.which("sips"):
        subprocess.run(["sips", "-s", "format", "png", str(pdf_file), "--out", str(img_file)], capture_output=True)
    if not img_file.exists():
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
    r_img = media.read_any(img_file)
    check("read_any لصورة", r_img["kind"] == "image" and r_img["meta"].get("ocr") is True)

    # 4. convert: png -> jpg, txt -> docx, صوت sine بـ ffmpeg -> mp3
    c_jpg = media.convert(img_file, "jpg", out_dir=QA / "dst")
    check("convert png إلى jpg", c_jpg.get("ok") and Path(c_jpg["path"]).exists() and Path(c_jpg["path"]).suffix.lower() == ".jpg")

    c_docx = media.convert(t_file, "docx", out_dir=QA / "dst")
    check("convert txt إلى docx", c_docx.get("ok") and Path(c_docx["path"]).exists() and Path(c_docx["path"]).suffix.lower() == ".docx")

    wav_sine = QA / "src" / "test_sine.wav"
    subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", str(wav_sine), "-y"], capture_output=True)
    c_mp3 = media.convert(wav_sine, "mp3", out_dir=QA / "dst")
    check("convert صوت sine بـ ffmpeg إلى mp3", c_mp3.get("ok") and Path(c_mp3["path"]).exists() and Path(c_mp3["path"]).suffix.lower() == ".mp3")

    # أداة read_any_file بالمكان uploads: يجب أن تصل إلى فحص الوجود لا أن تنهار (كانت تنهار بسبب Path غير مستورد)
    r_up = call("read_any_file", {"place": "uploads", "path": "20000101/لا_وجود_له.txt"})
    check("read_any_file في uploads تعيد «غير موجود» لا استثناءً", "غير موجود" in json.dumps(r_up, ensure_ascii=False))

    # تصحيح الأسماء ذات المسافة الضيقة (U+202F) التي يكتبها النموذج بمسافة عادية
    import agent_tools as _AT
    _d = QA / "src" / "لقطة"
    _d.mkdir(parents=True, exist_ok=True)
    _real = _d / "Captura 12.17.36\u202fa.m..png"
    _real.write_bytes(b"x")
    class _HM:
        class M:
            @staticmethod
            def cloud_resolve(place, rel):
                return QA, (QA / rel.lstrip("/")).resolve()
    _fixed = _AT._heal_one(_HM, "home", "src/لقطة/Captura 12.17.36 a.m..png")
    check("تصحيح اسم فيه مسافة ضيقة", _fixed.endswith("Captura 12.17.36\u202fa.m..png"))

    # 5. أداة read_any_file: رفض الهاتف ورفض مسار خارج الأماكن
    r_ph = call("read_any_file", {"place": "phone", "path": "file.txt"})
    check("read_any_file ترفض الهاتف", "error" in r_ph or "refused" in r_ph)
    r_out = call("read_any_file", {"place": "home", "path": "../etc/passwd"})
    check("read_any_file ترفض مسارًا خارج الأماكن", "error" in r_out or "refused" in r_out)

    # 6. transcribe: في غياب بيئة التفريغ تعيد رسالة عربية (محاكاة)
    orig_py = media.get_media_python
    media.get_media_python = lambda: None
    try:
        tr_err = media.transcribe(wav_sine)
        check("transcribe بلا بيئة تعيد رسالة عربية", "error" in tr_err and "محرّك التفريغ" in tr_err.get("error", ""))
    finally:
        media.get_media_python = orig_py

    print("— الدفتر والإيقاف")
    log = (DATA / "agent_audit.log").read_text(encoding="utf-8")
    check("دفتر التدقيق يسجل القرارات", all(w in log for w in ("pending:", "approved-done", "refused", "denied", "expired")))
    check("إيقاف الكل", req("POST", "/api/assistant/quick", {"action": "stop_all"})[0] == 200)
    check("الحالة الفورية بلا وكيل", req("POST", "/api/assistant/quick", {"action": "status"})[1].get("ok"))
finally:
    srv.terminate()
    try:
        srv.wait(10)
    except Exception:
        srv.kill()
    shutil.rmtree(QA, ignore_errors=True)
    shutil.rmtree(DATA, ignore_errors=True)
print(f"\nالنتيجة: {ok} ناجح، {fail} فاشل")
sys.exit(1 if fail else 0)
