"""اختبارات ربط حساب المستخدم في تيليجرام (٢.١٦) بلا شبكة: عميل وهمي مكان telethon."""
import asyncio
import json
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import telegram_account as A
import telegram_account_bot as AB


def msg(i, text="", name=None, ext="", mime="", size=0, voice=False, video=False, photo=False, preview=False, dur=None):
    f = types.SimpleNamespace(name=name, ext=ext, mime_type=mime, size=size, duration=dur) if (name or ext or mime) else None
    return types.SimpleNamespace(id=i, message=text, file=f, voice=voice or None, audio=None, video=video or None, photo=photo or None, web_preview=preview or None,
                                 date="2026-11-01 10:00:00", sender=types.SimpleNamespace(first_name="س"), sender_id=1)


class FakeClient:
    def __init__(self, store):
        self.store = store            # username/id ← قائمة رسائل
        self.downloads = []

    def is_connected(self):
        return True

    async def is_user_authorized(self):
        return True

    async def get_entity(self, ref):
        return types.SimpleNamespace(id=ref if isinstance(ref, int) else abs(hash(ref)) % 10 ** 6, title=str(ref), username=ref if isinstance(ref, str) else None)

    async def iter_messages(self, ent, search=None, limit=None, filter=None, min_id=0, reverse=False):
        rows = self.store.get("me" if ent == "me" else ent.username or ent.id, [])
        rows = [m for m in rows if m.id > min_id and (not search or search in (m.message or "") or search in ((m.file.name or "") if m.file else ""))]
        rows = sorted(rows, key=lambda m: m.id, reverse=not reverse)
        for m in rows[:limit]:
            yield m

    async def get_messages(self, ent, ids=None):
        rows = self.store.get("me" if ent == "me" else ent.username or ent.id, [])
        return next((m for m in rows if m.id == ids), None)

    async def download_media(self, m, file=None, progress_callback=None):
        if progress_callback:
            progress_callback(50, 100)
            progress_callback(100, 100)
        Path(file).write_bytes(b"x")
        self.downloads.append(file)
        return file


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.fake = FakeClient({})
        home = self.tmp / "home"
        home.mkdir()

        async def fake_client():
            return self.fake
        for x in (mock.patch.object(A, "DATA", self.tmp), mock.patch.object(A, "client", fake_client), mock.patch.object(A, "PACER", A.Pacer(0, 0)),
                  mock.patch.object(Path, "home", staticmethod(lambda: home)), mock.patch.object(A, "linked", lambda: True)):
            x.start()
            self.addCleanup(x.stop)
        A.DLS.clear()
        A.STATE.update(flood_until=0.0)


class Pure(unittest.TestCase):
    def test_norm_arabic(self):
        self.assertEqual(A.norm("الإِمَامُ أحمد"), A.norm("الامام احمد"))
        self.assertEqual(A.norm("مكتبة"), A.norm("مكتبه"))

    def test_classify(self):
        self.assertEqual(A.classify(msg(1, name="x.pdf", ext=".pdf", mime="application/pdf")), "book")
        self.assertEqual(A.classify(msg(1, name="d.mp3", ext=".mp3", mime="audio/mpeg")), "audio")
        self.assertEqual(A.classify(msg(1, voice=True, ext=".ogg", mime="audio/ogg")), "audio")
        self.assertEqual(A.classify(msg(1, name="v.mp4", ext=".mp4", mime="video/mp4", video=True)), "video")
        self.assertEqual(A.classify(msg(1, text="شاهد https://x.com/a")), "link")
        self.assertEqual(A.classify(msg(1, text="كلام")), "text")
        self.assertEqual(A.classify(msg(1, name="a.bin", ext=".bin", mime="application/x-bin")), "file")

    def test_match_watch(self):
        ws = [{"word": "طبعة جديدة", "on": True}, {"word": "ابن قدامة", "on": False}, {"word": "الإمام", "on": True}]
        self.assertEqual([w["word"] for w in A.match_watch("صدرت طبعه جديده من الكتاب", ws)], ["طبعة جديدة"])
        self.assertEqual(A.match_watch("ابن قدامة", ws), [])             # مطفأة
        self.assertEqual([w["word"] for w in A.match_watch("قال الامام", ws)], ["الإمام"])
        self.assertEqual(A.match_watch("طبعة فقط", ws), [])              # كل كلمات العبارة مطلوبة

    def test_suggest_place(self):
        self.assertEqual(A.suggest_place("audio", True), "تفريغ")
        self.assertEqual(A.suggest_place("audio"), "صوت")
        self.assertEqual(A.suggest_place("book"), "كتب")
        self.assertEqual(A.suggest_place("link"), "روابط")
        self.assertEqual(A.suggest_place("zzz"), "ملفات")

    def test_channel_ref(self):
        self.assertEqual(A.parse_channel_ref("https://t.me/fiqh_books"), "fiqh_books")
        self.assertEqual(A.parse_channel_ref("@fiqh_books"), "fiqh_books")
        self.assertEqual(A.parse_channel_ref("t.me/fiqh_books/12"), "fiqh_books")
        with self.assertRaises(ValueError):
            A.parse_channel_ref("ليس رابطا")

    def test_safe_name_and_unique(self):
        self.assertNotIn("/", A.safe_name("a/b:c"))
        d = Path(tempfile.mkdtemp())
        (d / "كتاب.pdf").write_bytes(b"1")
        self.assertEqual(A.unique_path(d, "كتاب.pdf").name, "كتاب (1).pdf")

    def test_human_size(self):
        self.assertEqual(A.human_size(0), "—")
        self.assertIn("م.ب", A.human_size(5 * 1024 ** 2))


