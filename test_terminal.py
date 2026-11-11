import shutil
import sys
import tempfile
import threading
import time
import types
from pathlib import Path
import unittest
from unittest import mock

import terminal as T


@unittest.skipUnless(T.available(), "tmux غير مثبت")
class Term(unittest.TestCase):
    def setUp(self):
        T.SOCK = "zajel-test"
        T.MON.clear()

    def tearDown(self):
        T._t("kill-server")

    def test_flow(self):
        self.assertTrue(T.start("shell")["started"])
        self.assertFalse(T.start("shell")["started"])
        T.resize("shell", 90, 24)
        T.send("shell", "echo mark-$((5*5))", ["Enter"])
        time.sleep(1)
        s = T.screen("shell")
        self.assertIn("mark-25", s["text"])
        self.assertEqual((s["cols"], s["rows"]), (90, 24))
        self.assertTrue(T.screen("shell", s["hash"]).get("unchanged"))
        self.assertEqual(T.state_of("shell")[0] in ("working", "idle"), True)
        T.stop("shell")
        self.assertEqual(T.state_of("shell")[0], "stopped")

    def test_blocked_keys_and_ids(self):
        T.start("shell")
        with self.assertRaises(ValueError):
            T.send("shell", "", ["rm"])
        with self.assertRaises(ValueError):
            T.start("../etc")

    def test_wait_detection(self):
        T.start("shell")
        T.send("shell", "printf 'Continue? (y/n) '", ["Enter"])
        time.sleep(T.IDLE_SECS + 1)
        self.assertEqual(T.state_of("shell")[0], "idle")   # الطرفية العادية لا تُعدّ منتظِرة؛ الوكلاء فقط


class BroadcastTests(unittest.TestCase):
    def test_broadcast_validation_and_trim(self):
        started, readied, typed = [], [], []
        with mock.patch.object(T, "start", lambda i: started.append(i) or {"ok": True, "started": True}), \
             mock.patch.object(T, "_wait_idle", lambda i, timeout=60: readied.append(i) or "idle"), \
             mock.patch.object(T, "_type_message", lambda i, text: typed.append((i, text))):

            # 1. Empty text rejected
            with self.assertRaises(ValueError):
                T.broadcast(["shell"], "")
            with self.assertRaises(ValueError):
                T.broadcast(["shell"], "   ")

            # 2. Unknown id rejected
            with self.assertRaises(ValueError):
                T.broadcast(["unknown_agent_xyz"], "مرحبا")
            with self.assertRaises(ValueError):
                T.broadcast(["shell", "unknown_agent_xyz"], "مرحبا")

            # 3. Empty ids rejected
            with self.assertRaises(ValueError):
                T.broadcast([], "مرحبا")

            # 4. more than five accepted (up to MAX_BROADCAST), duplicates removed
            ids_input = ["shell", "claude", "codex", "hermes", "agy", "shell2", "claude"]
            res = T.broadcast(ids_input, "رسالة تجربة")
            self.assertTrue(res["ok"])
            self.assertEqual(res["ids"], ["shell", "claude", "codex", "hermes", "agy", "shell2"])

            # 5. Duplicates deduplicated
            res_dedup = T.broadcast(["shell", "shell", "claude", "claude"], "نص")
            self.assertEqual(res_dedup["ids"], ["shell", "claude"])

            # Wait briefly for daemon threads to run
            time.sleep(0.2)
            self.assertTrue(len(started) > 0)
            self.assertTrue(len(readied) > 0)
            self.assertTrue(len(typed) > 0)


class HealthHooks(unittest.TestCase):
    def test_brief_and_gating(self):
        import agent_health as H
        tmp = tempfile.mkdtemp()
        H.init(tmp)
        self.assertEqual(T._health_brief("codex")["status"], "")
        calls = []
        saved = (H.check, H.due)
        H.due = lambda i, force=False: False
        H.check = lambda i, force=False: calls.append(i) or {"status": "ok"}
        try:
            self.assertFalse(T.health_check("codex")["started"])      # لم يحن موعده
            self.assertFalse(T.health_check("nope")["started"])
        finally:
            H.check, H.due = saved
        self.assertIn("agents", T.health_all())
        shutil.rmtree(tmp, ignore_errors=True)


