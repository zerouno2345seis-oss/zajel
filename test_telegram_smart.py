# -*- coding: utf-8 -*-
import types
import unittest
from unittest import mock

import telegram_account_bot as AB
import telegram_smart as S


class Clean(unittest.TestCase):
    def test_json_extraction_and_intake_limits(self):
        d = S.parse_json('نص قبل {"understood":"x","questions":[{"q":"a","options":["1","2"]},{"q":"b","options":[]},{"q":"c","options":["x"]},{"q":"d","options":["y"]}]} بعد')
        c = S.clean_intake(d)
        self.assertEqual(len(c["questions"]), S.MAX_QUESTIONS)
        self.assertEqual(c["questions"][0]["options"], ["1", "2"])
        with self.assertRaises(ValueError):
            S.parse_json("بلا جيسون")

    def test_plan_is_capped_and_sanitised(self):
        plan = S.clean_plan({"search_queries": ["a1", "a2", "a3", "a4", "a5", "a6", "a1"], "channel_queries": ["قنوات"] * 20, "type": "weird",
                             "known_channels": ["@good_chan", "bad name!", "x", "good_chan"]}, "الطلب")
        self.assertEqual(len(plan["search_queries"]), S.MAX_QUERIES)
        self.assertEqual(plan["type"], "all")
        self.assertEqual(plan["known_channels"], ["good_chan"])
        self.assertLessEqual(len(plan["channel_queries"]), 8)
        self.assertEqual(S.clean_plan({}, "الطلب")["search_queries"], ["الطلب"])      # خطة فارغة ← يبحث بنص الطلب

    def test_rank_uses_best_query_variant_then_views(self):
        items = [{"title": "Libro de Elizabeth Clapp", "views": 5}, {"title": "كتاب آخر", "views": 99}, {"title": "Elizabeth Clapp libro", "views": 500}]
        r = S.rank(items, ["Elisabeth Clapp", "إليزابيث كلاب"])
        self.assertEqual([i["views"] for i in r], [500, 5])


class Execute(unittest.TestCase):
    def test_execute_verifies_discovers_searches_and_ranks(self):
        plan = {"summary": "", "channel_queries": ["libros"], "known_channels": ["ghost_chan", "real_chan"], "search_queries": ["Elizabeth Clapp", "Elisabeth Clapp"], "type": "all"}
        found = [{"id": 2, "name": "كبيرة", "username": "big", "count": 900}]
        verified = [{"id": 1, "name": "حقيقية", "username": "real_chan", "count": 10}]

        def fake_search(q, type_="all", per_lib=10, libs_override=None, progress=None, expand=True):
            self.assertFalse(expand)                                # الموظف يستعمل صيغه هو لا التوسيع الآلي
            self.assertEqual([l["id"] for l in libs_override], [1, 2])
            if progress:
                progress(1, 2, "x")
            return {"items": [{"ref": f"{q}:1", "t": "book", "title": "Libro " + q, "views": 1}], "counts": {}}
        with mock.patch.object(S, "verify_known", return_value=verified) as vk, mock.patch.object(S, "discover_many", return_value=found), \
                mock.patch.object(S.A, "search", fake_search):
            prog = []
            r = S.execute(plan, "الطلب", progress=lambda *a: prog.append(a))
        vk.assert_called_once_with(["ghost_chan", "real_chan"])
        self.assertEqual(len(r["items"]), 2)
        self.assertEqual(r["counts"]["all"], 2)
        self.assertIn(1, S.A.TMP_LIBS)                              # التنزيل ممكن قبل أي حفظ
        self.assertEqual(len(prog), 2)

    def test_no_channels_found_raises(self):
        with mock.patch.object(S, "verify_known", return_value=[]), mock.patch.object(S, "discover_many", return_value=[]):
            with self.assertRaises(ValueError):
                S.execute({"channel_queries": [], "known_channels": [], "search_queries": ["q"], "type": "all"}, "الطلب")

    def test_channel_cap(self):
        many = [{"id": i, "name": str(i), "username": "u%d" % i, "count": i} for i in range(100, 160)]
        with mock.patch.object(S, "verify_known", return_value=[]), mock.patch.object(S, "discover_many", return_value=many), \
                mock.patch.object(S.A, "search", lambda *a, **k: {"items": [], "counts": {}}):
            r = S.execute({"channel_queries": ["x"], "known_channels": [], "search_queries": ["q"], "type": "all"}, "الطلب")
        self.assertEqual(len(r["libs"]), S.MAX_CHANNELS)