class Fuzzy(unittest.TestCase):
    def test_terms_drop_stopwords_and_accents(self):
        self.assertEqual(A.fuzzy_terms("El secreto de sus ojos"), ["secreto", "ojos", "sus"])
        self.assertIn("peliculas", A.fuzzy_terms("Películas"))
        self.assertEqual(A.fuzzy_terms("pdf"), [])

    def test_misspelling_still_matches(self):
        it = {"title": "El secreto de sus ojos (2009)", "meta": ""}
        self.assertGreaterEqual(A.fuzzy_score(it, "secreto de los hojos"), 0.5)
        far = {"title": "كتاب المغني لابن قدامة", "meta": ""}
        self.assertEqual(A.fuzzy_score(far, "secreto de los hojos"), 0.0)

    def test_arabic_variants(self):
        it = {"title": "الأَشباه والنظائر", "meta": ""}
        self.assertGreaterEqual(A.fuzzy_score(it, "الاشباه والنظائر"), 0.99)
        it2 = {"title": "مدرسة الفقه", "meta": ""}
        self.assertGreaterEqual(A.fuzzy_score(it2, "مدرسه الفقه"), 0.99)

    def test_rank_orders_and_filters(self):
        items = [{"title": "كتاب آخر", "date": "2020"}, {"title": "El secreto de sus ojos", "date": "2021"}, {"title": "secreto", "date": "2022"}]
        r = A.fuzzy_rank(items, "secreto de sus hojos")
        self.assertEqual(r[0]["title"], "El secreto de sus ojos")
        self.assertNotIn("كتاب آخر", [i["title"] for i in r])
        self.assertEqual(A.fuzzy_rank(items, "pdf"), items)       # بلا كلمات مهمة: لا تصفية


class Pacing(unittest.TestCase):
    def test_pacer_spaces_requests_and_obeys_flood(self):
        t = [100.0]
        slept = []

        def sleep(s):
            slept.append(s)
            t[0] += s
        p = A.Pacer(base=2, jitter=0, sleep=sleep, clock=lambda: t[0])
        p.wait()
        t[0] += 0.5
        p.wait()
        self.assertAlmostEqual(slept[-1], 1.5)         # يكمل الفاصل ٢ ثانية
        p.flood(30)
        p.wait()
        self.assertGreaterEqual(slept[-1], 30)         # لا طلب قبل انقضاء أمر الانتظار

    def test_jitter_is_variable(self):
        seen = set()
        for _ in range(20):
            p = A.Pacer(base=0, jitter=1, sleep=lambda s: seen.add(round(s, 3)), clock=lambda: 0.0)
            p.last = 0.0
            p.wait()
        self.assertGreater(len(seen), 5)

    def test_floodwait_short_is_retried_once_long_is_raised(self):
        class FloodWaitError(Exception):
            def __init__(self, s):
                self.seconds = s
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) == 1:
                raise FloodWaitError(1)
            return "ok"
        with mock.patch.object(A, "PACER", A.Pacer(0, 0, sleep=lambda s: None)):
            self.assertEqual(A.run(A.call(flaky)), "ok")
        self.assertEqual(len(calls), 2)

        async def long():
            raise FloodWaitError(5000)
        with self.assertRaises(ValueError) as cm:
            A.run(A.call(long))
        self.assertIn("5000", str(cm.exception))
        self.assertGreater(A.STATE["flood_until"], time.time() + 4000)


