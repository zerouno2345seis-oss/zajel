import shutil
import sys
import tempfile
import threading
import time
import types
from pathlib import Path
import unittest

import terminal as T


@unittest.skipUnless(T.available(), "tmux غير مثبت")
class Term(unittest.TestCase):
    def setUp(self):
        T.SOCK = "zajel-test"
        T.MON.clear()

    def tearDown(self):
        T._t("kill-server")

    def test_flow(self):
        self.assertTrue(T.start("shell")["started"])
        self.assertFalse(T.start("shell")["started"])
        T.resize("shell", 90, 24)
        T.send("shell", "echo mark-$((5*5))", ["Enter"])
        time.sleep(1)
        s = T.screen("shell")
        self.assertIn("mark-25", s["text"])
        self.assertEqual((s["cols"], s["rows"]), (90, 24))
        self.assertTrue(T.screen("shell", s["hash"]).get("unchanged"))
        self.assertEqual(T.state_of("shell")[0] in ("working", "idle"), True)
        T.stop("shell")
        self.assertEqual(T.state_of("shell")[0], "stopped")

    def test_blocked_keys_and_ids(self):
        T.start("shell")
        with self.assertRaises(ValueError):
            T.send("shell", "", ["rm"])
        with self.assertRaises(ValueError):
            T.start("../etc")

    def test_wait_detection(self):
        T.start("shell")
        T.send("shell", "printf 'Continue? (y/n) '", ["Enter"])
        time.sleep(T.IDLE_SECS + 1)
        self.assertEqual(T.state_of("shell")[0], "idle")   # الطرفية العادية لا تُعدّ منتظِرة؛ الوكلاء فقط


@unittest.skipUnless(T.available(), "tmux غير مثبت")
class Council(unittest.TestCase):
    FAKE = r'''import sys, re, time
buf = ""
name = sys.argv[1] if len(sys.argv) > 1 else "fake"
print("ready", flush=True)
for line in sys.stdin:
    buf += line
    m = re.search(r"ثم A- ثم (\w+) ثم", buf)
    if m and buf.rstrip().endswith("في أي مكان آخر."):
        tok = m.group(1)
        time.sleep(1)
        print(f"● ⟦A-{tok}⟧")
        print(f"  جواب من {name}: وصل {len(buf)} حرفًا")
        print(f"● ⟦Z-{tok}⟧", flush=True)
        buf = ""
'''

    def setUp(self):
        Path("/tmp/fake_agent.py").write_text(self.FAKE, encoding="utf-8")
        T.SOCK = "zajel-test2"
        T.ANSWER_TIMEOUT = 40
        self.tmp, self.old_data = tempfile.mkdtemp(), T.DATA
        T.DATA = Path(self.tmp)          # لا تُكتب ملفات الاختبار في بيانات المستخدم
        for i, nm in (("fa", "A"), ("fb", "B"), ("fm", "M")):
            T.BY_ID[i] = {"id": i, "name": nm, "cmd": "python3 -u /tmp/fake_agent.py " + nm}

    def tearDown(self):
        T._t("kill-server")
        for i in ("fa", "fb", "fm"):
            T.BY_ID.pop(i, None)
        T.DATA = self.old_data
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_round(self):
        r = T.council_start(["fa", "fb"], "ما عاصمة فرنسا؟", main="fm", mode="terminal", blind=False)
        rid = r["id"]
        for _ in range(90):
            v = T.council_view(rid)["round"]
            if v["phase"] in ("done", "stopped"):
                break
            time.sleep(1)
        self.assertEqual(v["phase"], "done", v)
        self.assertIn("جواب من A", v["agents"]["fa"]["answer"])
        self.assertIn("جواب من B", v["agents"]["fb"]["answer"])
        self.assertIn("جواب من M", v["eval"]["answer"])
        self.assertIn("إجابة A", T._eval_prompt(T.COUNCIL[rid]))


VERDICT = "## الخلاصة\nالثقة: عالية\nخلاصة.\n## الاتفاق\nا\n## الاختلاف ومن الأصح\nب\n## خريطة الأقوال\n| الادعاء | أ | ب | التحقق |\n## المصادر\nم\n## الترتيب\nر\n## الحكم النهائي\nالحكم الموحّد هنا"


