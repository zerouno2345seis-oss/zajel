"""اختبارات نقل وإنقاذ المساحات: مجلدات مؤقتة فقط، لا يُلمس شيء من ملفات المستخدم."""
import os, shutil, sys, tempfile, time, types
from pathlib import Path

T = Path(tempfile.mkdtemp(prefix="zajel-tj-"))
os.environ["PB_DATA"] = str(T / "data")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import transfer_jobs as TJ

SRC, DST, TRASH = T / "src", T / "dst", T / "trash"
for d in (SRC, DST, TRASH, T / "data"):
    d.mkdir(parents=True, exist_ok=True)
ROOTS = {"s": SRC, "d": DST}

def cloud_resolve(root, rel=""):
    b = ROOTS[root].resolve()
    return b, (b / rel.lstrip("/")).resolve()
M = types.SimpleNamespace(cloud_resolve=cloud_resolve, cloud_roots=lambda: [{"id": "s"}, {"id": "d"}],
                          cleaner=types.SimpleNamespace(trash_dir_for=lambda p: TRASH))
TJ.init(M, T / "data")

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print("✓", name)
    else: fail += 1; print("✗", name)

def wait(jid, states=("done", "cancelled", "error"), t=20):
    t0 = time.time()
    while time.time() - t0 < t:
        if TJ.JOBS[jid]["state"] in states and not TJ._alive(jid):
            return TJ.JOBS[jid]
        time.sleep(0.05)
    raise TimeoutError

def mk():
    shutil.rmtree(SRC); SRC.mkdir(); shutil.rmtree(DST); DST.mkdir()
    (SRC / "a").mkdir(); (SRC / "a" / "x.txt").write_text("hello"); (SRC / "a" / "y.bin").write_bytes(os.urandom(300000))
    (SRC / "z.txt").write_text("zzz")

# 1) نسخ: الأصل يبقى
mk()
j = TJ.create({"src_root": "s", "dst_root": "d", "dst_dir": "out", "mode": "copy", "items": ["a", "z.txt"]})
j = wait(j["id"])
check("النسخ ينتهي done", j["state"] == "done")
check("بنية المجلد محفوظة في الوجهة", (DST / "out/a/x.txt").read_text() == "hello" and (DST / "out/z.txt").exists())
check("الأصل باقٍ بعد النسخ", (SRC / "a/x.txt").exists())
check("التقرير يعدّ الملفات", j["report"]["copied"] == 3 and j["report"]["freed"] == 0)

# 2) نقل مع تحقق: الأصل إلى السلة
mk()
j = wait(TJ.create({"src_root": "s", "dst_root": "d", "dst_dir": "", "mode": "move", "items": ["a"]})["id"])
check("النقل ينتهي", j["state"] == "done" and (DST / "a/y.bin").exists())
check("الأصل غادر مكانه", not (SRC / "a").exists())
check("الأصل في السلة لا محذوف نهائيًا", len(list(TRASH.iterdir())) == 2)
check("المساحة المحررة محسوبة", j["freed"] > 300000)
u = TJ.undo(j["id"])
check("التراجع يعيد الملفات", u["restored"] == 2 and (SRC / "a/x.txt").exists())
for p in TRASH.iterdir(): shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink()

# 3) عدم الحذف عند عدم التطابق
mk()
orig = TJ._copy
def bad_copy(j, f, s, ctrl, tmp, base):
    orig(j, f, s, ctrl, tmp, base)
    d = TJ.resolve(j["dst_root"], "") / f["dst_rel"]
    d.write_bytes(d.read_bytes()[:-1] + b"X") if d.stat().st_size else None   # نفس الحجم، محتوى مختلف
TJ._copy = bad_copy
j = wait(TJ.create({"src_root": "s", "dst_root": "d", "dst_dir": "", "mode": "move", "items": ["a", "z.txt"]})["id"])
TJ._copy = orig
check("عدم تطابق البصمة ⇒ الأصل باقٍ", (SRC / "a/x.txt").exists() and (SRC / "a/y.bin").exists() and (SRC / "z.txt").exists())
check("الملفات الفاشلة مسجّلة", j["report"]["failed"] and not list(TRASH.iterdir()))
j = wait(TJ.retry_failed(j["id"])["id"])
check("إعادة المحاولة تنجح بعد الإصلاح", j["state"] == "done" and not j["report"]["failed"] and not (SRC / "z.txt").exists())
for p in TRASH.iterdir(): shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink()

# 4) استئناف بعد انهيار: نقتل التنفيذ بعد نسخ أول ملف
mk()
(SRC / "b.txt").write_text("bbb")
calls = {"n": 0}
orig_p = TJ._process
def crashy(j, f, ctrl, tmp):
    calls["n"] += 1
    if calls["n"] == 2:
        raise KeyboardInterrupt        # محاكاة موت العملية
    return orig_p(j, f, ctrl, tmp)
