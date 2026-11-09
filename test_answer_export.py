import tempfile
import unittest
from pathlib import Path

import answer_export as A

CODEX = """› أريد أن تبحث لي في حكم الجمع في حالة المطر، والدليل
  من الكتاب والسنة
• الجمع بين المغرب والعشاء للمطر جائز عند الجمهور.
  ودليله حديث ابن عباس في صحيح مسلم.
  Worked for 1m 6s • 11:30 PM
› Ask Codex to do anything
"""
AGY_PENDING = """> أريد أن تبحث لي في حكم الجمع
  في حالة المطر
Allow calling this tool?
> 1. Yes, allow tool call
"""


class Screen(unittest.TestCase):
    def test_codex_screen(self):
        q, a = A.from_screen("codex", CODEX)
        self.assertTrue(q.startswith("أريد أن تبحث") and q.endswith("والسنة"))
        self.assertIn("حديث ابن عباس", a)
        self.assertNotIn("Worked for", a)
        self.assertNotIn("Ask Codex", a)

    def test_pending_approval_is_not_an_answer(self):
        q, a = A.from_screen("agy", AGY_PENDING)
        self.assertTrue(q)
        self.assertEqual(a, "")

    def test_short_title(self):
        self.assertEqual(A.short_title("أريد أن تبحث لي في حكم الجمع في حالة المطر، والدليل", "Codex"), "حكم الجمع في حالة المطر Codex")


class Docx(unittest.TestCase):
    def test_build_and_no_overwrite(self):
        from docx import Document
        with tempfile.TemporaryDirectory() as d:
            ans = "## الخلاصة\nالجمع **جائز**.\n- الدليل الأول\n1. أولًا\n| القول | الدليل |\n|---|---|\n| الجواز | حديث |\n```\nprint(1)\n```"
            p = A.build_docx("حكم الجمع Codex", "سؤال؟", ans, "Codex", Path(d) / "x.docx")
            doc = Document(str(p))
            self.assertEqual(doc.paragraphs[0].text, "حكم الجمع Codex")
            self.assertIn("w:bidi", doc.paragraphs[0]._p.xml)
            self.assertEqual(len(doc.tables), 1)
            A.SOURCES["fake"] = lambda cwd: ("سؤال تجربة طويل؟", "جواب كامل يكفي ليُعدّ جوابًا حقيقيًا مكتملًا هنا.")
            r1 = A.export("fake", "Fake", out_dir=d)
            r2 = A.export("fake", "Fake", out_dir=d)
            self.assertNotEqual(r1["path"], r2["path"])
            self.assertTrue(r2["path"].endswith("(2).docx"))


if __name__ == "__main__":
    unittest.main()