class DirectCouncil(unittest.TestCase):
    """المجلس المباشر مع وحدة council_agents وهمية (تُحقن في sys.modules، بلا ملف في المستودع)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = (T.DATA, dict(T.COUNCIL), list(T.COUNCIL_ORDER), sys.modules.get("council_agents"), T._run_eval)
        T.DATA = Path(self.tmp)
        T.COUNCIL.clear(); T.COUNCIL_ORDER.clear()
        self.calls, self.judge, self.active, self.peak = [], [], 0, 0
        self.answers = {"codex": "جواب كودكس عن السؤال المطروح " * 3, "hermes": "جواب هرمس عن السؤال المطروح " * 3}
        self.verdicts = [VERDICT]
        self.judge_sleep = 0
        mu = threading.Lock()
        test = self

        def run(agent_id, prompt, depth="bal", workdir=None, add_dirs=(), on_event=None, should_stop=None, timeout=900):
            test.calls.append((agent_id, prompt, list(add_dirs), depth))
            if on_event:
                on_event("activity", "يقرأ: ملف"); on_event("text", "جزء")
            if prompt.startswith("أنت الوكيل الرئيسي"):
                with mu:
                    test.active += 1; test.peak = max(test.peak, test.active)
                time.sleep(test.judge_sleep)
                with mu:
                    test.active -= 1
                test.judge.append(prompt)
                v = test.verdicts.pop(0) if len(test.verdicts) > 1 else test.verdicts[0]
                return {"ok": True, "text": v, "partial": False, "error": "", "secs": 0.1, "model": "judge-m"}
            if prompt.startswith("[جولة النقد المتبادل]"):
                return {"ok": True, "text": "## النقد\nملاحظات\n## الخلاصة\nمنقّحة من " + agent_id, "partial": False, "error": "", "secs": 0.1, "model": "m"}
            return {"ok": True, "text": test.answers[agent_id], "partial": agent_id == "hermes", "error": "", "secs": 0.1, "model": "m-" + agent_id}

        fake = types.ModuleType("council_agents")
        fake.run = run
        fake.can_run = lambda i: True
        fake.init = lambda d: None
        fake.check = lambda ids, force=False: {i: {"state": "ready", "note": "", "secs": 1.0} for i in ids}
        fake.profiles = lambda: {"claude": {"effort": "high"}}
        fake.set_profile = lambda i, patch: dict({"effort": "high"}, **patch)
        sys.modules["council_agents"] = fake

    def tearDown(self):
        for rd in T.COUNCIL.values():
            rd["stop"] = True
        T.DATA, c, o, mod, T._run_eval = self.saved
        T.COUNCIL.clear(); T.COUNCIL.update(c); T.COUNCIL_ORDER[:] = o
        if mod is None:
            sys.modules.pop("council_agents", None)
        else:
            sys.modules["council_agents"] = mod
        shutil.rmtree(self.tmp, ignore_errors=True)

    def wait(self, rid, secs=20):
        for _ in range(secs * 20):
            r = T.council_view(rid)["round"]
            if r["phase"] in ("done", "stopped", "error") and rid not in T.RUNNING:
                return r
            time.sleep(0.05)
        self.fail("لم تنته الجولة: " + str(T.council_view(rid)["round"]["phase"]))

    def test_blind_letters_and_retry_mapping(self):
        rid = T.council_start(["codex", "hermes"], "ما حكم المسألة؟", main="claude")["id"]
        rd = T.COUNCIL[rid]
        self.assertEqual(sorted(rd["letters"].values()), ["أ", "ب"])
        self.verdicts = [VERDICT + "\nRETRY: " + rd["letters"]["hermes"], VERDICT]
        r = self.wait(rid)
        self.assertEqual(r["phase"], "done")
        self.assertEqual(r["agents"]["hermes"].get("retries"), 1)
        self.assertFalse(r["agents"]["codex"].get("retries"))
        self.assertEqual(len(self.judge), 2)
        for word in ("Codex", "codex", "Hermes", "hermes"):
            self.assertNotIn(word, self.judge[0])
        self.assertIn("RETRY: أ, ب", self.judge[0])
        self.assertNotIn("RETRY", r["eval"]["answer"])
        self.assertEqual(r["eval"]["version"], 2)
        self.assertEqual(r["agents"]["hermes"]["model"], "m-hermes")
        self.assertTrue(r["agents"]["hermes"]["partial"])
        self.assertEqual(T._retry_ids(rd, "الإجابة " + rd["letters"]["codex"] + "، hermes, zz"), ["codex", "hermes"])

    def test_answer_files_and_preview(self):
        self.answers["codex"] = "س" * 9000 + " نهاية-كاملة"
        rid = T.council_start(["codex", "hermes"], "سؤال طويل الإجابة", main="claude")["id"]
        r = self.wait(rid)
        d = Path(self.tmp) / "council" / rid
        f = d / (r["letters"]["codex"] + ".md")
        self.assertEqual(f.read_text(encoding="utf-8"), self.answers["codex"])
        self.assertTrue((d / (r["letters"]["hermes"] + ".md")).is_file())
        self.assertEqual((d / "verdict.md").read_text(encoding="utf-8"), VERDICT)
        jp = self.judge[0]
        self.assertIn(str(f), jp)
        self.assertNotIn("نهاية-كاملة", jp)                 # المعاينة ٦٠٠٠ حرف فقط…
        self.assertIn("انتهت المعاينة عند 6000", jp)        # …مع التصريح بأن الكامل في الملف
        judge_dirs = [c[2] for c in self.calls if c[1].startswith("أنت الوكيل الرئيسي")][0]
        self.assertIn(str(d), judge_dirs)
        delegate_q = [c[1] for c in self.calls if c[0] == "codex"][0]
        for h in ("## الخلاصة", "## التفصيل", "## الأدلة والمصادر", "## درجة الثقة", "## ما لم أتحقق منه", "لا تعدّل أي ملف"):
            self.assertIn(h, delegate_q)

    def test_followup_note(self):
        q1 = "سؤال أول طويل جدًا " * 40 + "آخر-السؤال"
        rid = T.council_start(["codex"], q1, main="claude")["id"]
        self.wait(rid)
        rid2 = T.council_start(["codex"], "وماذا عن الحالة الثانية؟", main="claude", parent=rid)["id"]
        self.wait(rid2)
        q = [c[1] for c in self.calls if c[0] == "codex"][-1]
        self.assertIn("آخر-السؤال", q)                       # السؤال السابق كاملًا لا أول ٣٠٠ حرف
        self.assertIn(str(Path(self.tmp) / "council" / rid / "verdict.md"), q)
        self.assertIn("الحكم الموحّد هنا", q)
        self.assertNotIn("## المصادر\nم", q)                 # «الحكم النهائي» فقط لا الحكم كله
        self.assertIn(str(Path(self.tmp) / "council" / rid), [c[2] for c in self.calls if c[0] == "codex"][-1])

    def test_eval_lock(self):
        rid = T.council_start(["codex"], "سؤال", main="claude", evaluate=False)["id"]
        self.wait(rid)
        self.judge_sleep = 0.4
        T.council_evaluate(rid); T.council_evaluate(rid)
        for _ in range(100):
            if len(self.judge) == 2 and T.COUNCIL[rid]["phase"] == "done":
                break
            time.sleep(0.05)
        self.assertEqual(len(self.judge), 2)
        self.assertEqual(self.peak, 1)                       # لم يعمل حكمان معًا
        self.assertEqual(T.COUNCIL[rid]["eval"]["version"], 2)

    def test_final_phase_after_exception(self):
        def boom(rd):
            raise RuntimeError("انفجار")
        T._run_eval = boom
        rid = T.council_start(["codex"], "سؤال", main="claude")["id"]
        r = self.wait(rid)
        self.assertEqual(r["phase"], "error")
        self.assertIn("انفجار", r["error"])
        saved = (Path(self.tmp) / "terminal_council.json").read_text(encoding="utf-8")
        self.assertIn('"error"', saved)

    def test_review_round_uses_revised(self):
        rid = T.council_start(["codex", "hermes"], "سؤال للنقد", main="claude", review=True)["id"]
        r = self.wait(rid)
        self.assertTrue(r["review"])
        rev = [c for c in self.calls if c[1].startswith("[جولة النقد المتبادل]")]
        self.assertEqual(sorted(c[0] for c in rev), ["codex", "hermes"])
        other = T.COUNCIL[rid]["letters"]["hermes"]
        self.assertIn("الإجابة " + other, [c[1] for c in rev if c[0] == "codex"][0])
        self.assertIn("منقّحة من codex", r["agents"]["codex"]["revised"])
        d = Path(self.tmp) / "council" / rid
        self.assertTrue((d / (r["letters"]["codex"] + ".rev.md")).is_file())
        self.assertIn("منقّحة بعد النقد المتبادل", self.judge[0])
        self.assertNotIn("جواب كودكس", self.judge[0])

    def test_verdict_prompt_headings(self):
        rid = T.council_start(["codex", "hermes"], "سؤال", main="claude", verify=True)["id"]
        self.wait(rid)
        p = T._eval_prompt(T.COUNCIL[rid])
        pos = [p.index("## " + h) for h in T.VERDICT_HEADS]
        self.assertEqual(pos, sorted(pos))
        self.assertIn("«الثقة: عالية»", p)
        self.assertIn("✓ تحقق", p)
        self.assertIn("| الادعاء | أ | ب | التحقق |", p)
        T.COUNCIL[rid]["verify"] = False
        self.assertNotIn("✓ تحقق", T._eval_prompt(T.COUNCIL[rid]))

    def test_defaults_and_api(self):
        rid = T.council_start(["codex"], "سؤال", main="claude", depth="fast")["id"]
        rd = T.COUNCIL[rid]
        self.assertEqual((rd["limit"], rd["blind"], rd["review"], rd["verify"]), (180, True, False, True))
        self.wait(rid)
        self.assertEqual([c[3] for c in self.calls if c[0] == "codex"], ["fast"])
        self.assertEqual(T.council_check("codex,claude,zz")["agents"]["codex"]["state"], "ready")
        self.assertTrue(all(a["direct"] for a in T.council_agents()["agents"]))
        self.assertEqual(T.council_set_profile("codex", {"web": False})["profile"]["web"], False)
        self.assertIn("claude", T.council_profiles()["profiles"])


if __name__ == "__main__":
    unittest.main()
