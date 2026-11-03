import time
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
