import json
import shlex
import unittest
from types import SimpleNamespace

import adbclean
import cleaner


class FakeM:
    PROTECTED_PATHS = set()

    def __init__(self):
        self.calls = []

    def shell(self, command, serial, timeout):
        self.calls.append((command, serial, timeout))
        out = ""
        if "df -k /data" in command:
            out = "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/data 1000000 850000 150000 85% /data\n"
        elif "getprop ro.product.model" in command:
            out = "Galaxy Test\n"
        elif "dumpsys diskstats" in command:
            # الصيغة الحقيقية كما يخرجها Galaxy S24 Ultra
            out = 'Photos Size: 8282116096\nVideos Size: 20730728448\nAudio Size: 6407413760\nSystem Size: 36712517632\nOther Size: 26015698944\n'
            out += 'Package Names: ["com.whatsapp","com.sec.android.easyMover"]\n'
            out += 'App Sizes: [100,200]\nApp Data Sizes: [300,2147483648]\nCache Sizes: [40,50]\n'
        elif "du -sk" in command:
            if "/com.whatsapp/" in command:
                out = "12\t/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Video\n"
            elif "/com.whatsapp.w4b/" in command:
                out = "4\t/sdcard/Android/media/com.whatsapp.w4b/WhatsApp/Media/WhatsApp Images\n"
            elif "/sdcard/log/" in command:
                out = "8\t/sdcard/log/main\n"
        elif "find /sdcard/Download/ -maxdepth 2" in command:
            out = "100|/sdcard/Download/report.pdf\n100|/sdcard/Download/report (1).pdf\n100|/sdcard/Download/report (2).pdf\n100|/sdcard/Download/different.pdf\n"
        elif command.startswith("sha256sum "):
            paths = shlex.split(command[len("sha256sum "):].split(" 2>/dev/null")[0])
            for path in paths:
                digest = "a" * 64 if path.endswith("report.pdf") or path.endswith("report (1).pdf") else "b" * 64
                out += f"{digest}  {path}\n"
        elif command.startswith("stat -c"):
            out = "100|/sdcard/Download/report.pdf\n"
        return SimpleNamespace(stdout=out, stderr="", returncode=0)


def new_job():
    return cleaner.new_job("caches", "/sdcard")


class AdbCleanTest(unittest.TestCase):
    def setUp(self):
        self.m = FakeM()
        adbclean.init(self.m, cleaner)

    def test_diskstats_parallel_arrays_totals_and_storage_card(self):
        health = adbclean._phone_health("serial")
        self.assertEqual(health["facts"], {"total": 1024000000, "used": 870400000, "free": 153600000, "model": "Galaxy Test"})
        self.assertEqual([a["pkg"] for a in health["apps"]], ["com.sec.android.easyMover", "com.whatsapp"])
        self.assertIn("الصور: 8.3 غيغابايت", health["cards"][1]["details"])
        self.assertEqual(health["cards"][0]["status"], "warn")
        self.assertIn("Smart Switch", health["apps"][0]["note"])

    def test_whatsapp_media_is_informational_and_not_allowed(self):
        job = new_job()
        result = adbclean.caches(job, "serial")
        category = next(c for c in result["categories"] if c["id"] == "whatsapp-media")
        self.assertEqual(len(category["items"]), 2)
        self.assertFalse(category["selectable"])
        self.assertEqual(category["action"]["kind"], "howto")
        self.assertTrue(all(i["path"] not in job["allowed"] for i in category["items"]))

    def test_download_copies_require_size_and_sha256_equality(self):
        job = new_job()
        result = adbclean.caches(job, "serial")
        category = next(c for c in result["categories"] if c["id"] == "download-copies")
        self.assertEqual([i["path"] for i in category["items"]], ["/sdcard/Download/report (1).pdf"])
        self.assertEqual(category["items"][0]["note"], "نسخة مطابقة لـ report.pdf")

    def test_allowed_set_total_and_permanent_rules(self):
        job = new_job()
        result = adbclean.caches(job, "serial")
        by_id = {c["id"]: c for c in result["categories"]}
        logs = by_id["device-logs"]["items"][0]["path"]
        copy = by_id["download-copies"]["items"][0]["path"]
        media = by_id["whatsapp-media"]["items"][0]["path"]
        self.assertIn(logs, job["allowed"])
        self.assertIn(logs, job["perm_ok"])
        self.assertIn(copy, job["allowed"])
        self.assertIn(copy, job["perm_ok"])
        self.assertNotIn(media, job["allowed"])
        self.assertEqual(result["total"], sum(c["size"] for c in result["categories"] if c["selectable"]))


if __name__ == "__main__":
    unittest.main()
