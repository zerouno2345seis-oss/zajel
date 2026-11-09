"""اختبارات بوت زاجل المطوّر (٢.١٦): الأقسام، الأزرار الملوّنة، الرمز على شاشة الماك، مستويات الخطورة، البثّ والإيقاف."""
import time
import types
import unittest
from unittest import mock

import telegram_link as TL
import telegram_more as M

REAL_SEND = TL.send


class Base(unittest.TestCase):
    def setUp(self):
        self.cfg = {"chat_id": 7, "conv": "c", "approve_red": True, "topics": {}}
        self.sent, self.edits, self.api, self.mac = [], [], [], []
        TL.WAITCODE.clear()
        M.PENDING_Y.clear()
        p = [mock.patch.object(TL, "_cfg", lambda: self.cfg), mock.patch.object(TL, "_save_cfg", lambda d: self.cfg.update(d) or self.cfg),
             mock.patch.object(TL, "send", lambda t, c=None, **k: self.sent.append((t, k)) or 1),
             mock.patch.object(TL, "edit", lambda c, m, t, kb=None: self.edits.append((t, kb))),
             mock.patch.object(TL, "_quiet", lambda *a, **k: None),
             mock.patch.object(TL, "_show_on_mac", lambda label, code: self.mac.append(code))]
        for x in p:
            x.start()
            self.addCleanup(x.stop)


class Buttons(Base):
    def test_colored_buttons(self):
        self.assertEqual(TL._b("ن", "d", "success"), {"text": "ن", "callback_data": "d", "style": "success"})
        self.assertNotIn("style", TL._b("ن", "d"))
        self.assertNotIn("style", TL._b("ن", "d", "bogus"))

    def test_commands_match_design(self):
        self.assertEqual([c for c, _ in TL.COMMANDS], "home search inbox watch dls backup files mail term phone clean disks agents talk update settings help".split())
        self.assertTrue(all(d for _, d in TL.COMMANDS))

    def test_reply_keyboard_six_buttons(self):
        self.assertEqual(sum(TL.MAIN_KB, []), ["الرئيسية", "بحث", "الوارد", "المساعد", "المهام", "المزيد"])
        self.assertEqual(TL._kb(), TL.MAIN_KB)

    def test_more_has_all_nineteen_sections(self):
        text, kb = M.screen_more()
        data = [b["callback_data"] for r in kb for b in r]
        for k in M.TITLES:
            self.assertIn("scr:" + k, data)
        self.assertEqual(len(M.TITLES), 19)
        self.assertTrue(all(len(r) <= 3 for r in kb))

    def test_section_errors_do_not_crash(self):
        with mock.patch.dict("sys.modules", {"health": None}):
            text, kb = M.screen_monitor()
        self.assertIn("تعذّر", text)


class Topics(Base):
    def test_send_uses_device_topic(self):
        self.cfg["topics"] = {TL.HOST: 55}
        calls = []
        with mock.patch.object(TL, "_tok", lambda: "T"), mock.patch.object(TL, "_api", lambda t, m, p, timeout=0: calls.append((m, p)) or {"message_id": 9}):
            REAL_SEND("مرحبا", 7)
            self.cfg["topics"] = {}
            REAL_SEND("بلا أقسام", 7)
        self.assertEqual(calls[0][1]["message_thread_id"], 55)
        self.assertNotIn("message_thread_id", calls[1][1])

    def test_ensure_topics_creates_once_and_survives_failure(self):
        made = []
        with mock.patch.object(TL, "_tok", lambda: "T"), mock.patch.dict(TL.STATE, {"gateway": True}), \
                mock.patch.object(TL, "_presence", lambda: {"imac": {}, "mini": {}}), mock.patch.object(TL, "_mail_repo", lambda: None), \
                mock.patch.object(TL, "_api", lambda t, m, p, timeout=0: made.append(p["name"]) or {"message_thread_id": 100 + len(made)}):
            TL.ensure_topics()
            TL.ensure_topics()
        self.assertEqual(len(made), 2)
        self.assertEqual(self.cfg["topics"], {"imac": 101, "mini": 102})
        self.cfg["topics"] = {}

        def boom(*a, **k):
            raise ValueError("not enabled")
        with mock.patch.object(TL, "_tok", lambda: "T"), mock.patch.dict(TL.STATE, {"gateway": True}), \
                mock.patch.object(TL, "_presence", lambda: {"imac": {}}), mock.patch.object(TL, "_api", boom):
            TL.ensure_topics()
            err = TL.STATE.get("topics_error", "")
        self.assertEqual(self.cfg["topics"], {})
        self.assertIn("Threaded Mode", err)

    def test_route_by_topic(self):
        self.cfg["topics"] = {"imac": 11, "mini": 12}
        got = []
        pres = {"imac": {"ts": time.time()}, "mini": {"ts": time.time()}}
        with mock.patch.object(TL, "_presence", lambda: pres), mock.patch.object(TL, "HOST", "imac"), \
                mock.patch.object(TL, "_mail_repo", lambda: True), mock.patch.object(TL, "_forward", lambda u, h: got.append(("fwd", h))), \
                mock.patch.object(TL, "_dispatch", lambda u: got.append(("here",))), mock.patch.object(TL, "_target", lambda: "imac"):
            msg = {"chat": {"id": 7}, "text": "مرحبا", "message_thread_id": 12}
            TL._route({"message": msg})
            TL._route({"message": {**msg, "message_thread_id": 11}})
            TL._route({"message": {"chat": {"id": 99}, "text": "x", "message_thread_id": 12}})      # غريب: لا يُوجَّه بقسم
        self.assertEqual(got, [("fwd", "mini"), ("here",), ("here",)])


