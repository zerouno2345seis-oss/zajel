"""اختبارات واجهة التطبيق المصغّر على الماك: التفويض، مستويات الخطورة في الخادم، الرمز على الشاشة."""
import time
import types
import unittest
from unittest import mock

import miniapp_api as MA
import telegram_link as TL


class Base(unittest.TestCase):
    def setUp(self):
        self.mac, self.ran = [], []
        MA.PENDING.clear()
        p = [mock.patch.object(TL, "_cfg", lambda: {"chat_id": 7}), mock.patch.object(TL, "_show_on_mac", lambda label, code: self.mac.append(code)),
             mock.patch.object(MA, "run", lambda op, a: self.ran.append((op, a)) or {"done": op})]
        for x in p:
            x.start()
            self.addCleanup(x.stop)

    def req(self, op, args=None, user=7, **k):
        return MA.handle({"user": user, "op": op, "args": args or {}, **k})


class Rounds(Base):
    def test_levels(self):
        self.assertEqual(MA.LEVELS["round.start"], "y")                 # يكتب في طرفيات الماك: تأكيد أولًا
        r = self.req("round.start", {"question": "س", "answerers": ["claude"]})
        self.assertEqual(r["needs"], "confirm")
        self.assertEqual(self.ran, [])
        r2 = self.req("round.start", {"question": "س", "answerers": ["claude"]}, confirm=r["token"])
        self.assertTrue(r2["ok"])
        for op in ("round.status", "round.last", "round.select", "round.judge", "round.deepen", "round.send_report", "round.agents"):
            self.assertEqual(MA.LEVELS[op], "g")

    def test_start_forwards_length_and_judge_participation(self):
        fake = types.SimpleNamespace(PERPLEXITY="perplexity", start_round=mock.Mock(
            return_value={"agents": {}, "verdict": "", "deep_answer": ""}))
        with mock.patch.dict("sys.modules", {"judge": fake}):
            MA._round("start", {"question": "س", "answerers": ["codex"],
                                "judge": "codex", "judge_may_answer": True, "length": "موجز"})
        fake.start_round.assert_called_once_with("س", ["codex"], "codex", False, False,
                                                 judge_may_answer=True, length="موجز")

    def test_trim(self):
        big = {"agents": {"a": {"answer": "x" * 20000}}, "verdict": "v" * 40000, "deep_answer": ""}
        v = MA._round_view(big)
        self.assertEqual(len(v["agents"]["a"]["answer"]), MA.ANSWER_CAP)
        self.assertTrue(v["agents"]["a"]["truncated"])


class Auth(Base):
    def test_only_paired_user(self):
        self.assertTrue(self.req("home")["ok"])
        r = self.req("home", user=99)
        self.assertTrue(r["refused"])
        self.assertTrue(self.req("home", user=None)["refused"])
        self.assertEqual(self.ran, [("home", {})])

    def test_unpaired_bot_refuses_everyone(self):
        with mock.patch.object(TL, "_cfg", lambda: {"chat_id": 0}):
            self.assertTrue(self.req("home", user=0)["refused"])

    def test_unknown_op_refused(self):
        self.assertTrue(self.req("shell.exec", {"cmd": "rm -rf /"})["refused"])
        self.assertEqual(self.ran, [])


