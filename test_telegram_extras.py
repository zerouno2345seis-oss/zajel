import tempfile
import unittest
from unittest import mock

import telegram_extras as X
import telegram_link as TL
import terminal as T

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sent, self.edits = [], []
        p = [mock.patch.object(TL, "DATA", self.tmp), mock.patch.object(TL, "send", lambda t, c=None, kb=None, reply_kb=None: self.sent.append((t, kb)) or 1),
             mock.patch.object(TL, "edit", lambda c, m, t, kb=None: self.edits.append((t, kb))),
             mock.patch.object(TL, "_quiet", lambda *a, **k: None),
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
                mock.patch.object(X, "_screen_of", lambda i: ("شاشة", [])):
            X.on_special(7, "tsend", "/tsend claude تابع العمل")
            key, p = next(iter(X.CONFIRM.items()))
            self.assertEqual(sent, [])
            X.on_callback(7, 3, "tm", f"ok:{key}:0000" if p["code"] != "0000" else f"ok:{key}:1111")
            self.assertEqual(sent, [])               # رمز خاطئ
            X.on_callback(8, 3, "tm", f"ok:{key}:{p['code']}")
            self.assertEqual(sent, [])               # محادثة أخرى
            X.on_callback(7, 3, "tm", f"ok:{key}:{p['code']}")
            self.assertEqual(sent, [("claude", "تابع العمل", ["Enter"])])
            self.assertNotIn(key, X.CONFIRM)

    def test_waiting_text_flow_and_unknown_agent(self):
        with self.assertRaises(ValueError):
            X.on_special(7, "tsend", "/tsend nope hello")
        X.WAITING[7] = "claude"
        self.assertTrue(X.pending_text(7, "اكتب كذا"))
        self.assertEqual(next(iter(X.CONFIRM.values()))["text"], "اكتب كذا")
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
            key, p = next(iter(X.CONFIRM.items()))
            self.assertEqual(stopped, [])
            X.on_callback(7, 3, "tm", f"ok:{key}:{p['code']}")
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
