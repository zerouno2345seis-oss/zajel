"""اختبار ذاكرة المساعد في مجلد مؤقت فقط (لا يمسّ بيانات المستخدم ولا ذاكرة Hermes الحقيقية)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import assistant_store as S


class MemoryTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        S.init(self.d.name)

    def tearDown(self):
        self.d.cleanup()

    def test_migration_keeps_backup(self):
        (Path(self.d.name) / "assistant_memory.json").write_text(json.dumps([{"id": "a1", "text": "يحب الشرح بتشبيه", "kind": "preference", "pinned": True}]), encoding="utf-8")
        m = S.memory_list()
        self.assertEqual(m[0]["text"], "يحب الشرح بتشبيه")
        self.assertTrue(m[0]["pinned"])
        self.assertTrue((Path(self.d.name) / "assistant_memory.json.bak").exists())
        self.assertTrue((Path(self.d.name) / "assistant_memory.md").exists())

    def test_manual_edit_roundtrip(self):
        r = S.memory_add("لا نحذف شيئًا من مجلد الرسالة", kind="decision", reason="بحث أكاديمي")
        p = Path(self.d.name) / "assistant_memory.md"
        p.write_text(p.read_text(encoding="utf-8") + "§\\nسطر كتبه المستخدم يدويًا بلا وصف\\n".replace("\\n", "\n"), encoding="utf-8")
        m = S.memory_list()
        self.assertEqual(len(m), 2)
        self.assertEqual(m[0]["reason"], "بحث أكاديمي")
        self.assertEqual(m[1]["kind"], "fact")
        self.assertEqual(m[0]["id"], r["id"])

    def test_rating_excludes_and_budget(self):
        a = S.memory_add("معلومة جيدة للاختبار الأول")
        b = S.memory_add("معلومة سيئة للاختبار الثاني")
        S.memory_rate(b["id"], -1)
        p = S.memory_prompt("اختبار")
        self.assertIn(a["id"], p)
        self.assertNotIn(b["id"], p)
        for i in range(60):
            S.memory_add(("عنصر طويل رقم %d " % i) + "كلمة " * 30)
        self.assertLessEqual(S.memory_budget()["used"], S.MEM_BUDGET)

    def test_secrets(self):
        for bad in ("my key " + "sk" + "-abcdefghijklmnopqrstuvwx", "ghp_" + "a1" * 15, "بطاقتي 4111 1111 1111 1111", "user:pass1234@host.com", "x" * 10 + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"):
            self.assertTrue(S.is_secret(bad), bad)
            with self.assertRaises(ValueError):
                S.memory_add(bad)
        for ok in ("يفضّل المصادر الرسمية أولًا في البحث", "رقم الهاتف 0551234 للتواصل", "يحب القهوة صباحًا"):
            self.assertFalse(S.is_secret(ok), ok)

    def test_import_hermes(self):
        home = Path(self.d.name) / "home"
        (home / ".hermes" / "memories").mkdir(parents=True)
        (home / ".hermes" / "memories" / "MEMORY.md").write_text("## عنوان\n- يفضّل المصادر الرسمية أولًا\n- مفتاحه " + "sk" + "-abcdefghijklmnopqrstuvwxyz1234\n§\nيحب الاختصار في الردود\n", encoding="utf-8")
        S.memory_add("يحب الاختصار في الردود")
        with mock.patch.object(Path, "home", return_value=home):
            c = {x["text"]: x["status"] for x in S.memory_import_scan("hermes")}
            self.assertEqual(c["يفضّل المصادر الرسمية أولًا"], "new")
            self.assertEqual(c["يحب الاختصار في الردود"], "dup")
            self.assertEqual([v for k, v in c.items() if "sk-" in k], ["secret"])
            self.assertEqual(len(S.memory_list()), 1)       # المعاينة لا تحفظ
            added, skipped = S.memory_import_commit("hermes", list(c))
            self.assertEqual(added, 1)
            self.assertEqual(len(S.memory_list()), 2)
            with self.assertRaises(ValueError):
                S.memory_import_scan("codex")



class SyncTest(unittest.TestCase):
    def setUp(self):
        self.a = tempfile.TemporaryDirectory(); self.b = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.a.cleanup(); self.b.cleanup()

    def test_two_computers(self):
        S.init(self.a.name)
        x = S.memory_add("معلومة من الكمبيوتر الأول للمزامنة")
        y = S.memory_add("معلومة ستُحذف لاحقًا بين الجهازين")
        text_a = S.memory_dump_text()
        S.init(self.b.name)
        self.assertEqual(S.memory_merge_remote(text_a), (2, 0, 0))
        import time; time.sleep(0.01)
        S.memory_delete(y["id"])                    # الثاني يحذف
        S.memory_rate(x["id"], 1)
        text_b = S.memory_dump_text()
        S.init(self.a.name)
        added, upd, rem = S.memory_merge_remote(text_b)
        self.assertEqual((added, upd, rem), (0, 1, 1))
        ids = [r["id"] for r in S.memory_list()]
        self.assertEqual(ids, [x["id"]])
        self.assertEqual(S.memory_list()[0]["rating"], 1)
        self.assertEqual(S.memory_merge_remote(text_b), (0, 0, 0))     # لا تكرار عند الإعادة


if __name__ == "__main__":
    unittest.main()
