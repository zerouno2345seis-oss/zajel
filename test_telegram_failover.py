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

class GatewayElection(unittest.TestCase):
    def test_desktop_wins_even_if_laptop_announces_gateway(self):
        now = 10000
        with mock.patch.object(TL.time, "time", return_value=now), mock.patch.object(TL, "HOST", "iMac"), \
             mock.patch.object(TL, "LAPTOP", False), mock.patch.dict(TL.MAIL, {"presence": {"MacBook": {"ts": now, "laptop": True, "gateway": True}}}):
            self.assertEqual(TL._other_gateway(), "")
        with mock.patch.object(TL.time, "time", return_value=now), mock.patch.object(TL, "HOST", "MacBook"), \
             mock.patch.object(TL, "LAPTOP", True), mock.patch.dict(TL.MAIL, {"presence": {"iMac": {"ts": now, "laptop": False, "gateway": False}}}):
            self.assertEqual(TL._other_gateway(), "iMac")

    def test_stale_desktop_allows_laptop_and_tie_has_one_winner(self):
        with mock.patch.object(TL.time, "time", return_value=10000), mock.patch.object(TL, "HOST", "a"), \
             mock.patch.object(TL, "LAPTOP", True), mock.patch.dict(TL.STATE, {"gateway": False}), \
             mock.patch.dict(TL.MAIL, {"presence": {"desktop": {"ts": 1, "laptop": False}, "b": {"ts": 10000, "laptop": True, "gateway": True}}}):
            self.assertEqual(TL._other_gateway(), "")

    def test_idle_return_and_activity(self):
        presence = {"iMac-kenana-2": {"ts": 10000, "laptop": False}, "MacBook": {"ts": 10000, "laptop": True}}
        with mock.patch.object(TL.time, "time", return_value=10000), mock.patch.object(TL, "_presence", return_value=presence), \
             mock.patch.object(TL, "_set_target") as target, mock.patch.object(TL, "send") as send, \
             mock.patch.dict(TL.STATE, {"gateway": True}), mock.patch.dict(TL.MAIL, {"target": "MacBook", "activity": 8201}):
            TL._revert_idle_target()
            target.assert_not_called()
            TL.MAIL["activity"] = 8200
            TL._revert_idle_target()
            target.assert_called_once_with("iMac-kenana-2")
            send.assert_called_once_with("رجعتُ إلى iMac-kenana-2")

class RoundFlow(unittest.TestCase):
    def test_selection_and_start(self):
        judge = types.SimpleNamespace(get_default_judge=lambda: "claude", set_default_judge=mock.Mock(),
                                      start_round=mock.Mock(return_value={"round_id": "r1", "agents": {}, "judge_state": "idle"}))
        runner = types.SimpleNamespace(agents=lambda: [{"id": a, "name": a, "installed": True} for a in ("claude", "codex", "gemini")])
        with mock.patch.dict("sys.modules", {"judge": judge, "agent_runner": runner}), \
             mock.patch.object(TL, "send"), mock.patch.object(TL, "edit"), mock.patch.object(TL.threading, "Thread") as thread:
            TL._round_begin(7)
            TL.ROUND_DRAFT[7].update(awaiting=False, question="ما الجواب؟")
            TL._round_callback(7, 1, "j:codex")
            self.assertNotIn("codex", TL.ROUND_DRAFT[7]["answerers"])
            TL._round_callback(7, 1, "auto")
            TL._round_callback(7, 1, "deep")
            TL._round_callback(7, 1, "send")
            judge.start_round.assert_called_once_with("ما الجواب؟", ["gemini"], judge="codex", auto_judge=True, deep=True)
            thread.return_value.start.assert_called_once()

    def test_status_needs_input_and_answer_is_sent_as_text(self):
        status = {"round_id": "r1", "judge_state": "idle", "agents": {"codex": {"name": "Codex", "state": "needs_input", "answer": "**جواب**"}}}
        self.assertIn("Codex ⚠️ ينتظر ردّك", TL._round_status_view(status)[0])
        with mock.patch.dict("sys.modules", {"judge": types.SimpleNamespace(round_status=lambda rid: status)}), mock.patch.object(TL, "send") as send:
            TL._round_callback(7, 1, "view:r1:codex")
            send.assert_called_once_with("**جواب**", 7)
