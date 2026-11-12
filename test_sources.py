import io
import json
import os
import sys
import types
import queue
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import sources


class SourcesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        sources.init(self.tmp.name)
        self.old_run = sources.RUN
        self.addCleanup(setattr, sources, "RUN", self.old_run)

    def test_catalog_cache_refresh_and_error(self):
        calls = []
        def run(argv, timeout, inp=None):
            calls.append(argv)
            return 0, json.dumps({"notebooks": [{"id": "123456789", "title": "", "is_owner": True}]}), ""
        sources.RUN = run
        first = sources.catalog()
        self.assertEqual(first["notebooks"], [{"id": "123456789", "title": "(بلا عنوان) 12345678", "owner": True}])
        self.assertEqual(sources.catalog(), first)
        self.assertEqual(len(calls), 1)
        sources.catalog(refresh=True)
        self.assertEqual(len(calls), 2)
        sources.RUN = lambda *a: (1, "", "خطأ")
        self.assertIn("خطأ", sources.catalog(refresh=True)["notebooks_error"])

    def test_selection(self):
        self.assertEqual(sources.get_selection(), {"libraries": [], "notebooks": [], "nb_mode": "answer"})
        selection = {"libraries": ["shamela"], "notebooks": [{"id": "a", "title": "عنوان", "on": True}], "nb_mode": "reference"}
        self.assertEqual(sources.set_selection(selection), selection)
        self.assertEqual(sources.get_selection(), selection)
        for invalid in ({"libraries": ["unknown"]}, {"notebooks": [{"id": str(i)} for i in range(6)]}, {"notebooks": [{"id": "a"}, {"id": "a"}]}, {"nb_mode": "other"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                sources.set_selection(invalid)
        self.assertEqual(sources.get_selection(), selection)

    def test_agents(self):
        for agent in ("codex", "claude", "agy"):
            with self.subTest(agent=agent):
                calls = []
                def run(argv, timeout, inp=None):
                    calls.append(argv)
                    return 0, "", ""
                sources.RUN = run
                self.assertTrue(sources.ensure_agent(agent, ["shamela", "aljam3:1"])["ok"])
                self.assertEqual(len(calls), 3)
                expected_name = "shamela-mcp" if agent == "agy" else "zajel_shamela"
                self.assertIn(expected_name, calls[1])
                self.assertEqual(calls[1][-2:], ["python3", "/Users/mohamad/SHAMILA/server.py"])
                if agent == "claude":
                    self.assertEqual(calls[1][3:5], ["-s", "user"])
                names = "shamela-mcp aljam3" if agent == "agy" else "zajel_shamela zajel_aljam3"
                sources.RUN = lambda *a: (0, names, "")
                self.assertTrue(sources.ensure_agent(agent, ["shamela", "aljam3:3"])["ok"])
                sources.RUN = lambda *a: (1, "", "تعذر")
                self.assertFalse(sources.ensure_agent(agent, ["shamela"], force=True)["ok"])
        self.assertFalse(sources.ensure_agent("pi", ["shamela"])["ok"])
        sources.RUN = lambda *a: (_ for _ in ()).throw(OSError("مفقود"))
        self.assertIn("مفقود", sources.ensure_agent("codex", ["shamela"], force=True)["note"])

    def test_agent_cache_and_force(self):
        calls = []
        sources.RUN = lambda argv, *args: (calls.append(argv) or 0, "zajel_shamela zajel_aljam3", "")
        self.assertTrue(sources.ensure_agent("codex", ["shamela"])["ok"])
        self.assertTrue(sources.ensure_agent("codex", ["shamela"])["ok"])
        self.assertEqual(len(calls), 1)
        self.assertTrue(sources.ensure_agent("codex", ["shamela", "aljam3:1"])["ok"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(set(json.loads((Path(self.tmp.name) / "sources_agents.json").read_text())["codex"]), {"zajel_shamela", "zajel_aljam3"})
        self.assertTrue(sources.ensure_agent("codex", ["shamela"], force=True)["ok"])
        self.assertEqual(len(calls), 3)

    def test_ensure_agent_reports_added(self):
        calls = []
        sources.RUN = lambda argv, *a: (calls.append(argv) or 0, "zajel_shamela", "")
        res = sources.ensure_agent("codex", ["shamela", "aljam3:1"])
        self.assertEqual(res["added"], ["zajel_aljam3"])               # الشاملة موجودة قبلًا، والجامع أُضيف الآن
        self.assertEqual(sources.ensure_agent("codex", ["shamela", "aljam3:1"])["added"], [])      # من الذاكرة
        self.assertEqual(sources.ensure_agent("pi", ["shamela"])["added"], [])
        self.assertEqual(sources.ensure_agent("claude", [])["added"], [])
        sources.RUN = lambda *a: (1, "", "تعذر")
        res = sources.ensure_agent("agy", ["shamela"])
        self.assertFalse(res["ok"])
        self.assertEqual(res["added"], [])

    def test_selection_sanitizes_file(self):
        path = Path(self.tmp.name) / "sources.json"
        path.write_text(json.dumps({"libraries": "bad", "notebooks": [{"id": "x", "title": 3, "on": "yes"}, {"id": 7}], "nb_mode": []}))
        self.assertEqual(sources.get_selection(), {"libraries": [], "notebooks": [{"id": "x", "title": "", "on": False}], "nb_mode": "answer"})
        path.write_text('{}')
        self.assertEqual(sources.get_selection(), {"libraries": [], "notebooks": [], "nb_mode": "answer"})

    def test_data_fallback(self):
        with patch.object(sources, "DATA", None), patch.dict(sys.modules, {"terminal": types.SimpleNamespace(DATA=Path(self.tmp.name))}):
            sources.set_selection({"libraries": ["shamela"]})
            self.assertEqual(sources.get_selection()["libraries"], ["shamela"])
        with patch.object(sources, "DATA", None), patch.dict(sys.modules, {"terminal": None}):
            self.assertEqual(sources._data(), Path.home())

    def test_run_path(self):
        with patch.dict(os.environ, {"PATH": "/original"}), patch.object(sources.subprocess, "run") as run:
            sources._run(["test"], 1)
            path = run.call_args.kwargs["env"]["PATH"].split(os.pathsep)
            self.assertEqual(path, [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".opencode/bin"), "/original"])

    def test_source_note(self):
        self.assertEqual(sources.source_note([]), "")
        self.assertIn("اقرأ أولًا ملف الأدلة: /tmp/e", sources.source_note([], "/tmp/e"))
        for library in sources.LIBRARIES:
            note = sources.source_note([library["id"]])
            self.assertIn(library["name"], note)
            self.assertIn("حرفيًا", note)
            if library["id"].startswith("aljam3:"):
                self.assertIn(library["id"][-1], note)
        self.assertIn("3، 2، 1", sources.source_note(["aljam3:3", "aljam3:2", "aljam3:1"]))

    def test_ask_notebook(self):
        calls = []
        def run(argv, timeout, inp=None):
            calls.append((argv, timeout))
            return 0, json.dumps({"answer": "جواب", "references": [{"citation_number": 1, "cited_text": "نص"}]}), ""
        sources.RUN = run
        self.assertEqual(sources.ask_notebook("id", "سؤال"), {"ok": True, "answer": "جواب", "refs": [{"n": 1, "text": "نص"}], "note": ""})
        self.assertEqual(calls[0], (["notebooklm", "ask", "-n", "id", "--json", "سؤال"], 150))
        sources.RUN = lambda *a: (_ for _ in ()).throw(subprocess.TimeoutExpired("notebooklm", 150))
        self.assertIn("مهلة", sources.ask_notebook("id", "سؤال")["note"])
        sources.RUN = lambda *a: (0, "{", "")
        self.assertFalse(sources.ask_notebook("id", "سؤال")["ok"])
        sources.RUN = lambda *a: (1, "", "فشل")
        self.assertIn("فشل", sources.ask_notebook("id", "سؤال")["note"])

    def test_ask_notebook_drops_empty_passages_and_adds_source_titles(self):
        ask = {"answer": "جواب", "references": [
            {"citation_number": 1, "cited_text": None, "source_id": "s1"},
            {"citation_number": 2, "cited_text": "  ", "source_id": "s1"},
            {"citation_number": 3, "cited_text": "نص حرفي", "source_id": "s2"}]}
        lst = {"sources": [{"id": "s1", "title": "كتاب أ.pdf"}, {"id": "s2", "title": "كتاب ب.pdf"}]}
        calls = []
        def run(argv, timeout, inp=None):
            calls.append(argv)
            return 0, json.dumps(lst if argv[1] == "source" else ask), ""
        sources.RUN = run
        res = sources.ask_notebook("nb", "سؤال")
        self.assertEqual(res["refs"], [{"n": 3, "text": "نص حرفي", "source": "كتاب ب.pdf"}])
        self.assertEqual(res["sources"], ["كتاب أ.pdf", "كتاب ب.pdf"])
        self.assertEqual(calls[1], ["notebooklm", "source", "list", "-n", "nb", "--json"])
        self.assertTrue(all("--new" not in c for c in calls))
        # فشل قائمة المصادر يسقط بصمت: يبقى الجواب
        sources.RUN = lambda argv, *a: (1, "", "x") if argv[1] == "source" else (0, json.dumps(ask), "")
        res = sources.ask_notebook("nb", "سؤال")
        self.assertTrue(res["ok"])
        self.assertEqual(res["refs"], [{"n": 3, "text": "نص حرفي"}])
        self.assertNotIn("sources", res)
        # كل المقاطع فارغة: لا refs
        only_empty = {"answer": "ج", "references": [{"citation_number": 1, "cited_text": None, "source_id": "s1"}]}
        sources.RUN = lambda argv, *a: (0, json.dumps(lst if argv[1] == "source" else only_empty), "")
        res = sources.ask_notebook("nb", "سؤال")
        self.assertEqual((res["refs"], res["sources"]), ([], ["كتاب أ.pdf"]))

    def test_evidence_without_passages(self):
        path = Path(self.tmp.name) / "e2" / "evidence.md"
        sources.write_evidence(path, [{"title": "دفتر", "answer": "جواب", "refs": [{"n": 1, "text": ""}, {"n": 2, "text": None}], "sources": ["كتاب أ.pdf"]}])
        text = path.read_text(encoding="utf-8")
        self.assertIn("لم يُرجع الدفتر مقاطع حرفية", text)
        self.assertNotIn("[1]", text)
        self.assertIn("المصادر التي استند إليها الدفتر: كتاب أ.pdf", text)

    def test_verify_calls_are_serialized_and_429_retried(self):
        active, peak, attempts = [0], [0], []
        def fake(quote):
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            time.sleep(0.02)
            active[0] -= 1
            attempts.append(quote)
            if quote == "ثقيل" and attempts.count("ثقيل") < 2:
                raise ValueError("خطأ من الخادم: خطأ HTTP 429 من الشاملة")
            return {"structuredContent": {"status": "verbatim", "locations": []}}
        with patch.object(sources, "_mcp_verify", side_effect=fake), patch.object(sources, "RETRY_WAIT", 0):
            results = []
            ths = [threading.Thread(target=lambda q=q: results.append(sources.shamela_verify(q))) for q in ("أ", "ب", "ج", "ثقيل")]
            [t.start() for t in ths]
            [t.join() for t in ths]
        self.assertEqual(peak[0], 1)                                     # لا نداءان معًا
        self.assertTrue(all(r and r["found"] for r in results))          # 429 أُعيدت المحاولة فنجح
        self.assertEqual(attempts.count("ثقيل"), 2)
        with patch.object(sources, "_mcp_verify", side_effect=ValueError("خطأ من الخادم: 429")), patch.object(sources, "RETRY_WAIT", 0):
            self.assertIsNone(sources.shamela_verify("نص"))              # بعد ثلاث محاولات: تعذّر لا استثناء

    def test_verify_ratio_uses_best_location(self):
        data = {"status": "partial", "locations": [{"book_name": "أ", "printed_page": "1", "field": "body", "match": "partial", "matched_words": 6, "quote_words": 15},
                                                    {"book_name": "ب", "printed_page": "2", "field": "body", "match": "partial", "matched_words": 9, "quote_words": 14}]}
        with patch.object(sources, "_mcp_verify", return_value={"structuredContent": data}):
            res = sources.shamela_verify("نص")
        self.assertEqual(res["where"], "ب، 2")
        self.assertAlmostEqual(res["ratio"], 9 / 14)
        data["locations"][0].update(match="verbatim", matched_words=14, quote_words=14)
        data["status"] = "verbatim"
        with patch.object(sources, "_mcp_verify", return_value={"structuredContent": data}):
            self.assertEqual(sources.shamela_verify("نص")["ratio"], 1.0)

    def test_evidence(self):
        path = Path(self.tmp.name) / "round" / "evidence.md"
        self.assertEqual(sources.write_evidence(path, [{"title": "دفتر", "answer": "جواب", "refs": [{"n": 2, "text": "نص حرفي"}]}]), str(path))
        text = path.read_text(encoding="utf-8")
        for piece in ("ملف الأدلة", "دفتر", "جواب", "[2] نص حرفي"):
            self.assertIn(piece, text)

    def test_verify_results(self):
        data = {"status": "differs", "locations": [{"book_name": "آخر", "printed_page": "1/ 2", "field": "body", "match": "partial"}, {"book_name": "كتاب", "printed_page": "5/ 159", "field": "footnote", "match": "verbatim", "source_url": "https://shamela.ws/book/119492/1434"}]}
        with patch.object(sources, "_mcp_verify", return_value={"structuredContent": data}):
            self.assertEqual(sources.shamela_verify("نص"), {"found": True, "where": "كتاب، 5/ 159", "in_footnote": True, "url": "https://shamela.ws/book/119492/1434", "match": "differs", "ratio": None})
        with patch.object(sources, "_mcp_verify", return_value={"content": [{"type": "text", "text": '{"status":"not_found"}'}]}):
            self.assertEqual(sources.shamela_verify("نص"), {"found": False, "where": "", "in_footnote": False, "url": "", "match": "not_found", "ratio": None})
        with patch.object(sources, "_mcp_verify", side_effect=OSError()):
            self.assertIsNone(sources.shamela_verify("نص"))

    def test_mcp_protocol_fake_server(self):
        messages = []
        pending = queue.Queue()
        class Output:
            def __iter__(self):
                return self
            def __next__(self):
                item = pending.get(timeout=2)
                if item is None:
                    raise StopIteration
                return item
            def close(self):
                pass
        class Input:
            def write(self, line):
                msg = json.loads(line)
                messages.append(msg)
                method = msg["method"]
                if method == "notifications/initialized":
                    return
                results = {"initialize": {}, "tools/list": {"tools": [{"name": "shamela_verify_quote", "inputSchema": {"properties": {"quote": {}}}}]}, "tools/call": {"structuredContent": {"status": "verbatim", "locations": [{"book_name": "كتاب", "author_name": "مؤلف", "printed_page": "5/ 159", "auto_numbered": False, "field": "body", "match": "verbatim", "source_url": "https://shamela.ws/book/119492/1434"}]}}}
                pending.put(json.dumps({"id": msg["id"], "result": results[method]}) + "\n")
            def flush(self):
                pass
            def close(self):
                pass
        class Process:
            stdin = Input()
            stdout = Output()
            def kill(self):
                pending.put(None)
            def wait(self):
                pass
        with patch.object(sources.subprocess, "Popen", return_value=Process()) as popen:
            self.assertEqual(sources.shamela_verify("نص"), {"found": True, "where": "كتاب، 5/ 159", "in_footnote": False, "url": "https://shamela.ws/book/119492/1434", "match": "verbatim", "ratio": None})
            self.assertEqual(popen.call_args.kwargs["env"]["PATH"], sources._env()["PATH"])
        self.assertEqual([x["method"] for x in messages], ["initialize", "notifications/initialized", "tools/list", "tools/call"])
        self.assertEqual(messages[-1]["params"]["arguments"], {"quote": "نص"})


if __name__ == "__main__":
    unittest.main()
