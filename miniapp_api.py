"""واجهة التطبيق المصغّر على الماك: كل طلب يصل من الصفحة عبر الوسيط، فيُنفَّذ هنا بما في زاجل من منطق.
- لا منطق جديد لما هو موجود: الملفات والعمليات عبر agent_server.call (الأدوات الحارسة)، والشاشات من telegram_more، والتيليجرام من telegram_account.
- مستوى كل عملية يُقرَّر هنا في الخادم (جدول LEVELS) لا في الصفحة:
  g أخضر: فوري. y أصفر: ملخص ثم تأكيد برمز لمرة واحدة يصدره الخادم. r أحمر: رمز من ٤ أرقام يظهر على شاشة الماك، صالح ٥ دقائق.
- عملية غير مذكورة في الجدول تُرفض.
- لا يُقبل إلا طلب مستخدم تيليجرام المقترن (يتحقق الوسيط من التوقيع، ونتحقق هنا ثانية من رقمه)."""
import random
import threading
import time

import telegram_link as TL

G, Y, R = "g", "y", "r"
CODE_SECS = 300
CONFIRM_SECS = 300

LEVELS = {
    "home": G, "files.places": G, "files.list": G, "files.search": G, "files.send": G, "files.copy": Y, "files.move": R, "files.delete": R,
    "assist.agents": G, "assist.ask": G, "assist.poll": G, "assist.stop": G,
    "tg.state": G, "tg.search": G, "tg.libs": G, "tg.lib_toggle": G, "tg.lib_add": G, "tg.suggest": G, "tg.inbox": G, "tg.inbox_poll": G, "tg.inbox_apply": G,
    "tg.watch": G, "tg.watch_add": G, "tg.watch_toggle": G, "tg.watch_remove": G, "tg.backup": G, "tg.backup_toggle": G, "tg.backup_candidates": G, "tg.backup_now": Y,
    "tg.dls": G, "tg.get": G, "tg.cancel": G,
    "more.list": G, "more.section": G, "device.list": G, "device.set": G,
    "approvals.list": G, "approvals.reject": G, "approvals.approve": R,
    "act.phone_connect": Y, "act.sync_run": Y, "act.wa_digest": G, "act.agent_ping": G, "act.stop_server": R, "act.apply_update": R,
    "act.term_send": R, "act.term_stop": R, "act.setting": G,
    "round.agents": G, "round.start": Y, "round.last": G, "round.status": G, "round.select": G, "round.judge": G, "round.deepen": G,
    "round.judge_default": G, "round.send_report": G,
}
LABELS = {"files.copy": "نسخ ملفات", "tg.backup_now": "نسخ المحادثات المختارة الآن", "act.phone_connect": "وصل الجوال لاسلكيًا", "act.sync_run": "المزامنة الآن",
          "act.stop_server": "إيقاف خادم", "act.apply_update": "تنزيل التحديث وإعادة تشغيل زاجل", "act.term_send": "الكتابة في طرفية وكيل", "approvals.approve": "موافقة على عملية معلّقة", "act.term_stop": "إغلاق جلسة طرفية",
          "round.start": "سؤال لعدة وكلاء"}
SUMMARY = {"files.copy": "ينسخ العناصر المختارة إلى الوجهة. لا يحذف شيئًا من الأصل.", "tg.backup_now": "يجلب الجديد من المحادثات المختارة إلى الماك. يستغرق دقائق.",
           "act.phone_connect": "يجرّب العنوان المحفوظ ثم اكتشاف الشبكة. لا يغيّر شيئًا في الجوال.", "act.sync_run": "يزامن هذا الجهاز مع المستودع الخاص (نحو دقيقة).",
           "round.start": "يرسل سؤالك إلى الوكلاء المختارين في طرفيات الماك فيبحثون بأدواتهم (قد يستغرق عشر دقائق، وثلاثين في البحث المتعمق)."}

PENDING = {}       # id ← {"op","args","level","code","until","tries","label"}
LOCK = threading.Lock()


DELEGATED_RED = ("files.move", "files.delete")


class Refused(Exception):
    pass


def level_of(op):
    lv = LEVELS.get(op)
    if lv is None:
        raise Refused("عملية غير معروفة؛ رُفضت.")
    return lv


def authorize(user_id):
    """لا يُسمع إلا للمستخدم المقترن."""
    cid = TL._cfg().get("chat_id")
    if not cid or int(user_id or 0) != int(cid):
        raise Refused("هذا الحساب غير مقترن بزاجل.")