class RedCode(Base):
    def test_code_shown_on_mac_only_and_expires(self):
        ran = []
        TL.ask_code(7, "حذف", lambda: ran.append(1))
        code = self.mac[0]
        self.assertEqual(len(code), 4)
        self.assertTrue(all(code not in t for t, _ in self.sent))
        TL.WAITCODE[7]["until"] = time.time() - 1
        self.assertTrue(TL._on_code_text(7, code))
        self.assertEqual(ran, [])
        self.assertNotIn(7, TL.WAITCODE)

    def test_three_wrong_tries_cancel(self):
        ran = []
        TL.ask_code(7, "حذف", lambda: ran.append(1))
        bad = "0000" if self.mac[0] != "0000" else "1111"
        for _ in range(3):
            TL._on_code_text(7, bad)
        self.assertNotIn(7, TL.WAITCODE)
        TL._on_code_text(7, self.mac[0])
        self.assertEqual(ran, [])

    def test_plain_text_is_not_swallowed(self):
        TL.ask_code(7, "حذف", lambda: None)
        self.assertFalse(TL._on_code_text(7, "اكتب لي ملخصًا"))
        self.assertIn(7, TL.WAITCODE)

    def test_correct_code_runs_once(self):
        ran = []
        TL.ask_code(7, "حذف", lambda: ran.append(1))
        TL._on_code_text(7, self.mac[0])
        TL._on_code_text(7, self.mac[0])
        self.assertEqual(ran, [1])

    def test_pending_approval_needs_code(self):
        approved = []
        fake = types.SimpleNamespace(pending_list=lambda: [{"id": "p1", "tool": "delete", "preview": {"title": "حذف ٣ ملفات"}, "expires_in": 600, "needs_word": None}],
                                     approve=lambda pid, w="": approved.append(pid), deny=lambda pid: None)
        with mock.patch.dict("sys.modules", {"agent_server": fake}):
            TL._on_callback(7, 3, "ok1:p1")
            self.assertEqual(approved, [])
            TL._on_callback(7, 3, "ok2:p1:0000")          # الزر القديم لم يعد يعتمد شيئًا
            self.assertEqual(approved, [])
            TL._on_code_text(7, self.mac[0])
        self.assertEqual(approved, ["p1"])

    def test_approve_disabled_blocks(self):
        self.cfg["approve_red"] = False
        fake = types.SimpleNamespace(pending_list=lambda: [{"id": "p1", "tool": "d", "preview": {}, "expires_in": 60, "needs_word": None}], approve=lambda *a: 1)
        with mock.patch.dict("sys.modules", {"agent_server": fake}):
            TL._on_callback(7, 3, "ok1:p1")
        self.assertEqual(self.mac, [])


class YellowLevel(Base):
    def test_confirm_requires_summary_first(self):
        ran = []
        with mock.patch.object(M, "_run_yellow", lambda aid, chat: ran.append(aid)):
            M.on_callback(7, 3, "ay2", "sync_run")                  # تأكيد بلا ملخص سابق: مرفوض
            self.assertEqual(ran, [])
            M.on_callback(7, 3, "ay", "sync_run")
            self.assertIn("🟡", self.edits[-1][0])
            M.on_callback(7, 3, "ay2", "sync_run")
            time.sleep(0.2)
            self.assertEqual(ran, ["sync_run"])
            M.on_callback(7, 3, "ay2", "sync_run")                  # لا يتكرر بالزر نفسه
            time.sleep(0.1)
            self.assertEqual(ran, ["sync_run"])

    def test_unknown_action_ignored(self):
        M.on_callback(7, 3, "ay", "format_disk")
        M.on_callback(7, 3, "ay2", "format_disk")
        self.assertEqual(self.edits, [])

    def test_server_stop_goes_through_pending(self):
        calls = []
        fake = types.SimpleNamespace(call=lambda n, a, agent="": calls.append((n, a)) or {"pending": True, "id": "x"})
        with mock.patch.dict("sys.modules", {"agent_server": fake}):
            M.on_callback(7, 3, "sv", "x:123")
        self.assertEqual(calls, [("stop_server", {"pid": 123})])
        self.assertEqual(self.sent, [])            # لا «تم»: بطاقة الموافقة تنتظر


