import types
import unittest
from unittest import mock

import telegram_link as TL


def fake_runner(behaviour):
    """behaviour: وكيل ← ("raise", رسالة) | ("done", نص) | ("error", خطأ) | ("silent", None)"""
    jobs, view = {}, {}

    def start_chat(agent, q, ctx, conv):
        kind, val = behaviour.get(agent, ("raise", "غير مثبّت"))
        if kind == "raise":
            raise ValueError(val)
        jid = "j-" + agent
        jobs[jid] = {"steps": []}
        view[jid] = {"state": "running", "text": "", "error": ""} if kind == "silent" else \
            {"state": "done", "text": val, "error": ""} if kind == "done" else {"state": "error", "text": "", "error": val}
        return {"job": jid, "conversation": "c1"}

    def stop(jid, why=""):
        view[jid]["state"] = "stopped"

    names = {a: {"name": a.capitalize(), "bin": a} for a in ["agy", "codex", "claude", "pi", "hermes", "opencode"]}
    return types.SimpleNamespace(AGENTS=names, JOBS=jobs, start_chat=start_chat, job_view=lambda j: view[j], stop=stop,
                                 _which=lambda b: True, friendly=lambda m: m, set_settings=lambda d: None)


class Failover(unittest.TestCase):
    def run_ask(self, behaviour, cfg=None, presence=None, failover=None):
        sent, forwarded = [], []
        cfg = {"conv": "c1", "agent_fixed": "", **(cfg or {})}
        runner = fake_runner(behaviour)
        with mock.patch.dict("sys.modules", {"agent_runner": runner}), \
             mock.patch.object(TL, "_cfg", lambda: cfg), mock.patch.object(TL, "_save_cfg", lambda d: cfg.update(d)), \
             mock.patch.object(TL, "send", lambda t, c=None, **k: sent.append(t) or 1), \
             mock.patch.object(TL, "edit", lambda c, m, t, *a, **k: sent.append(t)), \
             mock.patch.object(TL, "_quiet", lambda *a, **k: None), mock.patch.object(TL, "_check_pending", lambda *a: None), \
             mock.patch.object(TL, "_presence", lambda: presence or {}), mock.patch.object(TL, "_mail_repo", lambda: True), \
             mock.patch.object(TL, "_forward", lambda u, h: forwarded.append((u, h))), \
             mock.patch.object(TL, "HOST", "MacBook"), mock.patch.object(TL.time, "sleep", lambda s: None), \
             mock.patch.object(TL, "SILENCE", -1):
            TL._ask(7, "سؤال", failover=failover)
        return sent, forwarded

    def test_next_agent_when_first_fails(self):
        sent, fwd = self.run_ask({"agy": ("raise", "usage limit reached"), "hermes": ("done", "الجواب هنا بالتفصيل")})
        self.assertTrue(any("الجواب هنا" in t and "MacBook · Hermes" in t and "Agy على MacBook لم يستجب" in t for t in sent))
        self.assertEqual(fwd, [])

    def test_silent_agent_is_skipped(self):
        sent, _ = self.run_ask({"agy": ("silent", None), "hermes": ("done", "جواب")})
        self.assertTrue(any("سكت دقيقتين" in t and "Hermes" in t for t in sent))

    def test_all_fail_goes_to_other_device_once(self):
        now = TL.time.time()
        sent, fwd = self.run_ask({}, presence={"iMac": {"ts": now}})
        self.assertEqual(len(fwd), 1)
        u, host = fwd[0]
        self.assertEqual(host, "iMac")
        self.assertEqual(u["zajel_failover"]["tried"], ["MacBook"])
        self.assertEqual(u["message"]["text"], "سؤال")

    def test_no_bounce_back(self):
        now = TL.time.time()
        sent, fwd = self.run_ask({}, presence={"iMac": {"ts": now}}, failover={"from": "iMac", "tried": ["iMac"], "notes": ["x"]})
        self.assertEqual(fwd, [])
        self.assertTrue(any("لم يستجب أي وكيل" in t for t in sent))

    def test_manual_choice_is_not_switched(self):
        now = TL.time.time()
        sent, fwd = self.run_ask({"codex": ("error", "boom"), "hermes": ("done", "لا ينبغي")}, cfg={"agent_fixed": "codex"},
                                 presence={"iMac": {"ts": now}})
        self.assertEqual(fwd, [])
        self.assertFalse(any("لا ينبغي" in t for t in sent))


if __name__ == "__main__":
    unittest.main()
