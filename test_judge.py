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
        self.events = []     # ترتيب الاستدعاءات: ("restart", id) و("broadcast", ids)
        self.restart_err = None
        self.ans = {}        # id ← (سؤال، جواب)
        self.st = {}

    def restart(self, i, cwd=""):
        self.events.append(("restart", i))
        if self.restart_err:
            raise self.restart_err

    def broadcast(self, ids, text):
        self.events.append(("broadcast", list(ids)))
        self.sent.append((list(ids), text))
        for i in ids:
            self.BROADCAST_STATE[i] = {"state": "sent", "note": ""}
        return {"ok": True}

    def last_answer(self, i):
        q, a = self.ans.get(i, ("", ""))
        return {"question": q, "answer": a}

    def state_of(self, i):
        return (self.st.get(i, "idle"), "", 0)


class FakeS:
    """بديل وهمي لوحدة sources: لا notebooklm ولا MCP ولا خادم الشاملة."""
    def __init__(self):
        self.nb = {}               # معرّف الدفتر ← نتيجة ask_notebook
        self.asked = []
        self.ensure = {}           # وكيل ← نتيجة ensure_agent (الافتراضي ok)
        self.ensured = []
        self.notes = []
        self.written = []
        self.verify = {}           # نص ← نتيجة shamela_verify؛ غياب المفتاح = None (تعذّر)
        self.verified = []
        self.added = {}            # وكيل ← قائمة الوصلات المسجّلة حديثًا

    def ask_notebook(self, nb_id, question, timeout=150):
        self.asked.append((nb_id, question))
        r = self.nb.get(nb_id, {"ok": True, "answer": "جواب " + nb_id, "refs": [{"n": 1, "text": "مقطع حرفي من " + nb_id}], "note": ""})
        if isinstance(r, Exception):
            raise r
        return r

    def ensure_agent(self, agent_id, libraries):
        self.ensured.append((agent_id, list(libraries)))
        r = self.ensure.get(agent_id, {"ok": True, "note": ""})
        if isinstance(r, Exception):
            raise r
        return dict(r, added=self.added.get(agent_id, []))

    def source_note(self, libraries, evidence_path=""):
        self.notes.append((list(libraries), evidence_path))
        out = ""
        if libraries:
            out += "\n\n[مصادر: " + "،".join(libraries) + "]"
        if evidence_path:
            out += "\n[أدلة: " + str(evidence_path) + "]"
        return out

    def write_evidence(self, path, items):
        self.written.append(items)
        Path(path).write_text("\n".join(i["title"] + ":" + i["answer"] for i in items), encoding="utf-8")
        return str(path)

    def shamela_verify(self, quote):
        self.verified.append(quote)
        return self.verify.get(quote)


class JudgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.t = FakeT()
        self.s = FakeS()
        judge.T, judge.DATA, judge.POLL, judge.S = self.t, self.tmp, 0.01, self.s
        judge.ROUNDS.clear()
        judge.set_default_judge("agy")

    def tearDown(self):
        judge.S = None
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
        r = judge.start_round("س", ["claude", "codex"], judge="claude", judge_may_answer=True)
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

    def test_judge_policy_length_and_cleaning(self):
        r = judge.start_round("س", ["claude", "codex"], judge="claude", length="موجز")
        self.assertEqual(list(r["agents"]), ["codex"])
        self.assertIn("موجز", self.t.sent[-1][1])
        with self.assertRaises(ValueError):
            judge.start_round("س", ["claude"], judge="claude")
        with self.assertRaises(ValueError):
            judge.start_round("س", ["codex"], length="كبير")
        self.assertEqual(judge._strip_notes("سأذكر مثالًا وأتحقق من المصدر.\n\nالحديث الموقوف هو قول الصحابي.\n○ Thought for 26.1s\n&gt; نص"), "الحديث الموقوف هو قول الصحابي.\n&gt; نص")
        self.assertEqual(judge._strip_notes("استعمل &amp;lt; في الكود"), "استعمل &amp;lt; في الكود")
        self.assertEqual(judge._strip_notes("سأذكر أن الحكم واجب.\n\nالدليل هنا."), "سأذكر أن الحكم واجب.\n\nالدليل هنا.")

    def test_citation_index_and_score_validation(self):
        from unittest.mock import patch
        r = judge.start_round("س", ["codex"], judge="agy")
        rr = judge.ROUNDS[r["round_id"]]
        rr["agents"]["codex"]["answer"] = 'نص «هذه عبارة طويلة للاختبار في المصدر» [1]\n\nالمصادر\n[1] مؤلف، كتاب، ص ١، https://example.org/page'
        with patch('citation_check.fetch_source', return_value='هذه عبارة طويلة للاختبار في المصدر'):
            path, key = judge.build_answers_file(rr)
        self.assertIn('ج1-١ | ✅', path.read_text())
        verdict = '## تقييم كل جواب\nالدقة: ٨ من ١٠\nالتوثيق: ٧ من ١٠\nالشمول: ٦ من ١٠\nالدرجة الكلية: ١٠\n## جدول التحقق من الإحالات\n| ج1-١ | ✅ |\n| ج1-١ | ✅ |'
        result = judge._finish_verdict(rr, verdict, [], key, 'agy')
        self.assertIn('الدرجة الكلية: ٢١', result)
        self.assertIn('تكرار', result)

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

    # ---------- سلسلة المصادر ----------
    def _src(self, mode="answer", nbs=("abcdef123456",), libs=("shamela",)):
        return {"libraries": list(libs), "notebooks": [{"id": n, "title": "دفتر " + n[:3]} for n in nbs], "nb_mode": mode}

    def _nbid(self, nid):
        return "nb_" + nid[:8]

    def test_no_sources_is_unchanged(self):
        r = judge.start_round("س", ["codex"], sources={"libraries": [], "notebooks": []})
        self.assertNotIn("sources", r)
        self.assertNotIn("sources", judge.start_round("س", ["codex"], sources=None))
        self.assertEqual(self.s.ensured, [])
        self.assertEqual(self.t.sent[0][1], "س" + judge.CITE_NOTE)

    def test_notebook_pseudo_answerer_answer_mode(self):
        r = judge.start_round("س", ["codex"], sources=self._src("answer"))
        rid, nb = r["round_id"], self._nbid("abcdef123456")
        self.assertEqual(r["agents"][nb]["kind"], "notebook")
        self.assertEqual(r["agents"][nb]["name"], "دفتر: دفتر abc")
        self.assertEqual(r["agents"][nb]["nb_id"], "abcdef123456")
        self.assertEqual(r["sources"]["nb_mode"], "answer")
        self.assertEqual(self.t.sent[0][0], ["codex"])                 # يُرسل فورًا والدفتر يجيب بالتوازي
        s = self.wait(lambda: (lambda x: x if x["agents"][nb]["state"] == "done" else None)(judge.round_status(rid)))
        self.assertEqual(s["agents"][nb]["answer"], "جواب abcdef123456")
        self.assertEqual(s["agents"][nb]["refs"], [{"n": 1, "text": "مقطع حرفي من abcdef123456"}])
        self.assertEqual(self.s.asked, [("abcdef123456", "س")])
        self.assertNotIn(nb, [i for ids, _ in self.t.sent for i in ids])     # لا طرفية للدفتر
        self.assertEqual(self.s.ensured, [("codex", ["shamela"])])

    def test_notebook_reference_mode_waits_and_writes_evidence(self):
        r = judge.start_round("س", ["codex"], sources=self._src("reference"))
        rid = r["round_id"]
        sent = self.wait(lambda: self.t.sent)                               # أُرسل بعد انتهاء الدفتر
        self.assertEqual(r["agents"]["codex"]["state"], "waiting")
        ev = Path(self.tmp) / "rounds" / rid / "evidence.md"
        self.assertTrue(ev.is_file())
        self.assertIn("evidence.md", sent[0][1])
        self.assertEqual(self.s.written[0][0]["refs"][0]["text"], "مقطع حرفي من abcdef123456")
        self.assertEqual(judge.round_status(rid)["evidence_path"], str(ev))

    def test_sources_only_round_without_terminal_agents(self):
        r = judge.start_round("س", [], sources=self._src("answer"), judge="agy")
        rid, nb = r["round_id"], self._nbid("abcdef123456")
        self.assertEqual(list(r["agents"]), [nb])
        self.wait(lambda: judge.round_status(rid)["agents"][nb]["state"] == "done")
        self.assertEqual(self.t.sent, [])
        with self.assertRaises(ValueError):
            judge.start_round("س", [], sources=None)

    def test_ensure_agent_failure_does_not_stop_round(self):
        self.s.ensure["codex"] = {"ok": False, "note": "هذا الوكيل لا يدعم المصادر بعد"}
        r = judge.start_round("س", ["codex", "claude"], judge="agy", sources=self._src("answer", nbs=()))
        self.assertIn("لا يدعم", r["agents"]["codex"]["note"])
        self.assertTrue(any("لا يدعم" in v for v in r["source_issues"].values()))
        self.assertEqual(sorted(i for ids, _ in self.t.sent for i in ids), ["claude", "codex"])      # الجولة مضت
        self.s.ensure["codex"] = RuntimeError("boom")
        r = judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer", nbs=()))
        self.assertIn("codex", r["source_issues"])

    def test_added_connectors_restart_live_agent_before_broadcast(self):
        self.s.added = {"codex": ["zajel_shamela"]}
        self.t.st["codex"] = "idle"                      # جلسة حيّة هادئة
        r = judge.start_round("س", ["codex", "claude"], judge="agy", sources=self._src("answer", nbs=()))
        self.assertEqual(self.t.events[0], ("restart", "codex"))      # قبل أي إرسال
        self.assertNotIn(("restart", "claude"), self.t.events)
        self.assertLess(self.t.events.index(("restart", "codex")), min(i for i, e in enumerate(self.t.events) if e[0] == "broadcast"))
        self.assertIn("أُعيد تشغيل الوكيل لتفعيل وصلات المصادر", r["agents"]["codex"]["note"])

    def test_added_but_session_stopped_or_busy(self):
        self.s.added = {"codex": ["zajel_shamela"]}
        self.t.st["codex"] = "stopped"                   # لا جلسة: broadcast يبدأ جلسة جديدة
        judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer", nbs=()))
        self.assertNotIn(("restart", "codex"), self.t.events)
        self.t.events.clear()
        self.t.st["codex"] = "working"                   # مشغول: لا نقطع عمله
        r = judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer", nbs=()))
        self.assertNotIn(("restart", "codex"), self.t.events)
        self.assertIn("أعد تشغيل", r["agents"]["codex"]["note"])
        self.assertTrue(self.t.sent)

    def test_no_added_means_no_restart(self):
        self.t.st["codex"] = "idle"
        judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer", nbs=()))
        self.assertNotIn(("restart", "codex"), self.t.events)
        self.assertTrue(self.t.sent)

    def test_restart_failure_does_not_stop_round(self):
        self.s.added = {"codex": ["zajel_shamela"]}
        self.t.st["codex"] = "idle"
        self.t.restart_err = OSError("tmux")
        r = judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer", nbs=()))
        self.assertIn("أعد تشغيل هذا الوكيل بنفسك", r["agents"]["codex"]["note"])
        self.assertEqual(self.t.sent[0][0], ["codex"])                # أُرسل السؤال رغم الفشل
        self.assertTrue(any("أعد تشغيل" in v for v in r["source_issues"].values()))

    def test_round_with_real_sources_module_and_fake_runner(self):
        """الوحدة الحقيقية sources بمنفّذ أوامر وهمي: تطابق الأشكال بين judge وsources في الوضعين."""
        import sources
        calls = []

        def run(argv, timeout, inp=None):
            calls.append(argv)
            if argv[:2] == ["notebooklm", "ask"]:
                return 0, json.dumps({"answer": "جواب الدفتر [1]", "references": [{"citation_number": 1, "cited_text": "نص حرفي من الدفتر"}]}), ""
            if argv[1:3] == ["mcp", "list"]:
                return 0, "zajel_shamela zajel_aljam3", ""
            return 0, "", ""
        old_data, old_run = sources.DATA, sources.RUN
        sources.DATA, sources.RUN, judge.S = Path(self.tmp), run, sources
        try:
            for mode in ("answer", "reference"):
                with self.subTest(mode=mode):
                    self.t.sent.clear()
                    r = judge.start_round("س", ["codex"], judge="agy", sources=self._src(mode, libs=("shamela", "aljam3:3")))
                    rid, nb = r["round_id"], self._nbid("abcdef123456")
                    s = self.wait(lambda: (lambda x: x if x["agents"][nb]["state"] == "done" else None)(judge.round_status(rid)))
                    self.assertEqual(s["agents"][nb]["answer"], "جواب الدفتر [1]")
                    self.assertEqual(s["agents"][nb]["refs"], [{"n": 1, "text": "نص حرفي من الدفتر"}])
                    self.wait(lambda: self.t.sent)
                    sent = self.t.sent[-1][1]
                    self.assertIn("المكتبة الشاملة", sent)                 # source_note الحقيقي
                    self.assertIn("library_id: 3", sent)
                    self.assertEqual(("evidence.md" in sent), mode == "reference")
                    if mode == "reference":
                        ev = (Path(self.tmp) / "rounds" / rid / "evidence.md").read_text(encoding="utf-8")
                        self.assertIn("نص حرفي من الدفتر", ev)
                        self.assertIn("جواب الدفتر [1]", ev)
                    self.assertEqual(s["source_issues"], {})
            self.assertTrue(any(c[:2] == ["notebooklm", "ask"] and "--new" not in c for c in calls))
        finally:
            sources.DATA, sources.RUN = old_data, old_run

    def test_source_note_appended_to_broadcast(self):
        judge.start_round("س", ["codex"], sources=self._src("answer", libs=("shamela", "aljam3:3")))
        self.assertTrue(self.t.sent[0][1].startswith("س"))
        self.assertTrue(self.t.sent[0][1].endswith("[مصادر: shamela،aljam3:3]"))
        self.assertEqual(self.s.notes[0], (["shamela", "aljam3:3"], ""))

    def test_notebook_failure_listed_in_verdict_appendix(self):
        self.s.nb["abcdef123456"] = {"ok": False, "answer": "", "refs": [], "note": "انتهت مهلة الدفتر"}
        r = judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer"))
        rid, nb = r["round_id"], self._nbid("abcdef123456")
        s = self.wait(lambda: (lambda x: x if x["agents"][nb]["state"] == "error" else None)(judge.round_status(rid)))
        self.assertEqual(s["agents"][nb]["note"], "انتهت مهلة الدفتر")
        out = judge._finish_verdict(judge.ROUNDS[rid], "## الخلاصة الموحدة\nحكم", [], {}, "agy")
        self.assertIn("مصادر تعذّر الوصول إليها", out)
        self.assertIn("انتهت مهلة الدفتر", out)
        self.s.nb["abcdef123456"] = RuntimeError("x")                       # استثناء لا يُسقط الجولة
        r = judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer"))
        self.wait(lambda: judge.round_status(r["round_id"])["agents"][nb]["state"] == "error")

    def test_reask_and_deepen_for_notebook(self):
        r = judge.start_round("س", ["codex"], sources=self._src("answer"))
        rid, nb = r["round_id"], self._nbid("abcdef123456")
        self.wait(lambda: judge.round_status(rid)["agents"][nb]["state"] == "done")
        n = len(self.t.sent)
        self.s.nb["abcdef123456"] = {"ok": True, "answer": "جواب جديد", "refs": [], "note": ""}
        r = judge.reask(rid, nb)
        self.assertEqual(r["agents"][nb]["state"], "waiting")
        self.assertEqual(r["agents"][nb]["answer"], "")
        self.wait(lambda: judge.round_status(rid)["agents"][nb]["answer"] == "جواب جديد")
        self.assertEqual(len(self.s.asked), 2)
        self.assertEqual(len(self.t.sent), n)                               # لا إرسال للطرفية
        with self.assertRaises(ValueError) as cm:
            judge.deepen(rid, nb)
        self.assertIn("عمّق", str(cm.exception))
        with self.assertRaises(ValueError):
            judge.reask(rid, nb, deep=True)
        self.assertFalse(judge.set_selected(rid, nb, False)["agents"][nb]["selected"])

    def test_answers_file_has_notebooks_unanonymized_with_passages(self):
        r = judge.start_round("س", ["claude", "codex"], judge="claude", judge_may_answer=True, sources=self._src("answer"))
        rid, nb = r["round_id"], self._nbid("abcdef123456")
        self.wait(lambda: judge.round_status(rid)["agents"][nb]["state"] == "done")
        with judge._LOCK:
            rr = judge.ROUNDS[rid]
            rr["agents"]["claude"]["answer"] = "أنا Claude أرى كذا"
            rr["agents"]["codex"]["answer"] = "أنا Codex أرى غيره"
            rr["agents"][nb]["answer"] = "من دفتر Claude الخاص"
        p, key = judge.build_answers_file(rr)
        txt = p.read_text(encoding="utf-8")
        self.assertIn("من مصادر المستخدم (دفتر: دفتر abc)", txt)
        self.assertIn("«مقطع حرفي من abcdef123456»", txt)
        self.assertIn("المقاطع الحرفية", txt)
        self.assertIn("من دفتر Claude الخاص", txt)                          # لم يُجهَّل
        self.assertEqual(sorted(key), ["أ", "ب"])                          # الرموز للوكلاء وحدهم
        head = txt.split("## جواب من مصادر المستخدم")[0]
        self.assertNotIn("Claude", head.split("## الجواب (أ)")[-1])

    def test_judge_prompts_mention_notebooks_and_unverified(self):
        r = judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer"))
        rr = judge.ROUNDS[r["round_id"]]
        for p in (judge.judge_prompt(rr, "/a/answers.md"), judge.web_judge_prompt(rr)):
            self.assertIn("مصادر المستخدم", p)
            self.assertIn("وافقتها أجوبة الوكلاء", p)
            self.assertIn("غير متحقق", p)
        plain = judge.judge_prompt({"round_id": "x", "judge_also_answers": False}, "/a")
        self.assertNotIn("مصادر المستخدم", plain)
        nonb = judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer", nbs=()))
        p = judge.judge_prompt(judge.ROUNDS[nonb["round_id"]], "/a")
        self.assertNotIn("وافقتها", p)
        self.assertIn("غير متحقق", p)

    def test_strip_codex_memory_block_and_agy_action_lines(self):
        codex = "الجواب\n\n**المصادر**\n[1] مؤلف، كتاب\n\n<oai-mem-citation>\n<citation_entries>\nMEMORY.md:1-2|note=[x]\n</citation_entries>\n</oai-mem-citation>"
        self.assertEqual(judge._strip_notes(codex), "الجواب\n\n**المصادر**\n[1] مؤلف، كتاب")
        self.assertEqual(judge._strip_notes("الجواب\n<oai-mem-citation>\nناقص بلا إغلاق"), "الجواب")      # كتلة غير مغلقة
        agy = "… 9 more actions (5 reads, 4 tools) …\n  نعم هذا هو الجواب.\n⋯ 2 more action (1 read) ⋯\n  تتمة"
        self.assertNotIn("more actions", judge._strip_notes(agy))
        self.assertNotIn("more action", judge._strip_notes(agy))
        self.assertIn("نعم هذا هو الجواب.", judge._strip_notes(agy))
        self.assertIn("تتمة", judge._strip_notes(agy))

    def test_answers_file_notebook_without_passages_and_with_sources(self):
        self.s.nb["abcdef123456"] = {"ok": True, "answer": "جواب الدفتر", "refs": [], "sources": ["كتاب أ.pdf"], "note": ""}
        r = judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer", nbs=("abcdef123456",)))
        rid, nb = r["round_id"], self._nbid("abcdef123456")
        self.wait(lambda: judge.round_status(rid)["agents"][nb]["state"] == "done")
        rr = judge.ROUNDS[rid]
        self.assertEqual(rr["agents"][nb]["sources"], ["كتاب أ.pdf"])
        p, _ = judge.build_answers_file(rr)
        txt = p.read_text(encoding="utf-8")
        self.assertIn("لم يُرجع الدفتر مقاطع حرفية", txt)
        self.assertNotIn("«»", txt)
        self.assertIn("المصادر التي استند إليها الدفتر: كتاب أ.pdf", txt)
        # مقطع بمصدره
        rr["agents"][nb]["refs"] = [{"n": 1, "text": "نص حرفي", "source": "كتاب أ.pdf"}]
        txt = judge.build_answers_file(rr)[0].read_text(encoding="utf-8")
        self.assertIn("1. «نص حرفي» — من: كتاب أ.pdf", txt)
        self.assertNotIn("لم يُرجع الدفتر مقاطع", txt)

    def test_shamela_verification_in_answers_file(self):
        q1, q2, q3 = ("وأجمع عوام أهل العلم على إسقاط نفقة الناشز", "قول آخر طويل بما يكفي للفحص الآلي هنا", "نص ثالث طويل بما يكفي للفحص الآلي هنا")
        self.s.verify = {q1: {"found": True, "where": "المغني، ج٨/ص١٩٥", "in_footnote": False},
                         q2: {"found": True, "where": "كتاب، ج١/ص٢", "in_footnote": True}}
        r = judge.start_round("س", ["codex"], judge="agy", sources=self._src("answer", nbs=()))
        rr = judge.ROUNDS[r["round_id"]]
        rr["agents"]["codex"]["answer"] = ("ن [1] [2] [3]\n\nالمصادر\n[1] ابن قدامة، المغني، ج ٨ ص ١٩٥ «%s»\n[2] مؤلف، كتاب «%s»\n[3] مؤلف، كتاب ثالث «%s»" % (q1, q2, q3))
        p, _ = judge.build_answers_file(rr)
        txt = p.read_text(encoding="utf-8")
        self.assertIn("✅ موثّق | النص موجود في المتن: المغني، ج٨/ص١٩٥", txt)
        self.assertIn("⚠️ فيه خلل | النص موجود في الحاشية", txt)
        self.assertIn("❓ تعذّر التحقق | تعذّر التحقق", txt)                 # الخادم أعاد None
        self.assertIn("shamela", rr["source_issues"])
        out = judge._finish_verdict(rr, "## الخلاصة الموحدة\nx", [], {}, "agy")
        self.assertIn("المكتبة الشاملة: تعذّر خادمها", out)

    def test_no_shamela_verify_without_sources(self):
        r = judge.start_round("س", ["codex"], judge="agy")
        rr = judge.ROUNDS[r["round_id"]]
        rr["agents"]["codex"]["answer"] = "ن [1]\n\nالمصادر\n[1] مؤلف، كتاب «قول طويل بما يكفي للفحص الآلي هنا تمامًا»"
        judge.build_answers_file(rr)
        self.assertEqual(self.s.verified, [])

    def test_sources_validation(self):
        with self.assertRaises(ValueError):
            judge.start_round("س", ["codex"], sources=self._src("bogus"))
        with self.assertRaises(ValueError):
            judge.start_round("س", ["codex"], sources=self._src("answer", nbs=tuple("n%07d" % i + "xx" for i in range(6))))

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

    def test_approves_only_report_file_prompt(self):
        import judge
        t = self.t
        t.sent_keys = []
        t.send = lambda i, text="", keys=None, paste=False: t.sent_keys.append(keys)
        t._tail = lambda i, n=6: "Create file\n/data/rounds/r1/verdict.md\nAllow creation of this file?\n> 1. Yes, allow creation"
        self.assertTrue(judge._approve_report_write(t, "agy", "/data/rounds/r1/verdict.md"))
        self.assertEqual(t.sent_keys, [["Enter"]])
        t._tail = lambda i, n=6: "Create file\n/Users/mohamad/Library/Applicatio\nAllow creation of this file?\n> 1. Yes, allow creation"
        self.assertTrue(judge._approve_report_write(t, "agy", "/Users/mohamad/Library/Application Support/Phone Backup/rounds/r1/verdict.md"))      # مسار مقطوع في الشاشة
        t._tail = lambda i, n=6: "Create file\n/etc/passwd\nAllow creation of this file?\n> 1. Yes, allow creation"
        self.assertFalse(judge._approve_report_write(t, "agy", "/data/rounds/r1/verdict.md"))
        t._tail = lambda i, n=6: "/data/rounds/r1/verdict.md\nAllow this command: rm -rf ~ ?\n> 1. Yes, allow once"
        self.assertFalse(judge._approve_report_write(t, "agy", "/data/rounds/r1/verdict.md"))


if __name__ == "__main__":
    unittest.main()