def _id():
    return "%08x" % random.randint(0, 0xFFFFFFFF)


def handle(req):
    """req: {user, op, args, confirm?}. يعيد {ok, data} أو {error} أو {needs: confirm|code}."""
    try:
        authorize(req.get("user"))
        op, args = req.get("op"), req.get("args") or {}
        if op == "red.confirm":
            return red_confirm(args)
        lv = level_of(op)
        if op in DELEGATED_RED:             # الحذف والنقل: agent_server نفسه يحفظها معلّقة، فتصل بطاقة موافقة برمز على شاشة الماك
            r = _tool("move" if op == "files.move" else "delete", args)
            return {"ok": True, "approval": bool(r.get("pending")), "data": {"id": r.get("id"), "preview": r.get("preview")} if r.get("pending") else r.get("result")}
        if lv == Y:
            return _yellow(op, args, req.get("confirm"))
        if lv == R:
            return _red_begin(op, args)
        return {"ok": True, "data": run(op, args)}
    except Refused as e:
        return {"error": str(e), "refused": True}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": "تعذّر تنفيذ الطلب: " + str(e)[:120]}


def _yellow(op, args, token):
    now = time.time()
    with LOCK:
        for k in [k for k, v in PENDING.items() if v["until"] < now]:
            PENDING.pop(k, None)
        p = PENDING.get(token or "")
        if p and p["op"] == op and p["level"] == Y and p["args"] == args:
            PENDING.pop(token)
            ok = True
        else:
            ok = False
        if not ok:
            tid = _id()
            PENDING[tid] = {"op": op, "args": args, "level": Y, "until": now + CONFIRM_SECS}
            return {"needs": "confirm", "token": tid, "summary": SUMMARY.get(op, LABELS.get(op, op)), "label": LABELS.get(op, op)}
    return {"ok": True, "data": run(op, args)}


def _red_begin(op, args):
    code = "%04d" % random.randint(0, 9999)
    rid = _id()
    label = LABELS.get(op, op) + (": " + str(args.get("label") or args.get("name") or "") if isinstance(args, dict) else "")
    with LOCK:
        PENDING[rid] = {"op": op, "args": args, "level": R, "code": code, "until": time.time() + CODE_SECS, "tries": 0, "label": label}
    TL._show_on_mac(label, code)              # الرمز على شاشة الماك وحدها، لا في الرد إلى الهاتف
    return {"needs": "code", "id": rid, "label": label, "expires_in": CODE_SECS}


def red_confirm(args):
    rid, code = str(args.get("id") or ""), str(args.get("code") or "").strip()
    with LOCK:
        p = PENDING.get(rid)
        if not p or p["level"] != R or p["until"] < time.time():
            PENDING.pop(rid, None)
            raise ValueError("انتهت صلاحية الرمز؛ ابدأ العملية من جديد.")
        if code != p["code"]:
            p["tries"] += 1
            if p["tries"] >= 3:
                PENDING.pop(rid, None)
                raise ValueError("أُلغيت العملية بعد ثلاث محاولات خاطئة.")
            raise ValueError("الرمز غير صحيح. انظر إلى شاشة الماك.")
        PENDING.pop(rid)
    return {"ok": True, "data": run(p["op"], p["args"])}


# ================= التنفيذ =================
def _tool(name, args):
    import agent_server
    r = agent_server.call(name, args, agent="miniapp")
    if r.get("error") or r.get("refused"):
        raise ValueError(r.get("error"))
    return r


def _items(lst):
    return [{k: v for k, v in d.items() if k != "cancel"} for d in lst]


