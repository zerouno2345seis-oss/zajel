import tempfile
import unittest
from unittest import mock

import telegram_extras as X
import telegram_link as TL
import terminal as T

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sent, self.edits, self.macscreen = [], [], []
        TL.WAITCODE.clear()
        p = [mock.patch.object(TL, "DATA", self.tmp), mock.patch.object(TL, "send", lambda t, c=None, kb=None, reply_kb=None: self.sent.append((t, kb)) or 1),
             mock.patch.object(TL, "edit", lambda c, m, t, kb=None: self.edits.append((t, kb))),
             mock.patch.object(TL, "_quiet", lambda *a, **k: None),
             mock.patch.object(TL, "_show_on_mac", lambda label, code: self.macscreen.append(code)),
             mock.patch.object(TL, "_cfg", lambda: {"chat_id": 7, "conv": "x", "approve_red": True})]
        for x in p:
            x.start()
            self.addCleanup(x.stop)
        X.CONFIRM.clear()
        X.WAITING.clear()


@unittest.skipUnless(T.available(), "tmux غير مثبت")
class Terminal(Base):
    def test_send_needs_code(self):
        sent = []
        with mock.patch.object(T, "send", lambda i, t="", keys=None, paste=False: sent.append((i, t, keys))), \
                mock.patch.object(X, "_screen_of", lambda i: ("شاشة", [])), mock.patch("time.sleep"):
            X.on_special(7, "tsend", "/tsend claude تابع العمل")
            code = self.macscreen[0]
            self.assertEqual(sent, [])
            self.assertFalse(any(code in t for t, _ in self.sent))      # الرمز على شاشة الماك فقط، لا في تيليجرام
            TL._on_code_text(7, "0000" if code != "0000" else "1111")
            self.assertEqual(sent, [])               # رمز خاطئ
            TL._on_code_text(8, code)
            self.assertEqual(sent, [])               # محادثة أخرى
            TL._on_code_text(7, code)
            self.assertEqual(sent, [("claude", "تابع العمل", ["Enter"])])
            self.assertNotIn(7, TL.WAITCODE)

    def test_waiting_text_flow_and_unknown_agent(self):
        with self.assertRaises(ValueError):
            X.on_special(7, "tsend", "/tsend nope hello")
        X.WAITING[7] = "claude"
        self.assertTrue(X.pending_text(7, "اكتب كذا"))
        self.assertIn("اكتب كذا", TL.WAITCODE[7]["label"])
        self.assertFalse(X.pending_text(7, "عادي"))

    def test_safe_keys_only(self):
        sent = []
        with mock.patch.object(T, "send", lambda i, t="", keys=None, paste=False: sent.append(keys)), mock.patch.object(X, "_screen_of", lambda i: ("ش", [])), mock.patch("time.sleep"):
            X.on_callback(7, 3, "tm", "k:claude:Ctrl-C")
            X.on_callback(7, 3, "tm", "k:claude:rm")
        self.assertEqual(sent, [["C-c"]])

    def test_stop_needs_confirm(self):
        stopped = []
        with mock.patch.object(T, "stop", lambda i: stopped.append(i)):
            X.on_callback(7, 3, "tm", "x:claude")
            self.assertEqual(stopped, [])
            TL._on_code_text(7, self.macscreen[0])
        self.assertEqual(stopped, ["claude"])


if __name__ == "__main__":
    unittest.main()


class NotifyRepeatTests(unittest.TestCase):
    def test_repeat_suppressed_errors_pass(self):
        import telegram_link as t
        from unittest import mock
        t._SEEN.clear()
        cfg = dict(t.DEFAULTS, enabled=True, chat_id=1)
        with mock.patch.object(t, "_cfg", return_value=cfg), mock.patch.object(t, "send") as sd, mock.patch("threading.Thread") as th:
            t.notify("done", "اكتمل التحليل بعد 30 ثانية")
            t.notify("done", "اكتمل التحليل بعد 41 ثانية")
            self.assertEqual(th.call_count, 1)
            t.notify("error", "فشل"); t.notify("error", "فشل")
            self.assertEqual(th.call_count, 3)
