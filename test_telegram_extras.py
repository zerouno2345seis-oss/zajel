import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

import telegram_extras as X
import telegram_link as TL
import terminal as T

VERDICT = ("## الخلاصة\nالثقة: عالية\nبوينس آيرس.\n\n## الاتفاق\nاتفقا.\n\n## الحكم النهائي\nالعاصمة بوينس آيرس منذ 1880.\n")


def rnd(**kw):
    r = {"id": "r1", "question": "ما عاصمة الأرجنتين؟", "phase": "done", "letters": {"claude": "ب", "hermes": "أ"}, "created": 1,
         "agents": {"claude": {"name": "Claude", "state": "done", "answer": "ج1", "revised": ""}, "hermes": {"name": "Hermes", "state": "done", "answer": "ج2", "revised": "ج2 منقّحة", "partial": True}},
         "eval": {"name": "Claude", "state": "done", "answer": VERDICT}}
    r.update(kw)
    return r


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


class Pure(Base):
    def test_valid_url(self):
        for u in ("https://example.com/hook", "http://localhost:9/x", "http://192.168.1.5/h", "http://127.0.0.1:8/x"):
            self.assertTrue(X.valid_url(u), u)
        for u in ("http://example.com/x", "ftp://a.com", "https://user:pw@a.com/", "javascript:alert(1)", "https:///x", ""):
            self.assertFalse(X.valid_url(u), u)

    def test_sections_and_final(self):
        conf, final, sec = X._final_parts(rnd())
        self.assertEqual(conf, "الثقة: عالية")
        self.assertIn("1880", final)
        self.assertNotIn("اتفقا", final)
        self.assertIn("الاتفاق", sec)

    def test_cfg_roundtrip(self):
        X._save({"depth": "deep"})
        self.assertEqual(X._cfg()["depth"], "deep")
        self.assertEqual(X._cfg()["blind"], True)


class Council(Base):
    def test_ask_starts_round_with_saved_choices(self):
        X._save({"ids": ["hermes"], "main": "hermes", "depth": "deep", "review": True})
        calls = []
        with mock.patch.object(X, "_agents", lambda: [{"id": "claude", "name": "Claude", "direct": True}, {"id": "hermes", "name": "Hermes", "direct": True}]), \
                mock.patch.object(T, "council_start", lambda *a: calls.append(a) or {"ok": True, "id": "r9"}), \
                mock.patch.object(X, "_watch", lambda *a: None):
            X.council_ask(7, "/council ما الحكم؟")
        a = calls[0]
        self.assertEqual((a[0], a[1], a[2]), (["hermes"], "ما الحكم؟", "hermes"))
        self.assertEqual(a[8:], ("deep", True, True, True))
        self.assertEqual(X._cfg()["last"], "r9")
        self.assertIn("بدأ المجلس", self.sent[0][0])

    def test_ask_errors(self):
        with mock.patch.object(X, "_agents", lambda: [{"id": "claude", "name": "Claude", "direct": True}]):
            with self.assertRaises(ValueError):
                X.council_ask(7, "/council")
            X._save({"ids": []})
            with self.assertRaises(ValueError):
                X.council_ask(7, "سؤال")

    def test_deliver_message_and_answers(self):
        with mock.patch.object(X, "_view", lambda rid="": rnd()):
            X.deliver_message(7, "r1")
            text, kb = self.sent[-1]
            self.assertIn("الثقة: عالية", text)
            self.assertIn("1880", text)
            self.assertNotIn("اتفقا", text)
            self.assertTrue(any("cr:web:r1" in b["callback_data"] for row in kb for b in row))
            X.send_answers(7, "r1")
            joined = "\n".join(t for t, _ in self.sent[-2:])
            self.assertIn("الإجابة ب", joined)
            self.assertIn("منقّحة", joined)
            self.assertIn("[جزئية]", joined)

    def test_deliver_without_verdict(self):
        r = rnd(eval={"name": "Claude", "state": "error", "answer": "", "error": "نفد الرصيد"})
        with mock.patch.object(X, "_view", lambda rid="": r):
            X.deliver_message(7, "r1")
        self.assertIn("نفد الرصيد", self.sent[-1][0])

    def test_webhook_post(self):
        got = {}

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                got["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass
        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        with mock.patch.object(X, "_view", lambda rid="": rnd()):
            with self.assertRaises(ValueError):
                X.post_web("r1")                 # لا رابط
            X._save({"webhook": f"http://127.0.0.1:{srv.server_port}/h"})
            self.assertEqual(X.post_web("r1"), 200)
        b = got["body"]
        self.assertEqual(b["confidence"], "الثقة: عالية")
        self.assertEqual(len(b["answers"]), 2)
        self.assertIn("1880", b["final"])

    def test_cweb_command_validates(self):
        with self.assertRaises(ValueError):
            X.on_special(7, "cweb", "/cweb http://example.com/x")
        X.on_special(7, "cweb", "/cweb https://example.com/h")
        self.assertEqual(X._cfg()["webhook"], "https://example.com/h")
        X.on_special(7, "cweb", "/cweb off")
        self.assertEqual(X._cfg()["webhook"], "")

    def test_screen_toggles(self):
        with mock.patch.object(X, "_agents", lambda: [{"id": "claude", "name": "Claude", "direct": True}, {"id": "codex", "name": "Codex", "direct": True}]):
            X.on_callback(7, 5, "cg", "t:codex")
            self.assertIn("codex", X._cfg()["ids"])
            X.on_callback(7, 5, "cg", "m:codex")
            X.on_callback(7, 5, "cg", "d:fast")
            c = X._cfg()
            self.assertEqual((c["main"], c["depth"], c["review"], c["verify"]), ("codex", "fast", False, False))
            self.assertTrue(self.edits)

    def test_routing_through_telegram_link(self):
        with mock.patch.object(X, "_agents", lambda: [{"id": "claude", "name": "Claude", "direct": True}]):
            TL._on_text(7, "/council")
        self.assertIn("مجلس الوكلاء", self.sent[-1][0] if self.sent else self.edits[-1][0])
        calls = []
        with mock.patch.object(X, "council_ask", lambda chat, q, parent="": calls.append(q)):
            TL._on_text(7, "مجلس ما حكم كذا؟")
            TL._on_text(7, "/council ما حكم كذا؟")
        self.assertEqual(len(calls), 2)


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