def run(op, a):
    import telegram_more as M
    if op == "home":
        import shutil
        import agent_server
        du = shutil.disk_usage("/")
        acc = M._account()
        return {"host": TL.HOST, "version": TL._version(), "disk": {"used": du.used, "total": du.total}, "pending": agent_server.pending_list(),
                "inbox": acc.A.new_inbox() if acc and acc.linked() else 0, "downloads": acc.A.active_downloads() if acc and acc.linked() else 0,
                "linked": bool(acc and acc.linked())}
    if op == "device.list":
        pres = TL._presence()
        return {"target": TL._target(), "devices": [{"name": h, "online": time.time() - p.get("ts", 0) < TL.GW_FRESH, "version": p.get("version", "")} for h, p in sorted(pres.items())]}
    if op == "device.set":
        TL._set_target(str(a.get("name")))
        return {"target": TL._target()}
    if op == "files.places":
        return _tool("places", {}).get("result")
    if op == "files.list":
        return _tool("list_folder", {"place": a.get("place"), "path": a.get("path") or ""}).get("result")
    if op == "files.search":
        return _tool("search_all", {"q": str(a.get("q") or "")}).get("result")
    if op == "files.send":
        return _tool("send_to_telegram", {"place": a.get("place"), "path": a.get("path")}).get("result")
    if op == "files.copy":
        return _tool("copy", {k: a.get(k) for k in ("src_place", "items", "dst_place", "dst_path") if k in a} or a).get("result")
    if op == "assist.agents":
        import agent_runner
        return [{"id": k, "name": v["name"], "installed": bool(agent_runner._which(v["bin"]))} for k, v in agent_runner.AGENTS.items()]
    if op == "assist.ask":
        import agent_runner
        cands, _ = TL._candidates()
        agent = a.get("agent") if a.get("agent") in agent_runner.AGENTS else (cands[0] if cands else "")
        if not agent:
            raise ValueError("لا وكيل مثبّت.")
        r = agent_runner.start_chat(agent, str(a.get("q") or ""), "", "miniapp")
        return {"job": r["job"], "agent": agent_runner.AGENTS[agent]["name"]}
    if op == "assist.poll":
        import agent_runner
        v = agent_runner.job_view(str(a.get("job")))
        steps = (agent_runner.JOBS.get(str(a.get("job"))) or {}).get("steps") or []
        return {"state": v["state"], "text": v["text"], "error": v["error"], "step": steps[-1]["label"] if steps else ""}
    if op == "assist.stop":
        import agent_runner
        return {"stopped": agent_runner.stop(str(a.get("job")), "أوقفه المستخدم")}
    if op == "approvals.list":
        import agent_server
        return agent_server.pending_list()
    if op == "approvals.approve":
        import agent_server
        return agent_server.approve(str(a.get("id")))
    if op == "approvals.reject":
        import agent_server
        return agent_server.deny(str(a.get("id")))
    if op == "more.list":
        return [{"group": g, "items": [{"key": k, "name": M.TITLES[k]} for k in keys] } for g, keys in M.GROUPS]
    if op == "more.section":
        key = str(a.get("key"))
        if key not in M.TITLES:
            raise ValueError("قسم غير معروف.")
        text, kb = TL._screen(M.ALIAS.get(key, key))
        acts = [{**x, "level": LEVELS[x["op"]], "label": LABELS.get(x["op"], x["op"])} for x in SECTION_ACTIONS.get(key, [])]
        return {"title": M.TITLES[key], "text": text, "actions": acts}
    if op.startswith("round."):
        return _round(op[6:], a)
    if op.startswith("tg."):
        return _tg(op, a)
    if op.startswith("act."):
        return _act(op[4:], a)
    raise Refused("عملية غير مدعومة.")


# أزرار كل قسم (مستواها من LEVELS لا من هنا؛ الصفحة تعرض اللون فقط)
SECTION_ACTIONS = {
    "phone": [{"op": "act.phone_connect"}], "cloud": [{"op": "act.sync_run"}], "wa": [{"op": "act.wa_digest"}],
    "update": [{"op": "act.apply_update"}],
}


ANSWER_CAP = 12000      # حد حجم الجواب في الرد إلى الهاتف


def _round_view(r):
    if not r:
        return None
    r = dict(r)
    r["agents"] = {k: {**v, "answer": v["answer"][:ANSWER_CAP], "truncated": len(v["answer"]) > ANSWER_CAP} for k, v in r["agents"].items()}
    r["verdict"] = r["verdict"][:ANSWER_CAP * 2]
    r["deep_answer"] = r["deep_answer"][:ANSWER_CAP * 2]
    return r


def _round(name, a):
    import judge
    import terminal
    rid = str(a.get("id") or a.get("round_id") or "")
    if name == "agents":
        return {"agents": [{"id": x["id"], "name": x["name"]} for x in terminal.AGENTS if x.get("cmd") and x["id"] not in ("shell", "shell2")],
                "judge": judge.get_default_judge()}
    if name == "start":
        ans = [x for x in (a.get("answerers") or []) if x != judge.PERPLEXITY]       # نافذة Perplexity على الماك لا يقرؤها الهاتف
        return _round_view(judge.start_round(str(a.get("question") or ""), ans, str(a.get("judge") or ""), bool(a.get("auto_judge")), bool(a.get("deep")),
                                             judge_may_answer=a.get("judge_may_answer") is True, length=a.get("length") or ""))
    if name == "last":
        return {"round": _round_view(judge.last_round())}
    if name == "status":
        return _round_view(judge.round_status(rid))
    if name == "select":
        return _round_view(judge.set_selected(rid, str(a.get("agent_id") or ""), bool(a.get("selected"))))
    if name == "judge":
        if a.get("judge"):
            judge.set_default_judge(str(a["judge"]))
        return _round_view(judge.run_judge(rid, str(a.get("judge") or "")))
    if name == "deepen":
        return _round_view(judge.deepen(rid, str(a.get("agent_id") or "")))
    if name == "judge_default":
        return {"judge": judge.set_default_judge(str(a["judge"])) if "judge" in a else judge.get_default_judge()}
    if name == "send_report":
        r = judge.export_round(rid)
        TL.send_file(r["path"], r["title"])
        return {"sent": True, "title": r["title"], "missing": r.get("missing") or []}
    raise Refused("عملية غير مدعومة.")