class Login(unittest.TestCase):
    def test_invalid_inputs_store_nothing(self):
        with mock.patch.object(A, "_secret_set") as ss:
            for args in (("abc", "0" * 32, "+966500000000"), ("123", "short", "+966500000000"), ("123", "a" * 32, "0500000000")):
                with self.assertRaises(ValueError):
                    A.login_start(*args)
            ss.assert_not_called()

    def test_secrets_never_in_config_file(self):
        tmp = Path(tempfile.mkdtemp())
        with mock.patch.object(A, "DATA", tmp):
            A._save({"libs": [{"id": 1, "name": "x"}]})
            txt = (tmp / "telegram_account.json").read_text(encoding="utf-8")
        for bad in ("api_hash", "session", "password"):
            self.assertNotIn(bad, txt)


class Search(Base):
    def test_search_across_libs_with_counts_and_type_filter(self):
        self.fake.store = {"lib_a": [msg(1, name="الروض المربع.pdf", ext=".pdf", mime="application/pdf", size=5 * 1024 ** 2), msg(2, name="الروض شرح.mp3", ext=".mp3", mime="audio/mpeg", size=1024 ** 2, dur=3000)],
                           "lib_b": [msg(7, text="الروض رابط https://x.com/r")]}
        A._save({"libs": [{"id": 1, "name": "أ", "username": "lib_a", "list": "fiqh", "on": True}, {"id": 2, "name": "ب", "username": "lib_b", "list": "docs", "on": True},
                          {"id": 3, "name": "ج", "username": "lib_c", "list": "fiqh", "on": False}]})
        r = A.search("الروض")
        self.assertEqual(r["counts"]["all"], 3)
        self.assertEqual({i["t"] for i in r["items"]}, {"book", "audio", "link"})
        self.assertEqual(A.search("الروض", scope="docs")["counts"]["all"], 1)
        self.assertEqual([i["t"] for i in A.search("الروض", type_="book")["items"]], ["book"])
        with self.assertRaises(ValueError):
            A.search("   ")

    def test_search_without_enabled_lists(self):
        A._save({"libs": [{"id": 1, "name": "أ", "username": "a", "list": "fiqh", "on": False}]})
        with self.assertRaises(ValueError):
            A.search("x")


class Downloads(Base):
    def _wait(self, did, state="done"):
        for _ in range(100):
            if A.DLS[did]["state"] in (state, "error"):
                break
            time.sleep(0.05)
        return A.DLS[did]

    def test_download_into_type_folder(self):
        self.fake.store = {"lib_a": [msg(5, name="كتاب.pdf", ext=".pdf", mime="application/pdf", size=1000)]}
        A._save({"libs": [{"id": 1, "name": "أ", "username": "lib_a", "list": "fiqh", "on": True}]})
        notes = []
        did = A.download("1:5", notify=lambda t, d: notes.append(t))
        d = self._wait(did)
        self.assertEqual(d["state"], "done")
        self.assertTrue(d["path"].endswith("زاجل/تيليجرام/كتب/كتاب.pdf"), d["path"])
        self.assertEqual(d["p"], 100.0)
        self.assertIn("اكتمل", notes[0])

    def test_over_two_gb_refused(self):
        self.fake.store = {"lib_a": [msg(5, name="ضخم.mkv", ext=".mkv", mime="video/x-matroska", size=3 * 1024 ** 3, video=True)]}
        A._save({"libs": [{"id": 1, "name": "أ", "username": "lib_a", "list": "fiqh", "on": True}]})
        d = self._wait(A.download("1:5"))
        self.assertEqual(d["state"], "error")
        self.assertIn("٢ غيغابايت", d["error"])
        self.assertEqual(self.fake.downloads, [])

    def test_unknown_ref(self):
        with self.assertRaises(ValueError):
            A.download("99:1")

    def test_after_download_transcribe(self):
        calls = []
        fake_media = types.SimpleNamespace(transcribe=lambda p, **k: calls.append(p) or {"id": "j1"})
        with mock.patch.dict("sys.modules", {"media": fake_media}):
            d = {"then": "transcribe"}
            A._after_download(d, "/x/a.mp3")
        self.assertEqual(calls, ["/x/a.mp3"])
        self.assertEqual(d["job"], "j1")