class CustomAgentsAndShortcuts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_data = T.DATA
        T.DATA = Path(self.tmp)
        T._load_custom()
        T._apply_custom()
        self.orig_which = T._which
        T._which = lambda c: "/mock/bin/grok" if (c and str(c).strip().split()[0] == "grok") else self.orig_which(c)

    def tearDown(self):
        T._which = self.orig_which
        T.DATA = self.old_data
        T._load_custom()
        T._apply_custom()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_agent_and_duplicate_builtin_and_missing_cmd(self):
        # 1. Missing command rejected
        with self.assertRaises(ValueError):
            T.agent_add({"id": "custom1", "name": "Fake", "cmd": "nonexistent_binary_xyz"})

        # 2. Add valid agent
        res = T.agent_add({"id": "grok", "name": "Grok", "cmd": "grok", "ask": "grok -p"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["agent"]["id"], "grok")
        self.assertEqual(res["agent"]["name"], "Grok")

        # In custom_get()
        cg = T.custom_get()
        self.assertEqual(len(cg["agents"]), 1)
        self.assertEqual(cg["agents"][0]["id"], "grok")

        # In listing
        agents_list = T.listing()["agents"]
        grok_row = next((a for a in agents_list if a["id"] == "grok"), None)
        self.assertIsNotNone(grok_row)
        self.assertTrue(grok_row.get("custom"))

        # 3. Duplicate id rejected
        with self.assertRaises(ValueError):
            T.agent_add({"id": "grok", "name": "Grok Duplicate", "cmd": "grok"})

        # 4. Builtin id rejected
        with self.assertRaises(ValueError):
            T.agent_add({"id": "claude", "name": "Claude Fake", "cmd": "grok"})
        with self.assertRaises(ValueError):
            T.agent_add({"id": "shell", "name": "Shell Fake", "cmd": "grok"})

    def test_by_id_identity_preserved(self):
        old_by_id = id(T.BY_ID)
        old_agents = id(T.AGENTS)
        T.agent_add({"id": "grok", "name": "Grok", "cmd": "grok", "ask": "grok -p"})
        self.assertEqual(id(T.BY_ID), old_by_id)
        self.assertEqual(id(T.AGENTS), old_agents)
        self.assertIn("grok", T.BY_ID)
        self.assertTrue(T.BY_ID["grok"].get("custom"))

    def test_headless_set_from_ask(self):
        T.agent_add({"id": "grok", "name": "Grok", "cmd": "grok", "ask": "grok -p --flag"})
        self.assertEqual(T.HEADLESS.get("grok"), ["grok", "-p", "--flag"])
        self.assertTrue(T.can_direct("grok"))

        # Remove agent should clean up HEADLESS
        T.agent_remove("grok")
        self.assertNotIn("grok", T.HEADLESS)
        self.assertNotIn("grok", T.BY_ID)

    def test_shortcut_add_remove_and_validation(self):
        # Invalid path rejected
        with self.assertRaises(ValueError):
            T.shortcut_add({"kind": "path", "name": "Bad", "path": "/nonexistent/directory/xyz"})

        # Valid shortcut
        res = T.shortcut_add({"kind": "path", "name": "TempDir", "path": self.tmp})
        self.assertTrue(res["ok"])
        sc = res["shortcut"]
        self.assertTrue(sc["id"].startswith("s"))
        self.assertEqual(len(sc["id"]), 7)  # "s" + 6 hex chars
        self.assertEqual(sc["name"], "TempDir")

        # Agent shortcut
        with self.assertRaises(ValueError):
            T.shortcut_add({"kind": "agent", "name": "BadAgent", "path": self.tmp, "agent": "unknown_agent"})
        res_ag = T.shortcut_add({"kind": "agent", "name": "ClaudeAtTemp", "path": self.tmp, "agent": "claude"})
        self.assertTrue(res_ag["ok"])

        # Remove
        self.assertTrue(T.shortcut_remove(sc["id"])["ok"])
        with self.assertRaises(ValueError):
            T.shortcut_remove("s_not_found")

    def test_open_path_agent_running(self):
        T.agent_add({"id": "grok", "name": "Grok", "cmd": "grok"})

        class MockRes:
            def __init__(self, rc):
                self.returncode = rc
                self.stdout = ""
                self.stderr = ""

        orig_t = T._t
        try:
            def mock_t(*args, **kwargs):
                if args and args[0] == "has-session":
                    return MockRes(0)
                return MockRes(0)

            T._t = mock_t
            res = T.open_path("grok", self.tmp)
            self.assertFalse(res["ok"])
            self.assertTrue(res["running"])
            self.assertIn("يعمل", res["error"])
        finally:
            T._t = orig_t


if __name__ == "__main__":
    unittest.main()
