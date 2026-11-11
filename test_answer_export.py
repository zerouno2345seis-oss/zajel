import tempfile
import os
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


class Footnotes(unittest.TestCase):
    def test_citations_become_footnotes(self):
        ans = "جائز [1]، وقيل لا [2].\nوانظر [الموسوعة](https://x.org/a) وحديث مسلم[^m].\n\n## المصادر\n[1] المغني، 2/202.\n[2] المبسوط، 1/149.\n\n[^m]: صحيح مسلم، 705."
        text, notes = A.citations(ans)
        self.assertEqual(notes, ["المغني، 2/202.", "المبسوط، 1/149.", "https://x.org/a", "صحيح مسلم، 705."])
        self.assertNotIn("المصادر", text)
        self.assertNotIn("[1]", text)

    def test_docx_has_red_footnotes_restarting_each_page(self):
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            r = A.export_text("Codex", "سؤال؟", "جائز [1].\n\n## المصادر\n[1] المغني، 2/202.", out_dir=d)
            z = zipfile.ZipFile(r["path"])
            doc, fn, st = z.read("word/document.xml").decode(), z.read("word/footnotes.xml").decode(), z.read("word/settings.xml").decode()
            self.assertIn('w:footnoteReference w:id="1"', doc)
            self.assertIn('numRestart w:val="eachPage"', doc)
            self.assertIn("المغني", fn)
            self.assertIn('w:color w:val="C00000"', fn)
            self.assertIn("footnotePr", st)


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

    def test_mermaid_becomes_picture(self):
        import mermaid_render
        from docx import Document
        self.assertTrue(mermaid_render.is_mermaid("", "flowchart TD\nA-->B"))
        self.assertFalse(mermaid_render.is_mermaid("python", "print(1)"))
        if not mermaid_render.find_mmdc():
            self.skipTest("no mmdc")
        with tempfile.TemporaryDirectory() as d:
            os.environ["PB_DATA"] = d
            p = A.build_docx("م", "س؟", "```mermaid\nflowchart RL\nA[بداية]-->B[نهاية]\n```", "X", Path(d) / "m.docx")
            self.assertEqual(len(Document(str(p)).inline_shapes), 1)



class OpenCodeDB(unittest.TestCase):
    def test_last_question_and_answer_from_db(self):
        import json, sqlite3
        with tempfile.TemporaryDirectory() as d:
            old, A.HOME = A.HOME, Path(d)
            try:
                db = Path(d) / ".local/share/opencode/opencode.db"
                db.parent.mkdir(parents=True)
                con = sqlite3.connect(db)
                con.execute("create table message(id text, session_id text, time_created int, data text)")
                con.execute("create table part(id text, message_id text, session_id text, time_created int, data text)")
                for mid, t, role, parts in [("m1", 1, "user", ["سؤال قديم"]), ("m2", 2, "assistant", ["جواب قديم"]),
                                            ("m3", 3, "user", ["ما حكم المسح على الجوربين؟"]), ("m4", 4, "assistant", ["يجوز عند الجمهور [1].", "المصادر: المغني"])]:
                    con.execute("insert into message values(?,?,?,?)", (mid, "s1", t, json.dumps({"role": role})))
                    for k, txt in enumerate(parts):
                        con.execute("insert into part values(?,?,?,?,?)", (f"{mid}p{k}", mid, "s1", t, json.dumps({"type": "text", "text": txt})))
                con.execute("insert into part values('m4z','m4','s1',4,?)", (json.dumps({"type": "step-finish"}),))
                con.commit(); con.close()
                q, a = A.from_opencode("")
                self.assertEqual(q, "ما حكم المسح على الجوربين؟")
                self.assertEqual(a, "يجوز عند الجمهور [1].\n\nالمصادر: المغني")
            finally:
                A.HOME = old


class PiSessions(unittest.TestCase):
    def test_final_message_without_tool_call_is_the_answer(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            old, A.HOME = A.HOME, Path(d)
            try:
                sd = Path(d) / ".pi/agent/sessions" / ("--" + d.strip("/").replace("/", "-") + "--")
                sd.mkdir(parents=True)
                msg = lambda role, *parts: json.dumps({"type": "message", "message": {"role": role, "content": list(parts)}})
                lines = [msg("user", {"type": "text", "text": "ما حكم كذا؟"}),
                         msg("assistant", {"type": "text", "text": "سأبحث أولًا."}, {"type": "toolCall", "name": "x"}),
                         msg("toolResult", {"type": "text", "text": "نتيجة"}),
                         msg("assistant", {"type": "thinking", "thinking": "..."}, {"type": "text", "text": "الجواب: يجوز [1]."})]
                (sd / "s.jsonl").write_text("\n".join(lines), encoding="utf-8")
                self.assertEqual(A.from_pi(d), ("ما حكم كذا؟", "الجواب: يجوز [1]."))
            finally:
                A.HOME = old

if __name__ == "__main__":
    unittest.main()
