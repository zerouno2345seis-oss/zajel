import time
from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(T.available(), "tmux غير مثبت")
class Council(unittest.TestCase):
    FAKE = r'''import sys, re, time
buf = ""
name = sys.argv[1] if len(sys.argv) > 1 else "fake"
print("ready", flush=True)
for line in sys.stdin:
    buf += line
    m = re.search(r"ثم A- ثم (\w+) ثم", buf)
    if m and buf.rstrip().endswith("في أي مكان آخر."):
        tok = m.group(1)
        time.sleep(1)
        print(f"● ⟦A-{tok}⟧")
        print(f"  جواب من {name}: وصل {len(buf)} حرفًا")
        print(f"● ⟦Z-{tok}⟧", flush=True)
        buf = ""
'''

    def setUp(self):
        Path("/tmp/fake_agent.py").write_text(self.FAKE, encoding="utf-8")
        T.SOCK = "zajel-test2"
        T.ANSWER_TIMEOUT = 40
        for i, nm in (("fa", "A"), ("fb", "B"), ("fm", "M")):
            T.BY_ID[i] = {"id": i, "name": nm, "cmd": "python3 -u /tmp/fake_agent.py " + nm}

    def tearDown(self):
        T._t("kill-server")
        for i in ("fa", "fb", "fm"):
            T.BY_ID.pop(i, None)

    def test_round(self):
        r = T.council_start(["fa", "fb"], "ما عاصمة فرنسا؟", main="fm")
        rid = r["id"]
        for _ in range(90):
            v = T.council_view(rid)["round"]
            if v["phase"] in ("done", "stopped"):
                break
            time.sleep(1)
        self.assertEqual(v["phase"], "done", v)
        self.assertIn("جواب من A", v["agents"]["fa"]["answer"])
        self.assertIn("جواب من B", v["agents"]["fb"]["answer"])
        self.assertIn("جواب من M", v["eval"]["answer"])
        self.assertIn("إجابة A", T._eval_prompt(T.COUNCIL[rid]))
