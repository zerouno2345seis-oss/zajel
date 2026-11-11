"""اختبار الجولات والمحكِّم بطرفية وهمية (بلا tmux ولا وكلاء حقيقيين)."""
import json
import tempfile
import time
import unittest
from pathlib import Path

import answer_export
import judge


class FakeT:
    def __init__(self):
        self.BY_ID = {"claude": {"id": "claude", "name": "Claude", "cmd": "claude"}, "codex": {"id": "codex", "name": "Codex", "cmd": "codex"},
                      "agy": {"id": "agy", "name": "Gemini", "cmd": "agy"}}
        self.BROADCAST_STATE = {}
        self.sent = []
        self.ans = {}        # id ← (سؤال، جواب)
        self.st = {}

    def broadcast(self, ids, text):
        self.sent.append((list(ids), text))
        for i in ids:
            self.BROADCAST_STATE[i] = {"state": "sent", "note": ""}
        return {"ok": True}

    def last_answer(self, i):
        q, a = self.ans.get(i, ("", ""))
        return {"question": q, "answer": a}

    def state_of(self, i):
        return (self.st.get(i, "idle"), "", 0)


class JudgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.t = FakeT()
        judge.T, judge.DATA, judge.POLL = self.t, self.tmp, 0.01
        judge.ROUNDS.clear()

    def tearDown(self):
        judge.ROUNDS.clear()          # خيوط المراقبة تخرج حين تختفي جولتها، فلا تكتب في مجلد الاختبار التالي
        time.sleep(judge.POLL * 5)

    def wait(self, fn, secs=4):
        t0 = time.time()
        while time.time() - t0 < secs:
            v = fn()
            if v:
                return v
            time.sleep(0.02)
        self.fail("انتهت المهلة")

    def test_states_and_auto_judge(self):
        r = judge.start_round("ما حكم كذا؟", ["claude", "codex"], judge="agy", auto_judge=True)
        rid = r["round_id"]
        self.assertEqual(r["agents"]["claude"]["state"], "waiting")
        self.assertFalse(r["judge_also_answers"])
        self.assertIn("المصادر", self.t.sent[0][1])                       # ملاحظة التوثيق من الخادم
        # جواب قديم لسؤال آخر لا يُلتقط
        self.t.ans["claude"] = ("سؤال قديم", "جواب قديم")
        time.sleep(0.15)
        self.assertEqual(judge.round_status(rid)["agents"]["claude"]["state"], "waiting")
        self.t.ans["claude"] = ("ما حكم كذا؟ (وثّق)", "جواب [1]\n\nالمصادر\n[1] كتاب ص ١")
        self.t.st["codex"] = "waiting"
        self.t.ans["codex"] = ("ما حكم كذا؟ (وثّق)", "جزء")
        self.wait(lambda: judge.round_status(rid)["agents"]["claude"]["state"] == "done")
        self.assertEqual(judge.round_status(rid)["agents"]["codex"]["state"], "needs_input")
        self.t.st["codex"] = "idle"
        self.wait(lambda: judge.round_status(rid)["judge_state"] in ("running", "waiting_answers"))
        # المحكِّم يستلم ملف الأجوبة لا النص
        sent = self.wait(lambda: [s for s in self.t.sent if s[0] == ["agy"]])
        self.assertIn("answers.md", sent[0][1])
        self.assertLess(len(sent[0][1]), 4000)
        self.assertTrue((Path(self.tmp) / "rounds" / rid / "answers.md").is_file())
        self.t.ans["agy"] = ("⟦حكم:%s⟧ ..." % rid, "## الخلاصة الموحدة\nتم")
        s = self.wait(lambda: (lambda x: x if x["judge_state"] == "done" else None)(judge.round_status(rid)))
        self.assertIn("الخلاصة الموحدة", s["verdict"])
        self.assertEqual(judge.last_round()["round_id"], rid)

    def test_timeout(self):
        r = judge.start_round("سؤال", ["claude"], timeout_min=1)
        with judge._LOCK:
            judge.ROUNDS[r["round_id"]]["created"] -= 120
        s = self.wait(lambda: (lambda x: x if x["agents"]["claude"]["state"] == "timeout" else None)(judge.round_status(r["round_id"])))
        self.assertEqual(s["judge_state"], "idle")

    def test_broadcast_skipped_is_error(self):
        orig = self.t.broadcast
        self.t.broadcast = lambda ids, text: (orig(ids, text), self.t.BROADCAST_STATE.update({"codex": {"state": "skipped", "note": "يعرض سؤالًا"}}))
        r = judge.start_round("سؤال", ["codex"])
        s = self.wait(lambda: (lambda x: x if x["agents"]["codex"]["state"] == "error" else None)(judge.round_status(r["round_id"])))
        self.assertIn("سؤالًا", s["agents"]["codex"]["note"])

    def test_anonymize_and_judge_also_answers(self):
        r = judge.start_round("س", ["claude", "codex"], judge="claude")
        self.assertTrue(r["judge_also_answers"])
        rid = r["round_id"]
        with judge._LOCK:
            rr = judge.ROUNDS[rid]
            rr["agents"]["claude"]["answer"] = "As Claude, I think هذا صحيح. بحسب Anthropic."
            rr["agents"]["codex"]["answer"] = "أنا Codex وأرى أنه خطأ."
        p, key = judge.build_answers_file(rr)
        txt = p.read_text(encoding="utf-8")
        self.assertEqual(sorted(key), ["أ", "ب"])
        for bad in ("Claude", "Codex", "Anthropic"):
            self.assertNotIn(bad, txt)
        self.assertIn("الجواب (أ)", txt)
        self.assertIn("درجة لكل معيار", judge.judge_prompt(rr, p))

    def test_select_and_default_judge(self):
        r = judge.start_round("س", ["claude", "codex"])
        s = judge.set_selected(r["round_id"], "codex", False)
        self.assertFalse(s["agents"]["codex"]["selected"])
        self.assertEqual(judge.set_default_judge("agy"), "agy")
        self.assertEqual(judge.get_default_judge(), "agy")
        with self.assertRaises(ValueError):
            judge.set_default_judge("nope")
        with self.assertRaises(ValueError):
            judge.start_round("", ["claude"])

    def test_deep_note_and_timeout(self):
        r = judge.start_round("س", ["claude"], deep=True)
        self.assertEqual(r["timeout_min"], 30)
        self.assertIn("٨ مصادر", self.t.sent[0][1])

    def test_export_order(self):
        out = Path(self.tmp) / "out"
        r = answer_export.export_round("ما الحكم؟", "## الخلاصة الموحدة\nخلاصة", [("Claude", "جواب كلود [1]\n\nالمصادر\n[1] كتاب")], "عمق", out_dir=out, judge="Gemini")
        from docx import Document
        txt = "\n".join(p.text for p in Document(r["path"]).paragraphs)
        self.assertLess(txt.index("الحكم والخلاصة"), txt.index("الملحق: الأجوبة المختارة"))
        self.assertLess(txt.index("الملحق: الأجوبة المختارة"), txt.index("البحث المتعمق"))
        self.assertIn("جواب Claude", txt)


    def test_deep_for_one_agent_and_reask(self):
        r = judge.start_round("س", ["claude", "codex"], deep_agents=["codex"])
        rid = r["round_id"]
        self.assertTrue(r["agents"]["codex"]["deep"]) ; self.assertFalse(r["agents"]["claude"]["deep"])
        texts = {tuple(ids): txt for ids, txt in self.t.sent}
        self.assertNotIn("[بحث متعمق]", texts[("claude",)])
        self.assertIn("[بحث متعمق]", texts[("codex",)])
        self.assertEqual(r["timeout_min"], judge.DEEP_TIMEOUT_MIN)
        self.t.ans["claude"] = ("س", "جواب أول")
        self.wait(lambda: judge.round_status(rid)["agents"]["claude"]["state"] == "done")
        n = len(self.t.sent)
        r = judge.reask(rid, "claude")
        self.assertEqual(r["agents"]["claude"]["state"], "waiting")
        self.assertEqual(r["agents"]["claude"]["answer"], "")
        self.assertEqual(self.t.sent[n][0], ["claude"])
        time.sleep(0.2)
        self.assertEqual(judge.round_status(rid)["agents"]["claude"]["state"], "waiting")   # الجواب القديم لا يُلتقط
        self.t.ans["claude"] = ("س\n" + judge.round_status(rid)["agents"]["claude"]["mark"], "جواب ثانٍ")
        self.wait(lambda: judge.round_status(rid)["agents"]["claude"]["answer"] == "جواب ثانٍ")
        with self.assertRaises(ValueError):
            judge.reask(rid, "agy")              # ليس من المجيبين

    def test_deepen_one_agent_replaces_its_answer(self):
        r = judge.start_round("س", ["claude", "codex"])
        rid = r["round_id"]
        self.t.ans["claude"] = ("س", "جواب قصير")
        self.wait(lambda: judge.round_status(rid)["agents"]["claude"]["state"] == "done")
        r = judge.deepen(rid, "claude")
        self.assertTrue(r["agents"]["claude"]["deep"])
        self.assertEqual(r["agents"]["claude"]["state"], "waiting")
        self.assertIn("[بحث متعمق]", self.t.sent[-1][1])
        self.assertEqual(r["deep_state"], "idle")                 # لا شاشة «بحث متعمق» منفصلة
        self.t.ans["claude"] = ("س\n" + judge.round_status(rid)["agents"]["claude"]["mark"], "جواب أعمق بمصادر")
        self.wait(lambda: judge.round_status(rid)["agents"]["claude"]["answer"] == "جواب أعمق بمصادر")

    def test_judge_starts_now_with_finished_answers_only(self):
        r = judge.start_round("س", ["claude", "codex"], judge="agy")
        rid = r["round_id"]
        self.t.ans["claude"] = ("س", "جواب مكتمل")
        self.wait(lambda: judge.round_status(rid)["agents"]["claude"]["state"] == "done")
        judge.run_judge(rid)                                   # Codex لم يُجب بعد
        self.wait(lambda: any("⟦حكم:" in txt for _, txt in self.t.sent))
        ans = (Path(self.tmp) / "rounds" / rid / "answers.md").read_text(encoding="utf-8")
        self.assertIn("جواب مكتمل", ans)
        self.assertNotIn("Codex", ans)
        self.t.ans["agy"] = (f"⟦حكم:{rid}⟧", "## الخلاصة الموحدة\nحكم")       # يُنهي خيط المحكِّم قبل الاختبار التالي
        r = self.wait(lambda: (lambda r: r if r["judge_state"] == "done" else None)(judge.round_status(rid)), 10)
        self.assertIn("لم تدخل هذا التحكيم", r["verdict"])

    def test_reask_accepts_identical_answer(self):
        r = judge.start_round("س", ["claude"])
        rid = r["round_id"]
        self.t.ans["claude"] = ("س", "نفس الجواب")
        self.wait(lambda: judge.round_status(rid)["agents"]["claude"]["state"] == "done")
        judge.reask(rid, "claude")
        time.sleep(0.2)
        self.assertEqual(judge.round_status(rid)["agents"]["claude"]["state"], "waiting")
        self.assertIn("⟦إعادة 2⟧", self.t.sent[-1][1])
        self.t.ans["claude"] = ("س\n⟦إعادة 2⟧", "نفس الجواب")          # الجواب الجديد مطابق للقديم حرفًا
        self.wait(lambda: judge.round_status(rid)["agents"]["claude"]["state"] == "done")

    def test_unfence_hermes(self):
        import judge
        self.assertEqual(judge._strip_notes("```\nنص الجواب\nسطر ثان\n```"), "نص الجواب\nسطر ثان")
        self.assertEqual(judge._strip_notes("```\nنص يكتب الآن"), "نص يكتب الآن")
        keep = "مقدمة\n```py\nx=1\n```\nخاتمة"
        self.assertEqual(judge._strip_notes(keep), keep)

    def test_clean_verdict(self):
        import judge
        raw = "اكتب تقريرك بهذا الترتيب\n## الخلاصة الموحدة — خلاصة واحدة\nتعليمات\n○ Thought for 3m 59s\nالخلاصة الموحدة\nالنص الحقيقي[^1]\n▸ Thought for 43s"
        self.assertEqual(judge.clean_verdict(raw), "الخلاصة الموحدة\nالنص الحقيقي[^1]")

    def test_prompt_rules(self):
        import judge
        rr = {"round_id": "x", "judge_also_answers": False}
        p = judge.judge_prompt(rr, "/a/answers.md", "/a/verdict.md")
        for w in ("المتن نظيف", "[^1]", "جداول Markdown", "/a/verdict.md"):
            self.assertIn(w, p)

    # ---------- Perplexity محكِّمًا ----------
    def _web_round(self, size=None):
        r = judge.start_round("ما معنى الإفك؟", ["claude", "codex"], judge="perplexity")
        rid = r["round_id"]
        self.t.ans["claude"] = ("ما معنى الإفك؟", "الإفك الكذب [1]\n\nالمصادر\n[1] لسان العرب")
        self.t.ans["codex"] = ("ما معنى الإفك؟", "الإفك أشد الكذب")
        self.wait(lambda: all(a["state"] == "done" for a in judge.round_status(rid)["agents"].values()))
        judge.run_judge(rid)
        r = self.wait(lambda: (lambda r: r if r["judge_state"] == "web_pending" else None)(judge.round_status(rid)))
        return rid, r

    def test_perplexity_can_judge_and_messages(self):
        rid, r = self._web_round()
        self.assertEqual(r["judge"], "perplexity")
        self.assertEqual(self.t.sent[-1][1].count("⟦حكم:"), 0)          # لا شيء أُرسل إلى الطرفية
        msgs = r["web_judge"]["messages"]
        self.assertEqual(len(msgs), 1)
        for w in (judge.WEB_BEGIN, judge.WEB_END, "[^1]", "## الخلاصة الموحدة", "❓", "لسان العرب", "بحث الويب"):
            self.assertIn(w, msgs[0])
        self.assertEqual(judge.set_default_judge("perplexity"), "perplexity")

    def test_web_messages_split_in_parts(self):
        r = {"round_id": "r_1", "judge_also_answers": False}
        text = "\n".join(f"سطر {i} " + "ك" * 80 for i in range(300))
        msgs = judge.web_judge_messages(r, text, size=3000)
        self.assertGreater(len(msgs), 3)
        self.assertTrue(all(len(m) <= 3000 for m in msgs[:-1]))
        self.assertIn(f"الجزء 1 من {len(msgs) - 1}", msgs[0])
        self.assertIn("انتهى الإرسال", msgs[-1])
        self.assertIn(judge.WEB_END, msgs[-1])
        joined = "\n".join(m.split("=====\n", 1)[1] for m in msgs[:-1])
        self.assertEqual(joined, text)                                  # لا يضيع ولا يتكرر شيء
        self.assertEqual(judge._web_split("ب" * 25, 10), ["ب" * 10, "ب" * 10, "ب" * 5])

    def test_web_parse(self):
        B, E = judge.WEB_BEGIN, judge.WEB_END
        self.assertEqual(judge.web_verdict_parse(f"مقدمة\n{B}\nنص\n{E}\nبعد"), ("done", "نص"))
        self.assertEqual(judge.web_verdict_parse(f"{B}\nنص"), ("partial", "نص"))
        self.assertEqual(judge.web_verdict_parse(f"تكملة\n{E}"), ("tail", "تكملة"))
        self.assertEqual(judge.web_verdict_parse("لا أستطيع"), ("none", "لا أستطيع"))
        self.assertEqual(judge.web_verdict_parse(f"{B}\n```markdown\n## الخلاصة\nنص[^1]\n\n[^1]: مصدر\n```\n{E}"), ("done", "## الخلاصة\nنص[^1]\n\n[^1]: مصدر"))
        self.assertEqual(judge.web_verdict_parse(f"{B}\n```markdown\nنص يكتب"), ("partial", "نص يكتب"))

    def test_web_verdict_done_and_footnotes(self):
        rid, _ = self._web_round()
        B, E = judge.WEB_BEGIN, judge.WEB_END
        a = judge.web_verdict(rid, f"{B}\n## الخلاصة الموحدة\nالإفك الكذب[^1]", stable=3)
        self.assertEqual(a["action"], "wait")
        self.assertEqual(a["status"]["judge_state"], "running")
        a = judge.web_verdict(rid, f"{B}\n## الخلاصة الموحدة\nالإفك الكذب[^1]\n\n| أ | ب |\n|---|---|\n| 1 | 2 |\n\n[^1]: لسان العرب\n{E}")
        self.assertEqual(a["action"], "done")
        v = a["status"]["verdict"]
        self.assertTrue(v.startswith("## الخلاصة الموحدة"))
        self.assertIn("[^1]: لسان العرب", v)
        self.assertNotIn(E, v)
        self.assertEqual(judge.web_verdict(rid, "x")["action"], "stop")

    def test_web_verdict_continue_then_join(self):
        rid, _ = self._web_round()
        B, E = judge.WEB_BEGIN, judge.WEB_END
        a = judge.web_verdict(rid, f"{B}\n## الخلاصة الموحدة\nالجزء الأول", stable=judge.WEB_STALL)
        self.assertEqual((a["action"], a["message"]), ("send", judge.WEB_CONTINUE))
        a = judge.web_verdict(rid, "الجزء الثاني", stable=2)
        self.assertEqual(a["action"], "wait")
        a = judge.web_verdict(rid, f"الجزء الثاني\n{E}")
        self.assertEqual(a["action"], "done")
        self.assertIn("الجزء الأول\nالجزء الثاني", a["status"]["verdict"])

    def test_web_verdict_incomplete_accepted_with_warning(self):
        rid, _ = self._web_round()
        raw = f"{judge.WEB_BEGIN}\n## الخلاصة الموحدة\nناقص"
        for _ in range(judge.WEB_MAX_CONTINUE):
            self.assertEqual(judge.web_verdict(rid, raw, stable=judge.WEB_STALL)["action"], "send")
            raw = "تكملة بلا نهاية"
        a = judge.web_verdict(rid, raw, stable=judge.WEB_STALL)
        self.assertEqual(a["action"], "done")
        self.assertIn("⚠️ التقرير ناقص", a["status"]["verdict"])

    def test_web_verdict_refusal_restart_then_fail(self):
        rid, _ = self._web_round()
        a = judge.web_verdict(rid, "لا أستطيع المساعدة في هذا", stable=judge.WEB_REFUSE_STALL)
        self.assertEqual(a["action"], "restart")
        self.assertEqual(a["status"]["web_judge"]["attempt"], 2)
        a = judge.web_verdict(rid, "", error="nosubmit")
        self.assertEqual(a["action"], "fail")
        self.assertEqual(a["status"]["judge_state"], "error")

    def test_web_verdict_login_fails_at_once(self):
        rid, _ = self._web_round()
        a = judge.web_verdict(rid, "", error="login")
        self.assertEqual(a["action"], "fail")
        self.assertIn("تسجيل الدخول", a["status"]["judge_note"])

    def test_web_verdict_without_markers_but_report(self):
        rid, _ = self._web_round()
        self.assertEqual(judge.web_verdict(rid, "## الخلاصة الموحدة\nحكم", stable=5)["action"], "wait")
        a = judge.web_verdict(rid, "## الخلاصة الموحدة\nحكم", stable=judge.WEB_STALL)
        self.assertEqual(a["action"], "done")


if __name__ == "__main__":
    unittest.main()