class Inbox(Base):
    def test_poll_suggest_and_only_new(self):
        self.fake.store = {"me": [msg(1, name="كتاب.pdf", ext=".pdf", mime="application/pdf", size=10), msg(2, voice=True, ext=".ogg", mime="audio/ogg"), msg(3, text="كلام فقط"), msg(4, text="https://a.com/x")]}
        items = A.inbox_poll()
        self.assertEqual({i["id"]: i["to"] for i in items}, {1: "كتب", 2: "تفريغ", 4: "روابط"})
        self.assertEqual(A.new_inbox(), 3)
        self.assertEqual(len(A.inbox_poll()), 3)               # بلا تكرار
        self.fake.store["me"].append(msg(9, name="ص.jpg", ext=".jpg", mime="image/jpeg", photo=True))
        self.assertEqual(len(A.inbox_poll()), 4)

    def test_nothing_moves_before_approval_then_apply(self):
        self.fake.store = {"me": [msg(1, name="كتاب.pdf", ext=".pdf", mime="application/pdf", size=10), msg(4, text="https://a.com/x")]}
        A.inbox_poll()
        self.assertEqual(self.fake.downloads, [])
        self.assertEqual(A.dl_list(), [])
        n = A.inbox_apply()
        self.assertEqual(n, 2)
        for _ in range(60):
            if self.fake.downloads:
                break
            time.sleep(0.05)
        self.assertEqual(len(self.fake.downloads), 1)
        self.assertEqual(A.new_inbox(), 0)
        self.assertTrue((A.root_dir() / "روابط" / "روابط.md").exists())


class Watch(Base):
    def test_hit_recorded_once_and_notified(self):
        A.watch_add("طبعة جديدة")
        got = []
        lib = {"id": 1, "name": "مكتبة", "username": "m", "list": "fiqh", "on": True}
        m = msg(10, text="صدرت طبعة جديدة من الكتاب")
        with mock.patch.object(A, "HIT_NOTIFY", lambda h: got.append(h)):
            self.assertEqual(len(A.on_new_message(lib, m)), 1)
            self.assertEqual(A.on_new_message(lib, m), [])          # لا تكرار لنفس الرسالة
            self.assertEqual(A.on_new_message(lib, msg(11, text="لا شيء")), [])
        self.assertEqual(len(got), 1)
        self.assertEqual(A.hits()[0]["link"], "https://t.me/m/10")
        self.assertEqual(A.watch_words()[0]["hits"], 1)

    def test_add_toggle_remove_and_validation(self):
        with self.assertRaises(ValueError):
            A.watch_add("ا")
        A.watch_add("كشاف")
        A.watch_add("كشّاف")                                        # نفس الكلمة بعد التطبيع
        self.assertEqual(len(A.watch_words()), 1)
        wid = A.watch_words()[0]["id"]
        A.watch_toggle(wid)
        self.assertFalse(A.watch_words()[0]["on"])
        A.watch_remove(wid)
        self.assertEqual(A.watch_words(), [])

    def test_bot_notifier_respects_quiet_hours(self):
        sent = []
        cfg = {"chat_id": 7, "quiet_on": True, "quiet_from": 0, "quiet_to": 24}
        with mock.patch.object(AB.TL, "_cfg", lambda: cfg), mock.patch.object(AB.TL, "send", lambda *a, **k: sent.append(a)), mock.patch.object(AB.TL, "_quiet_now", lambda c: True):
            AB.hit_notifier({"w": "x", "ch": "c", "text": "t", "link": ""})
        self.assertEqual(sent, [])


class Backup(Base):
    def test_incremental_backup_and_html(self):
        self.fake.store = {123: [msg(1, text="أولى <b>"), msg(2, text="ثانية", name="ملف.pdf", ext=".pdf", mime="application/pdf", size=10)]}
        A.backup_set(123, "مجموعة الطلاب", True)
        self.assertEqual(A.backup_run(), 2)
        folder = A.backup_dir() / "مجموعة الطلاب"
        page = (folder / "index.html").read_text(encoding="utf-8")
        self.assertIn('dir="rtl"', page)
        self.assertIn("&lt;b&gt;", page)                              # لا حقن HTML
        self.assertTrue(list((folder / "media").glob("2-*")))
        self.fake.store[123].append(msg(3, text="ثالثة"))
        self.assertEqual(A.backup_run(), 1)                           # الجديد فقط
        self.assertEqual(len((folder / "messages.jsonl").read_text(encoding="utf-8").splitlines()), 3)
        self.assertEqual(A.backups()[0]["last_id"], 3)

    def test_disabled_chat_skipped_and_big_media_skipped(self):
        self.fake.store = {5: [msg(1, text="x", name="ضخم.mp4", ext=".mp4", mime="video/mp4", size=A.MAX_BACKUP_MEDIA + 1, video=True)]}
        A.backup_set(5, "قناة", False)
        self.assertEqual(A.backup_run(), 0)
        A.backup_set(5, "قناة", True)
        self.assertEqual(A.backup_run(), 1)
        self.assertEqual(self.fake.downloads, [])


