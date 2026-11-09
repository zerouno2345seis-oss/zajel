import json
import unittest
from unittest import mock

import telegram_relay as R


class Relay(unittest.TestCase):
    def test_https_required_and_menu_button(self):
        cfg = {}
        with mock.patch.object(R.TL, "_cfg", lambda: cfg), mock.patch.object(R.TL, "_save_cfg", lambda d: cfg.update(d)), mock.patch.object(R, "_key", lambda: "k"), \
                mock.patch.object(R, "start"), mock.patch.object(R.TL, "_quiet") as q:
            with self.assertRaises(ValueError):
                R.configure("http://evil.example")
            R.configure("https://zajel.example.workers.dev/")
            self.assertEqual(cfg["relay_url"], "https://zajel.example.workers.dev")
            method, params = q.call_args[0]
            self.assertEqual(method, "setChatMenuButton")
            self.assertEqual(params["menu_button"]["web_app"]["url"], "https://zajel.example.workers.dev/")

    def test_serve_one_replies_with_handler_result_and_survives_crash(self):
        sent = []
        with mock.patch.object(R, "_http", lambda m, p, b=None, timeout=0: sent.append((p, b))):
            R.serve_one({"id": "j1", "user": 7, "op": "home"}, handler=lambda r: {"ok": True, "echo": r["op"]})
            R.serve_one({"id": "j2", "user": 7, "op": "x"}, handler=lambda r: 1 / 0)
        self.assertEqual(sent[0], ("/mac/reply", {"id": "j1", "reply": {"ok": True, "echo": "home"}}))
        self.assertIn("تعذّر", sent[1][1]["reply"]["error"])

    def test_poll_dispatches_jobs(self):
        done = []
        with mock.patch.object(R, "_http", lambda m, p, b=None, timeout=0: {"jobs": [{"id": "a"}, {"id": "b"}]}), \
                mock.patch.object(R, "serve_one", lambda j, h=None: done.append(j["id"])), mock.patch("threading.Thread") as th:
            th.side_effect = lambda target, args, daemon: type("T", (), {"start": lambda s: target(*args)})()
            self.assertEqual(R.poll_once(), 2)
        self.assertEqual(done, ["a", "b"])

    def test_key_not_in_status_output(self):
        with mock.patch.object(R, "_key", lambda: "SECRETVALUE"), mock.patch.object(R.TL, "_cfg", lambda: {"relay_url": "https://x.dev"}):
            self.assertNotIn("SECRETVALUE", json.dumps(R.status()))


if __name__ == "__main__":
    unittest.main()


class UserAgent(unittest.TestCase):
    def test_custom_user_agent_sent(self):
        import telegram_relay as R
        seen = {}

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b"{}"

        def fake(req, timeout=0):
            seen["ua"] = req.get_header("User-agent")
            return Resp()
        with mock.patch.object(R, "url", lambda: "https://x.workers.dev"), mock.patch.object(R, "_key", lambda: "k"), mock.patch.object(R.urllib.request, "urlopen", fake):
            R._http("GET", "/mac/poll")
        self.assertEqual(seen["ua"], "zajel-mac/1.0")


class LoopSurvives(unittest.TestCase):
    def test_unexpected_exception_does_not_kill_polling(self):
        import http.client
        import telegram_relay as R
        calls = []

        def poll():
            calls.append(1)
            if len(calls) == 1:
                raise http.client.IncompleteRead(b"x")          # ليس URLError ولا OSError
            R._stop.set()
            return 0
        R._stop.clear()
        with mock.patch.object(R, "url", lambda: "https://x"), mock.patch.object(R, "_key", lambda: "k"), mock.patch.object(R, "poll_once", poll), \
                mock.patch.object(R._stop, "wait", lambda t=None: False):
            R._loop()
        self.assertEqual(len(calls), 2)                          # استمرّ بعد العطل ونجح في الدورة الثانية
        R._stop.clear()
