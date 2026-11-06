import unittest
from unittest.mock import patch

import cleaner as C
import fullclean


class FullCleanTests(unittest.TestCase):
    def setUp(self):
        C.JOBS.clear()

    def tearDown(self):
        C.JOBS.clear()

    def _job(self, serial=None):
        job = C.new_job("caches", "target")
        job["keep"] = True
        if serial:
            job["serial"] = serial
        return job

    def test_advice_split_and_archive_metadata(self):
        job = self._job()
        result = {"categories": [
            {"id": "icloud-archives", "title": "أرشيف", "desc": "أرشيف", "risk": "review", "size": 20,
             "selectable": True, "items": [{"path": "/archive", "name": "archive", "size": 20,
                                             "unique": {"count": 0, "size": 0, "complete": True}}]},
            {"id": "cloud", "title": "سحابة", "desc": "مزامنة", "risk": "info", "size": 30,
             "selectable": False, "action": {"kind": "howto", "label": "إدارة"},
             "items": [{"path": "/cloud", "name": "cloud", "size": 30, "note": "راجعها"}]},
        ]}
        plan = fullclean.build_plan([{"kind": "caches", "job": job["id"], "target": "Mac", "result": result}])
        self.assertEqual(len(plan["advice"]), 1)
        self.assertEqual(plan["advice"][0]["items"][0]["note"], "راجعها")
        archive = plan["items"][0]
        self.assertFalse(archive["default_on"])
        self.assertIn("كل ملفاته موجودة في مكان آخر", archive["desc"])
        self.assertEqual(archive["unique"][0]["count"], 0)

    def test_phone_default_on_rules(self):
        job = self._job("SERIAL")
        categories = [{"id": cid, "title": cid, "desc": "desc", "risk": "safe", "size": 1,
                       "items": [{"path": "/" + cid, "name": cid, "size": 1}]}
                      for cid in ("app-caches", "thumbs", "device-logs", "trash", "installers")]
        plan = fullclean.build_plan([{"kind": "caches", "job": job["id"], "target": "Phone", "result": {"categories": categories}}])
        self.assertEqual([item["default_on"] for item in plan["items"]], [True, True, True, False, False])
        self.assertTrue(all(item["device"] and item["group"] == "phone" for item in plan["items"]))
        self.assertTrue(all("يُحذف نهائيًا من الهاتف" in item["desc"] for item in plan["items"]))

    def test_apply_routes_phone_and_mac(self):
        phone, mac = self._job("SERIAL"), self._job()
        f = {"cancel": False, "progress": "", "report": None, "state": "applying", "error": ""}
        chosen = [{"job": phone["id"], "paths": ["/phone"], "title": "phone", "target": "p", "size": 1, "count": 1},
                  {"job": mac["id"], "paths": ["/mac"], "title": "mac", "target": "m", "size": 1, "count": 1}]
        with patch("adbclean.remove", return_value=[{"ok": True}]) as phone_remove, patch.object(C, "remove", return_value=[{"ok": True}]) as mac_remove:
            fullclean._apply(f, chosen)
        phone_remove.assert_called_once_with(phone, ["/phone"])
        mac_remove.assert_called_once_with(mac["id"], ["/mac"], False)

    def test_public_exposes_health(self):
        f = {"id": "x", "state": "ready", "progress": "ok", "steps": [], "started": 1,
             "health": {"cards": []}, "phone_health": {"Phone": {"cards": []}}}
        result = fullclean.public(f)
        self.assertEqual(result["health"], f["health"])
        self.assertEqual(result["phone_health"], f["phone_health"])


if __name__ == "__main__":
    unittest.main()