class BotScreens(Base):
    def test_search_results_screen_and_await(self):
        AB.RES[7] = {"q": "الروض", "counts": {"book": 1, "audio": 1, "video": 0, "all": 2},
                     "items": [{"ref": "1:5", "t": "book", "title": "الروض", "size_h": "5 م.ب"}, {"ref": "1:6", "t": "audio", "title": "شرح", "size_h": "1 م.ب"}]}
        text, kb = AB.screen_results(7)
        self.assertIn("2 نتيجة", text)
        datas = [b["callback_data"] for r in kb for b in r]
        self.assertIn("ta:g:1:5", datas)
        text2, _ = AB.screen_results(7, "audio")
        self.assertIn("1 نتيجة", text2)
        self.assertTrue(all(len(d.encode()) <= 64 for d in datas))
        AB.AWAIT[7] = "search"
        with mock.patch.object(AB, "do_search") as ds:
            self.assertTrue(AB.pending_text(7, "المغني"))
            ds.assert_called_with(7, "المغني")
            self.assertFalse(AB.pending_text(7, "غير منتظر"))

    def test_add_library_from_bot(self):
        sent = []
        with mock.patch.object(AB.TL, "send", lambda t, c, **k: sent.append(t)), mock.patch.object(AB.A, "lib_add") as la:
            AB.on_callback(9, 1, "la")
            self.assertEqual(AB.AWAIT[9], "addlib")
            self.assertTrue(AB.pending_text(9, "@kitab"))
            la.assert_called_with("@kitab")
            self.assertNotIn(9, AB.AWAIT)
            la.side_effect = ValueError("اكتب رابط القناة")
            AB.AWAIT[9] = "addlib"
            self.assertTrue(AB.pending_text(9, "xx"))
            self.assertEqual(AB.AWAIT[9], "addlib")
        datas = [b["callback_data"] for r in AB.screen_libs()[1] for b in r]
        self.assertIn("ta:la", datas)
        self.assertIn("ta:ls", datas)

    def test_pick_channels_from_search(self):
        sent = []
        items = [{"id": 1, "name": "قناة أ", "username": "a_chan", "who": "10 مشترك"}, {"id": 2, "name": "قناة ب", "username": "b_chan", "who": "5 مشترك"}]
        edits = []
        with mock.patch.object(AB.TL, "send", lambda t, c, **k: sent.append((t, k))), mock.patch.object(AB.TL, "edit", lambda c, m, t, kb=None: edits.append(t)), \
                mock.patch.object(AB.A, "suggestions", return_value=items), mock.patch.object(AB.A, "lib_add") as la:
            AB.AWAIT[5] = "addlib"
            self.assertTrue(AB.pending_text(5, "فقه"))
            self.assertEqual(len(AB.SUGG[5]["items"]), 2)
            AB.on_callback(5, 1, "ps:0")
            AB.on_callback(5, 1, "ps:1")
            AB.on_callback(5, 1, "ps:1")        # إلغاء التحديد
            AB.on_callback(5, 1, "pa")
            la.assert_called_once_with("a_chan")
            self.assertIn("قناة أ", edits[-1])
            self.assertNotIn(5, AB.SUGG)
            AB.AWAIT[5] = "addlib"
            self.assertTrue(AB.pending_text(5, "@zzz_chan"))
            la.assert_called_with("@zzz_chan")

    def test_commands(self):
        with mock.patch.object(AB, "do_search") as ds:
            self.assertTrue(AB.on_command(7, "search", "المغني"))
            ds.assert_called_with(7, "المغني")
        with mock.patch.object(AB.TL, "send", lambda *a, **k: 1):
            self.assertTrue(AB.on_command(7, "watchwords", "تحقيق جديد"))
        self.assertEqual(A.watch_words()[0]["word"], "تحقيق جديد")

    def test_every_screen_renders(self):
        for n in ("search", "inbox", "watchwords", "dls", "backup"):
            text, kb = AB.screen(n)
            self.assertTrue(text and kb is not None, n)


if __name__ == "__main__":
    unittest.main()
