import tempfile
import time
import unittest
from unittest import mock

import agent_health as ah


class T(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        ah.init(self.td)

    def test_version_parse(self):
        self.assertEqual(ah.parse_version("2.1.296 (Claude Code)"), "2.1.296")
        self.assertEqual(ah.parse_version("codex-cli 0.146.0"), "0.146.0")
        hermes = "⚠ install out of sync (npm: not installed or outdated) — run `hermes pm install`\nHermes Agent v0.21.5+8836.g84692b7 (2026.9.24)\n"
        self.assertEqual(ah.parse_version(hermes), "0.21.5+8836.g84692b7")
        self.assertIsNone(ah.parse_version("\x1b[33mwarning\x1b[0m"))

    def test_due(self):
        self.assertTrue(ah.due("pi"))
        ah._state["checks"]["pi"] = {"at": time.time() - 100}
        self.assertFalse(ah.due("pi"))
        self.assertTrue(ah.due("pi", force=True))
        ah._state["checks"]["pi"]["at"] = time.time() - 90000
        self.assertTrue(ah.due("pi"))

    def test_classify(self):
        b = {"id": "pi", "version": "1.0", "ok": True, "slow": False, "outdated": False}
        self.assertEqual(ah.classify(b), "ok")
        self.assertEqual(ah.classify(dict(b, outdated=True)), "outdated")
        self.assertEqual(ah.classify(dict(b, slow=True, outdated=True)), "slow")
        self.assertEqual(ah.classify(dict(b, ok=False)), "broken")
        self.assertTrue(ah.is_outdated("1.9.0", "1.10.0"))
        self.assertFalse(ah.is_outdated("1.5.0", "1.5.0"))

    def _patched(self, secs):
        return mock.patch.multiple(ah, _which=lambda n: "/x/" + n, version=lambda a: "1.0.0",
                                   latest=lambda a: "1.0.0",
                                   smoke=lambda a: {"ok": True, "secs": secs, "error": ""})

    def test_check_and_cache(self):
        with self._patched(25.0):
            d = ah.check("pi")
            self.assertEqual(d["status"], "slow")
            self.assertTrue(d["slow"])
        with mock.patch.object(ah, "smoke", side_effect=AssertionError):
            self.assertEqual(ah.check("pi")["status"], "slow")  # cached
        self.assertIn("pi", ah.status())

    def test_mark_forces_check(self):
        with self._patched(1.0):
            self.assertEqual(ah.check("pi")["status"], "ok")
        self.assertFalse(ah.mark_slow("pi", "a"))
        self.assertTrue(ah.mark_failure("pi", "b"))
        with self._patched(30.0):
            self.assertEqual(ah.check("pi")["status"], "slow")

    def test_update_needs_confirm(self):
        with mock.patch.object(ah, "_exec") as ex:
            r = ah.repair("pi", ["update"])
            self.assertFalse(r[0]["ok"])
            ex.assert_not_called()
            ex.return_value = (0, "done")
            r = ah.repair("pi", ["update"], confirm=True)
            self.assertTrue(r[0]["ok"])
            ex.assert_called_once_with(["pi", "update", "--self"], 45)

    def test_ladder_and_history_cap(self):
        calls = []
        with mock.patch.object(ah, "smoke", side_effect=[{"ok": False, "secs": 1, "error": "x"},
                                                         {"ok": True, "secs": 1, "error": ""}]):
            r = ah.repair("pi", ["smoke", "restart", "smoke", "cleanup"], restart=lambda a: calls.append(a))
        self.assertEqual([s["step"] for s in r], ["smoke", "restart", "smoke"])
        for i in range(70):
            ah.mark_slow("pi", i)
        self.assertEqual(len(ah.history()), 50)

    def test_update_commands(self):
        for a in ah.AGENTS:
            self.assertTrue(ah.update_command(a))
        self.assertIsNone(ah.update_command("zzz"))


if __name__ == "__main__":
    unittest.main()