class Levels(Base):
    def test_green_runs_immediately(self):
        self.assertEqual(self.req("tg.search", {"q": "x"})["data"], {"done": "tg.search"})

    def test_yellow_needs_server_issued_token(self):
        r = self.req("act.sync_run")
        self.assertEqual(r["needs"], "confirm")
        self.assertEqual(self.ran, [])
        bad = self.req("act.sync_run", confirm="forged")
        self.assertEqual(bad["needs"], "confirm")                          # رمز مزوَّر لا ينفع
        self.assertEqual(self.ran, [])
        ok = self.req("act.sync_run", confirm=r["token"])
        self.assertTrue(ok["ok"])
        self.assertEqual(len(self.ran), 1)
        again = self.req("act.sync_run", confirm=r["token"])               # لمرة واحدة
        self.assertEqual(again["needs"], "confirm")
        self.assertEqual(len(self.ran), 1)

    def test_yellow_token_bound_to_op_and_args(self):
        r = self.req("act.sync_run")
        other = self.req("act.phone_connect", confirm=r["token"])
        self.assertEqual(other["needs"], "confirm")
        self.assertEqual(self.ran, [])

    def test_yellow_token_expires(self):
        r = self.req("act.sync_run")
        MA.PENDING[r["token"]]["until"] = time.time() - 1
        self.assertEqual(self.req("act.sync_run", confirm=r["token"])["needs"], "confirm")
        self.assertEqual(self.ran, [])

    def test_red_code_on_mac_only(self):
        r = self.req("act.term_stop", {"agent": "claude"})
        self.assertEqual(r["needs"], "code")
        self.assertNotIn(self.mac[0], str(r))                               # الرمز لا يعود إلى الهاتف
        self.assertEqual(self.ran, [])
        bad = self.req("red.confirm", {"id": r["id"], "code": "0000" if self.mac[0] != "0000" else "1111"})
        self.assertIn("غير صحيح", bad["error"])
        ok = self.req("red.confirm", {"id": r["id"], "code": self.mac[0]})
        self.assertTrue(ok["ok"])
        self.assertEqual(self.ran, [("act.term_stop", {"agent": "claude"})])
        self.assertIn("انتهت", self.req("red.confirm", {"id": r["id"], "code": self.mac[0]})["error"])

    def test_red_three_tries_and_expiry(self):
        r = self.req("act.stop_server", {"pid": 1})
        wrong = "0000" if self.mac[0] != "0000" else "1111"
        for _ in range(3):
            self.req("red.confirm", {"id": r["id"], "code": wrong})
        self.assertIn("انتهت", self.req("red.confirm", {"id": r["id"], "code": self.mac[0]})["error"])
        r2 = self.req("act.stop_server", {"pid": 1})
        MA.PENDING[r2["id"]]["until"] = time.time() - 1
        self.assertIn("انتهت", self.req("red.confirm", {"id": r2["id"], "code": self.mac[-1]})["error"])
        self.assertEqual(self.ran, [])

    def test_red_confirm_needs_authorized_user(self):
        r = self.req("act.term_stop", {"agent": "claude"})
        out = self.req("red.confirm", {"id": r["id"], "code": self.mac[0]}, user=99)
        self.assertTrue(out["refused"])
        self.assertEqual(self.ran, [])

    def test_delete_and_move_delegate_to_guarded_tool(self):
        calls = []
        fake = types.SimpleNamespace(call=lambda n, a, agent="": calls.append(n) or {"pending": True, "id": "p9", "preview": {"title": "حذف"}})
        with mock.patch.dict("sys.modules", {"agent_server": fake}):
            r = self.req("files.delete", {"place": "mac", "items": ["a"]})
            m = self.req("files.move", {"place": "mac", "items": ["a"]})
        self.assertTrue(r["approval"] and m["approval"])
        self.assertEqual(calls, ["delete", "move"])
        self.assertEqual(self.ran, [])                                      # لم يُنفَّذ شيء قبل الموافقة

    def test_every_op_has_a_level_and_labels_for_non_green(self):
        for op, lv in MA.LEVELS.items():
            self.assertIn(lv, ("g", "y", "r"))
            if lv != "g" and op not in MA.DELEGATED_RED:
                self.assertIn(op, MA.LABELS)

    def test_settings_whitelist(self):
        with mock.patch.object(TL, "_save_cfg") as sv:
            MA._act("setting", {"key": "notify_error", "on": True})
            sv.assert_called_once()
            with self.assertRaises(ValueError):
                MA._act("setting", {"key": "approve_red", "on": True})         # الاعتماد من تيليجرام يُفتح من زاجل وحده
