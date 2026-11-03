import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import council_agents as ca


class CouncilAgentsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        ca.init(self.tmp.name)
        self.old_runner = ca._RUNNER
        self.old_profiles = ca._PROFILES.copy()

    def tearDown(self):
        ca._RUNNER = self.old_runner
        ca._PROFILES = self.old_profiles
        self.tmp.cleanup()

    def run_fake(self, body, env=None):
        calls = []

        def runner(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return __import__("subprocess").Popen([sys.executable, "-c", body], **kwargs)

        ca._RUNNER = runner
        with mock.patch.object(ca, "can_run", return_value=True), mock.patch.object(ca.shutil, "which", return_value=sys.executable):
            result = ca.run("claude", "اختبار", timeout=5)
        return result, calls

    def test_large_arabic_output_does_not_block(self):
        body = "import sys; sys.stdout.write('ع' * 200000); sys.stdout.flush()"
        result, _ = self.run_fake(body)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["text"]), 200000)

    def test_environment_is_allowlisted(self):
        os.environ["ZAJEL_SECRET_SHOULD_NOT_PASS"] = "secret"
        try:
            result, calls = self.run_fake("print('ok')")
            self.assertTrue(result["ok"])
            env = calls[0][1]["env"]
            self.assertNotIn("ZAJEL_SECRET_SHOULD_NOT_PASS", env)
            self.assertEqual(set(env), {"HOME", "USER", "LOGNAME", "SHELL", "LANG", "TERM", "TMPDIR", "PATH"})
        finally:
            os.environ.pop("ZAJEL_SECRET_SHOULD_NOT_PASS", None)

    def test_stop_kills_process_and_reports_stopped(self):
        body = "import time; print('working', flush=True); time.sleep(5)"
        calls = []

        def runner(cmd, **kwargs):
            calls.append(kwargs)
            return __import__("subprocess").Popen([sys.executable, "-c", body], **kwargs)

        ca._RUNNER = runner
        count = [0]

        def stop():
            count[0] += 1
            return count[0] > 5

        with mock.patch.object(ca, "can_run", return_value=True), mock.patch.object(ca.shutil, "which", return_value=sys.executable):
            result = ca.run("claude", "اختبار", should_stop=stop, timeout=4)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "stopped")

    def test_nonzero_with_text_is_partial_success(self):
        result, _ = self.run_fake("import sys; print('Error: نص مفيد'); sys.exit(3)")
        self.assertTrue(result["ok"])
        self.assertTrue(result["partial"])
        self.assertIn("Error:", result["text"])

    def test_command_construction_for_each_agent(self):
        profile = ca._default("opencode")
        answer = Path(self.tmp.name) / "answer"
        expected = {
            "claude": ("-p", "--output-format", "stream-json", "--allowedTools", "--disallowedTools"),
            "codex": ("exec", "--skip-git-repo-check", "-s", "read-only", "--json", "-o", "--search"),
            "agy": ("-p", "--mode", "plan", "--output-format", "stream-json"),
            "hermes": ("-z", "--reasoning"),
            "opencode": ("run", "--agent", "plan", "--variant", "--format", "json"),
        }
        for agent_id, tokens in expected.items():
            with self.subTest(agent=agent_id):
                cmd = ca._command(agent_id, "prompt", profile, "deep", [], answer)
                for token in tokens:
                    self.assertIn(token, cmd)

    def test_profile_defaults_and_persistence(self):
        self.assertEqual(ca.set_profile("claude", {})["effort"], "high")
        self.assertTrue(ca.profiles()["claude"]["enabled"])
        ca.set_profile("claude", {"model": "model-x", "effort": "bad"})
        self.assertEqual(ca.profiles()["claude"]["effort"], "high")
        ca.init(self.tmp.name)
        self.assertEqual(ca.profiles()["claude"]["model"], "model-x")


if __name__ == "__main__":
    unittest.main()