class Flow(unittest.TestCase):
    def setUp(self):
        self.sent, self.edits = [], []
        S.SM.clear()
        AB.AWAIT.clear()
        AB.RES.clear()
        for x in (mock.patch.object(AB.TL, "send", lambda t, c, **k: self.sent.append((t, k.get("kb"))) or 7),
                  mock.patch.object(AB.TL, "edit", lambda c, m, t, kb=None: self.edits.append(t)),
                  mock.patch.object(S.threading, "Thread", lambda target, args=(), daemon=None: types.SimpleNamespace(start=lambda: target(*args)))):
            x.start()
            self.addCleanup(x.stop)

    def test_full_conversation(self):
        intake = {"understood": "كتب كلاب", "questions": [{"q": "اللغة؟", "options": ["إسبانية", "إنجليزية"]}, {"q": "الصيغة؟", "options": ["PDF"]}]}
        plan = {"summary": "سأبحث بإملاءات", "channel_queries": ["libros pdf"], "known_channels": [], "search_queries": ["Elizabeth Clapp"], "type": "book"}
        item = {"ref": "1:1", "t": "book", "title": "Elizabeth Clapp libro", "size_h": "1 MB", "views": 10, "date": "2020"}
        result = {"items": [item], "counts": {"all": 1, "book": 1}, "libs": [{"id": 1, "name": "قناة", "username": "c", "list": "tmp", "on": True}], "queries": ["Elizabeth Clapp"]}
        calls = []

        def llm(prompt, model="sonnet"):
            calls.append(prompt[:20])
            import json
            return json.dumps(intake if "TASK 1" in prompt else plan)
        with mock.patch.object(S, "llm", llm), mock.patch.object(S, "execute", return_value=result) as ex:
            AB.on_callback(5, 1, "sm")
            self.assertEqual(AB.AWAIT[5], "smart_brief")
            self.assertTrue(AB.pending_text(5, "كتب إليزابيث كلاب"))
            self.assertEqual(AB.AWAIT[5], "smart_ans")
            AB.on_callback(5, 1, "sa:0")                    # السؤال الأول بزر
            self.assertTrue(AB.pending_text(5, "PDF فقط"))   # الثاني بنص حر
            ex.assert_called_once()
            self.assertEqual(ex.call_args[0][0]["search_queries"], ["Elizabeth Clapp"])
        self.assertEqual(S.SM[5]["ans"], [("اللغة؟", "إسبانية"), ("الصيغة؟", "PDF فقط")])
        self.assertEqual(len(AB.RES[5]["items"]), 1)
        text, kb = AB.screen_results(5)
        datas = [b["callback_data"] for r in kb for b in r]
        self.assertIn("ta:g:1:1", datas)
        self.assertNotIn("ta:sl", datas)                     # لا حفظ للقنوات تلقائيًا
        self.assertNotIn(5, AB.AWAIT)

    def test_no_questions_goes_straight_to_search(self):
        with mock.patch.object(S, "llm", lambda p, model="sonnet": '{"understood":"واضح","questions":[],"summary":"s","channel_queries":["x"],"search_queries":["q"],"type":"all"}'), \
                mock.patch.object(S, "execute", return_value={"items": [], "counts": {"all": 0}, "libs": [], "queries": ["q"]}) as ex:
            AB.on_callback(6, 1, "sm")
            AB.pending_text(6, "فيلم واضح")
            ex.assert_called_once()
        self.assertIn("أعد بخطة جديدة", " ".join(b["text"] for r in AB.screen_results(6)[1] for b in r))

    def test_model_failure_offers_simple_search(self):
        def boom(p, model="sonnet"):
            raise ValueError("لا نموذج")
        with mock.patch.object(S, "llm", boom):
            AB.on_callback(8, 1, "sm")
            AB.pending_text(8, "شيء")
        self.assertTrue(any("ta:ss" in str(k) for _, k in self.sent) or any("تعذّر" in e for e in self.edits))


if __name__ == "__main__":
    unittest.main()