def _tg(op, a):
    import telegram_account as A
    if not A.linked():
        raise ValueError("حسابك في تيليجرام غير مربوط؛ اربطه من زاجل ← الإعدادات.")
    if op == "tg.state":
        return {"linked": True, "new_inbox": A.new_inbox(), "active": A.active_downloads(), "flood": A.flood_message()}
    if op == "tg.search":
        return A.search(a.get("q"), a.get("scope") or "all", a.get("type") or "all")
    if op == "tg.libs":
        return {"libs": A.libs(), "lists": A.LISTS}
    if op == "tg.lib_toggle":
        return A.lib_set(a.get("id"), bool(a.get("on")))
    if op == "tg.lib_add":
        return A.lib_add(a.get("ref"), a.get("list") or "fiqh")
    if op == "tg.suggest":
        return A.suggestions(str(a.get("q") or "فقه"))
    if op == "tg.inbox":
        return A.inbox_items()
    if op == "tg.inbox_poll":
        return A.inbox_poll()
    if op == "tg.inbox_apply":
        return {"done": A.inbox_apply(a.get("ids"))}
    if op == "tg.watch":
        return {"words": A.watch_words(), "hits": A.hits()}
    if op == "tg.watch_add":
        return A.watch_add(a.get("word"), a.get("where") or "all")
    if op == "tg.watch_toggle":
        return A.watch_toggle(a.get("id"))
    if op == "tg.watch_remove":
        return A.watch_remove(a.get("id"))
    if op == "tg.backup":
        return {"chats": A.backups(), "stats": A.backup_stats()}
    if op == "tg.backup_candidates":
        return A.backup_candidates()
    if op == "tg.backup_toggle":
        return A.backup_set(a.get("id"), a.get("name") or "", bool(a.get("on")))
    if op == "tg.backup_now":
        threading.Thread(target=A.backup_run, daemon=True).start()
        return {"started": True}
    if op == "tg.dls":
        return A.dl_list()
    if op == "tg.get":
        return {"id": A.download(str(a.get("ref")), then=a.get("then") if a.get("then") in ("transcribe", "kindle") else "")}
    if op == "tg.cancel":
        return A.dl_cancel(str(a.get("id")))
    raise Refused("عملية غير مدعومة.")


def _act(name, a):
    import telegram_more as M
    if name == "phone_connect":
        return M._call("phone_connect").get("result")
    if name == "sync_run":
        import app_update
        return app_update.sync_run()
    if name == "wa_digest":
        import whatsapp_watch as W
        return W.digest_now()
    if name == "agent_ping":
        import agent_runner
        return agent_runner.ping(str(a.get("id")))
    if name == "stop_server":
        import servers
        return servers.stop(int(a.get("pid")), bool(a.get("force")))
    if name == "apply_update":
        import app_update
        return app_update.apply()
    if name == "term_send":
        import terminal
        if a.get("agent") not in terminal.BY_ID:
            raise ValueError("وكيل غير معروف.")
        terminal.send(a["agent"], str(a.get("text") or ""), ["Enter"], paste=len(str(a.get("text") or "")) > 300)
        return {"sent": True}
    if name == "term_stop":
        import terminal
        return terminal.stop(str(a.get("agent")))
    if name == "setting":
        key = str(a.get("key"))
        if key not in ("notify_error", "notify_long", "notify_done", "notify_term", "notify_repeat", "quiet_on", "notify_update"):
            raise ValueError("إعداد غير مسموح من التطبيق.")           # اعتماد الحمراء يُفتح من زاجل وحده
        TL._save_cfg({key: bool(a.get("on"))})
        return {key: bool(a.get("on"))}
    raise Refused("عملية غير مدعومة.")
