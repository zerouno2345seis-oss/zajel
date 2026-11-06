import unittest
from unittest import mock

import health


class ParserTests(unittest.TestCase):
    def test_parse_pmset_g_and_uptime(self):
        self.assertEqual(health.parse_pmset_g("Now drawing from 'Battery Power'"),
                         {"power_source": "البطارية"})
        self.assertAlmostEqual(health.parse_uptime_days("11:05  up 8 days, 02:30, 3 users"), 8 + 150 / 1440)
        self.assertAlmostEqual(health.parse_uptime_days("11:05  up 02:30, 3 users"), 150 / 1440)

    def test_parse_pmset_custom(self):
        parsed = health.parse_pmset_custom("""Battery Power:
 standby              1
 hibernatemode        3
AC Power:
 standby              0
 hibernatemode        3
""")
        self.assertEqual(parsed["battery"], {"standby": 1, "hibernatemode": 3})
        self.assertEqual(parsed["ac"], {"standby": 0, "hibernatemode": 3})

    def test_parse_wake_log(self):
        sample = """2026-11-03 05:25:37 -0300 Sleep               \tEntering Sleep state due to 'Sleep Service Back to Sleep':TCPKeepAlive=active Using Batt (Charge:68%) 917 secs
2026-11-03 05:54:47 -0300 Wake                \tWake from Standby [CDNVA] : due to lid Using BATT (Charge:68%)
2026-11-03 05:54:47 -0300 WakeTime            \tWakeTime: 9.400 sec
2026-11-06 10:07:27 -0300 Wake                \tDarkWake to FullWake from Deep Idle [CDNVA] : due to UserActivity Assertion Using AC (Charge:80%)
2026-11-06 10:52:54 -0300 Notification        \tDisplay is turned off
"""
        parsed = health.parse_wake_log(sample)
        self.assertEqual((parsed["deep"], parsed["normal"], parsed["sleep"]), (1, 1, 1))
        self.assertEqual(parsed["slow_wakes"], [9.4])
        self.assertFalse(parsed["display_only"])
        only = "2026-11-06 10:52:54 -0300 Notification        \tDisplay is turned off\n2026-11-06 10:59:35 -0300 Notification        \tDisplay is turned on"
        self.assertTrue(health.parse_wake_log(only)["display_only"])

    def test_parse_assertions_groups_process_and_ignores_system(self):
        parsed = health.parse_assertions("""pid 55(Perplexity): [0x1] PreventUserIdleSystemSleep named: keep awake
pid 55(Perplexity): [0x2] NoIdleSleepAssertion named: another
pid 1(powerd): [0x3] PreventUserIdleSystemSleep named: system
pid 2(WindowServer): [0x4] NoIdleSleepAssertion named: display
""")
        self.assertEqual(parsed, {"Perplexity": 2})

    def test_parse_swap_and_memory_pressure(self):
        parsed = health.parse_swap("vm.swapusage: total = 10.00G  used = 4.25G  free = 5.75G")
        self.assertAlmostEqual(parsed["used_gb"], 4.25)
        self.assertEqual(health.parse_memory_pressure("System-wide memory free percentage: 41%"), 41)

    def test_group_rss_and_cpu_threshold(self):
        lines = """RSS   %CPU COMM
102400 12.0 /Applications/Claude.app/Contents/MacOS/Claude Helper
51200 60.5 /usr/libexec/mds_stores
20480 50.0 /Applications/Safari.app/Contents/MacOS/Safari
"""
        self.assertEqual(health.group_rss(lines)[0], {"name": "Claude", "rss_mb": 100.0})
        self.assertEqual(health.parse_cpu_hogs(lines), [{"name": "mds_stores", "cpu_percent": 60.5}])

    def test_parse_sysctl_and_disk(self):
        parsed = health.parse_sysctl("""vm.swapusage: total = 2G  used = 512M  free = 1G
hw.memsize: 25769803776
hw.ncpu: 14
machdep.cpu.brand_string: Apple M5 Pro
kern.boottime: { sec = 1793900000, usec = 0 } Thu Nov  5 00:00:00 2026
""")
        self.assertEqual(parsed["ram_bytes"], 25769803776)
        self.assertEqual(parsed["cpu_count"], 14)
        self.assertEqual(parsed["cpu"], "Apple M5 Pro")
        self.assertEqual(parsed["swap"]["used_bytes"], 512 * 1024**2)
        self.assertEqual(parsed["boot_epoch"], 1793900000)
        disk = health.parse_disk("Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/disk3s1 1000000 850000 150000 85% /")
        self.assertEqual(disk["free_bytes"], 150000 * 1024)
        self.assertEqual(disk["free_percent"], 15)

    def test_parse_login_items(self):
        self.assertEqual(health.parse_login_items("Claude, OneDrive, Terminal"), ["Claude", "OneDrive", "Terminal"])
        self.assertEqual(health.parse_login_items(""), [])


class ScanTests(unittest.TestCase):
    def test_returns_complete_schema_when_all_commands_fail(self):
        with mock.patch.object(health, "run_command", side_effect=OSError("unavailable")):
            result = health.scan()
        self.assertEqual(set(result), {"cards", "facts"})
        self.assertEqual({card["id"] for card in result["cards"]},
                         {"sleep", "awake_blockers", "memory", "top_apps", "cpu_hogs", "disk", "login_items"})
        for card in result["cards"]:
            self.assertEqual(set(card), {"id", "title", "status", "summary", "details", "advice", "commands"})
            self.assertEqual(card["status"], "warn")


if __name__ == "__main__":
    unittest.main()