TJ._process = crashy
j = TJ.create({"src_root": "s", "dst_root": "d", "dst_dir": "", "mode": "move", "items": ["z.txt", "b.txt", "a"]})
jid = j["id"]
t0 = time.time()
while TJ._alive(jid) and time.time() - t0 < 10: time.sleep(0.05)
TJ._process = orig_p
st = {f["rel"]: f["status"] for f in TJ.JOBS[jid]["files"]}
check("الملف الأول انتهى قبل الانهيار", st["z.txt"] == "deleted")
TJ.JOBS[jid]["state"] = "running"; TJ._save(TJ.JOBS[jid])     # كما تركه الانهيار
TJ.init(M, T / "data")                                       # «إعادة تشغيل»
check("بعد التشغيل تظهر المهمة «interrupted»", TJ.JOBS[jid]["state"] == "interrupted")
j = wait(TJ.resume(jid)["id"])
check("الاستئناف يكمل الباقي", j["state"] == "done" and (DST / "b.txt").exists() and (DST / "a/y.bin").exists())
check("لا نسخ مكررة بعد الاستئناف", not list(DST.glob("* 2*")))

# 5) تعارض الأسماء: لا يُستبدل ملف مختلف
mk(); (DST / "z.txt").write_text("different")
j = wait(TJ.create({"src_root": "s", "dst_root": "d", "dst_dir": "", "mode": "copy", "items": ["z.txt"]})["id"])
check("ملف مختلف بالاسم نفسه ⇒ يُعاد تسمية الجديد", (DST / "z.txt").read_text() == "different" and (DST / "z 2.txt").read_text() == "zzz")

# 6) إيقاف مؤقت وإلغاء
mk()
big = SRC / "big.bin"; big.write_bytes(os.urandom(40 * 1024 * 1024))
j = TJ.create({"src_root": "s", "dst_root": "d", "dst_dir": "", "mode": "copy", "items": ["big.bin"]})
TJ.pause(j["id"], True); time.sleep(0.4)
n1 = TJ.JOBS[j["id"]]["bytes_done"]; time.sleep(0.4)
check("الإيقاف المؤقت يجمّد التقدم", TJ.JOBS[j["id"]]["state"] == "paused" and TJ.JOBS[j["id"]]["bytes_done"] == n1)
TJ.cancel(j["id"]); j = wait(j["id"])
check("الإلغاء ينظّف الملف الجزئي", j["state"] == "cancelled" and not list(DST.glob("big.bin*")))

# 7) رفض الوجهة داخل المصدر ورفض مجلد فارغ
mk()
for body, name in (({"src_root": "s", "dst_root": "s", "dst_dir": "a", "mode": "move", "items": ["a"]}, "وجهة داخل المصدر"),
                   ({"src_root": "s", "dst_root": "d", "mode": "copy", "items": []}, "بلا اختيار"),
                   ({"src_root": "s", "dst_root": "d", "mode": "copy", "items": ["../x"]}, "مسار خارجي")):
    try: TJ.create(body); check("يرفض " + name, False)
    except ValueError: check("يرفض " + name, True)

# 8) حماية iCloud: الصور مرفوضة والواتساب يحتاج تأكيدًا
for items, allow, exp in ((["com~apple~Photos/x"], True, False), (["57T~net~whatsapp~WhatsApp/b"], False, False), (["57T~net~whatsapp~WhatsApp/b"], True, True)):
    try: TJ._yellow_red_check("icloud_all", items, allow); got = True
    except ValueError: got = False
    check(f"حماية iCloud {items[0][:12]} allow={allow}", got == exp)
check("تصنيف iCloud", TJ._icloud_category("com~apple~CloudDocs")[0] == "green" and TJ._icloud_category("com~apple~Pages")[0] == "green_old")

# 9) التحليل والاقتراحات + الأقدم من سنة
mk(); old = time.time() - 400 * 86400
os.utime(SRC / "a/x.txt", (old, old))
a = TJ.analysis("s", True); t0 = time.time()
while a["state"] == "running" and time.time() - t0 < 10: time.sleep(0.05)
check("التحليل يحسب الإجمالي", a["state"] == "done" and a["total_bytes"] > 300000)
check("الأقدم من سنة", a["older_than_year"]["count"] == 1)
check("التقاط الملف المبعد", TJ._placeholder_real(".doc.pdf.icloud") == "doc.pdf")
j = wait(TJ.create({"src_root": "s", "dst_root": "d", "dst_dir": "old", "mode": "copy", "rule": {"older_than_days": 365}})["id"])
check("نقل بقاعدة «أقدم من سنة»", (DST / "old/a/x.txt").exists() and not (DST / "old/z.txt").exists())
check("space_alert تعيد قاموسًا", "alert" in TJ.space_alert())

shutil.rmtree(T, ignore_errors=True)
print(f"\nالنتيجة: {ok} ناجح، {fail} فاشل")
sys.exit(1 if fail else 0)
