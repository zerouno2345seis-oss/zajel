import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cleaner
import clean_knowledge


class CleanerFullTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.old_home = cleaner.HOME
        cleaner.HOME = self.home
        self.old_locations = clean_knowledge.LOCATIONS
        clean_knowledge.LOCATIONS = [dict(item) for item in self.old_locations]
        cleaner.JOBS.clear()
        (self.home / "Documents").mkdir()

    def tearDown(self):
        cleaner.HOME = self.old_home
        clean_knowledge.LOCATIONS = self.old_locations
        cleaner.JOBS.clear()
        self.tmp.cleanup()

    def _large(self, path, size=50 * 1024 * 1024 + 1):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            fh.truncate(size)
        return path

    def test_categories_unique_move_keep_and_health_failure(self):
        onedrive = self._large(self.home / "Library/CloudStorage/OneDrive-account/file.bin")
        archive = self.home / "iCloud Drive (old)"
        unique = self._large(archive / "new.bin", 8)
        archive.mkdir(exist_ok=True)
        self._large(archive / "same.bin")
        self._large(self.home / "Documents/same.bin")
        recording = self._large(self.home / ".gemini/antigravity-ide/browser_recordings/capture.bin")
        self.assertFalse(clean_knowledge.matches_keep(recording.parent, self.home))
        vm = self.home / "Library/Application Support/Claude/vm_bundles/vm.img"
        self._large(vm)

        job = cleaner.new_job("caches", str(self.home))
        # Keep the fixtures compact while exercising category thresholds.
        def fake_du(path):
            path = Path(path)
            total = path.stat().st_size if path.is_file() else sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
            return total

        with patch.object(cleaner, "du_kb", side_effect=fake_du):
            with patch.dict("sys.modules", {"health": None}):
                result = cleaner.caches(job)

        cats = {cat["id"]: cat for cat in result["categories"]}
        self.assertIn("agent-recordings", cats)
        self.assertFalse(cats["cloud-onedrive"]["selectable"])
        self.assertNotIn(str(onedrive.parent), job["allowed"])

        self.assertIn(str(recording.parent), job["allowed"])
        self.assertEqual(cats["icloud-archives"]["items"][0]["unique"]["count"], 1)
        self.assertIsNone(result["health"])

        job["unique_ok"] = {str(archive)}
        job["unique"] = {str(archive): ["new.bin", "same.bin"]}
        dest = self.home / "saved"
        (dest / "same.bin").parent.mkdir(parents=True)
        (dest / "same.bin").write_text("do not overwrite")
        moved = cleaner.move_unique(job["id"], str(archive), str(dest))
        self.assertEqual(moved["moved"], 1)
        self.assertEqual(moved["skipped"], 1)
        self.assertFalse(unique.exists())
        self.assertEqual((dest / "same.bin").read_text(), "do not overwrite")

        job["allowed"].add(str(vm.parent))
        report = cleaner.remove(job["id"], [str(vm.parent)], permanent=False)
        self.assertFalse(report[0]["ok"])
        self.assertTrue(vm.exists())

if __name__ == "__main__":
    unittest.main()