class AccountScreens(Base):
    def test_not_linked_message(self):
        with mock.patch.object(M, "_account", lambda: None):
            text, kb = M.screen("search")
        self.assertIn("ربط حسابك", text)


class StopButton(Base):
    def test_stop_sets_flag_and_stops(self):
        stopped = []
        runner = types.SimpleNamespace(stop=lambda j, w="": stopped.append(j) or True)
        with mock.patch.dict("sys.modules", {"agent_runner": runner}):
            TL._on_callback(7, 3, "stp:j1")
        self.assertEqual(stopped, ["j1"])
        self.assertIn("j1", TL.STOPPED)


if __name__ == "__main__":
    unittest.main()


class InlineMode(Base):
    def setUp(self):
        super().setUp()
        self.answers = []
        p = mock.patch.object(TL, "_quiet", lambda m, p=None, **k: self.answers.append((m, p)))
        p.start()
        self.addCleanup(p.stop)

    def test_unpaired_user_gets_nothing(self):
        TL._on_inline({"id": "q1", "from": {"id": 99}, "query": "المغني"})
        m, p = self.answers[-1]
        self.assertEqual((m, p["results"]), ("answerInlineQuery", []))

    def test_results_from_libraries_and_mac_files(self):
        lib = types.SimpleNamespace(linked=lambda: True, A=types.SimpleNamespace(search=lambda q: {"items": [
            {"ref": "1:5", "t": "book", "title": "المغني", "lib_name": "مكتبة", "size_h": "5 م.ب", "link": "https://t.me/m/5"},
            {"ref": "1:6", "t": "link", "title": "رابط", "lib_name": "م", "size_h": "—", "link": "https://t.me/m/6"}]}))
        server = types.SimpleNamespace(call=lambda n, a, agent="": {"result": {"entries": [{"name": "المغني.docx", "place": "mac", "path": "/x/المغني.docx"}, {"name": "مجلد", "is_dir": True}]}})
        with mock.patch.object(M, "_account", lambda: lib), mock.patch.dict("sys.modules", {"agent_server": server}):
            TL._on_inline({"id": "q1", "from": {"id": 7}, "query": "المغني"})
        res = self.answers[-1][1]["results"]
        self.assertEqual([r["id"][0] for r in res], ["t", "m"])
        self.assertIn("https://t.me/m/5", res[0]["input_message_content"]["message_text"])
        self.assertTrue(all(len(r["id"].encode()) <= 64 for r in res))
        self.assertTrue(self.answers[-1][1]["is_personal"])

    def test_short_query_empty(self):
        TL._on_inline({"id": "q1", "from": {"id": 7}, "query": "م"})
        self.assertEqual(self.answers[-1][1]["results"], [])

    def test_chosen_mac_file_is_sent_to_bot_chat_only_for_owner(self):
        calls = []
        server = types.SimpleNamespace(call=lambda n, a, agent="": calls.append((n, a)) or {})
        TL.FIND["abc"] = ("mac", "/x/f.pdf")
        with mock.patch.dict("sys.modules", {"agent_server": server}):
            TL._on_chosen({"result_id": "mabc", "from": {"id": 99}})
            self.assertEqual(calls, [])
            TL._on_chosen({"result_id": "mabc", "from": {"id": 7}})
        self.assertEqual(calls, [("send_to_telegram", {"place": "mac", "path": "/x/f.pdf"})])

    def test_inline_updates_handled_locally(self):
        got = []
        with mock.patch.object(TL, "_dispatch", lambda u: got.append("here")), mock.patch.object(TL, "_forward", lambda u, h: got.append("fwd")), \
                mock.patch.object(TL, "_target", lambda: "other"), mock.patch.object(TL, "_presence", lambda: {"other": {"ts": time.time()}}):
            TL._route({"inline_query": {"id": "1", "from": {"id": 7}, "query": "x"}})
        self.assertEqual(got, ["here"])
