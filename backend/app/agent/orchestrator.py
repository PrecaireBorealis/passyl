"""Intent → fixed pipeline → Number Guard → reply writer (spec 4.2, 12)."""
import json
import time
from datetime import timedelta
from pathlib import Path

from ..actions import executor, store
from ..actions.executor import ActionError
from ..adapters.synthetic import get_adapter
from ..clock import today
from ..engine import brief as brief_mod
from . import intents, memory, number_guard, templates, tools
from .llm import LLMUnavailable, chat, tool_loop
from .trace import Trace

PROMPTS = Path(__file__).parent / "prompts"


def _compact(obj):
    """Drop nulls and long Hindi descriptions to keep the LLM prompt short."""
    if isinstance(obj, dict):
        return {k: _compact(v) for k, v in obj.items() if v is not None and k not in ("description_hi", "params")}
    if isinstance(obj, list):
        return [_compact(v) for v in obj]
    return obj


def write_reply(intent: str, lang: str, channel: str, tool_json: dict, fallback: str, tr: Trace, merchant_id: str) -> str:
    max_words = 60 if channel == "voice" else 90
    t0 = time.perf_counter()
    try:
        prompt = (PROMPTS / "write_reply.md").read_text().format(
            intent=intent, lang={"en": "English", "hi": "Hindi (Devanagari)"}.get(lang, "Hinglish (Roman script)"),
            max_words=max_words, memory_json=json.dumps(memory.durable(merchant_id), default=str)[:800],
            tool_json=json.dumps(_compact(tool_json), default=str, ensure_ascii=False))
        r = chat([{"role": "user", "content": prompt}], system=(PROMPTS / "system.md").read_text(), timeout=8,
                 max_tokens=220)
        text = r["text"].strip().strip('"')
        if not text:
            raise LLMUnavailable("empty reply")
        g = number_guard.check(text, tool_json)
        ms = (time.perf_counter() - t0) * 1000
        if g["ok"] and len(text.split()) <= max_words * 1.3:
            tr("llm_write", ms, "reply written, number guard ok")
            return text
        tr("llm_write", ms, f"number guard rejected {g['unmatched'] or 'length'}; using template")
    except LLMUnavailable as e:
        from .llm import provider
        why = "no LLM configured" if provider() == "none" else f"LLM unavailable: {str(e)[:50]}"
        tr("llm_write", (time.perf_counter() - t0) * 1000, f"template reply ({why}); numbers from tools")
    return fallback


def handle(text: str, merchant_id: str, lang: str | None = None, channel: str = "chat") -> dict:
    a = get_adapter()
    if a.get_merchant(merchant_id) is None:
        raise KeyError(merchant_id)
    s = memory.session(merchant_id)
    tr = Trace()
    lang = lang or intents.language(text, s["lang"])
    s["lang"] = lang
    pending = None
    if s["pending_action_id"]:
        act = store.get_action(s["pending_action_id"])
        pending = act if act and act["status"] == "draft" else None
    t0 = time.perf_counter()
    cls = intents.classify(text, pending is not None, s["last_intent"])
    intent = cls["intent"]
    tr("classify", (time.perf_counter() - t0) * 1000, f"{intent} via {cls['via']}")
    d = today()
    cards, tool_json, pending_action, fallback = [], {}, None, ""

    def why_card():
        h = cls.get("hours") or [None, None]
        if s["last_why"] and not cls.get("hours"):
            tr("explain_change", 1, "cached Why card")
            return s["last_why"]
        if intent == "WHY":
            summ = tr.timed("get_summary", lambda: tools.get_summary(merchant_id, d.isoformat()),
                            lambda r: f"₹{r['revenue_today']:,} vs normal ₹{r['revenue_normal']:,}" if r["revenue_normal"]
                            else f"₹{r['revenue_today']:,} so far (no normal yet)")
            tool_json["summary"] = summ
        card = tools.explain_change(merchant_id, d.isoformat(), h[0], h[1], trace=tr)
        s["last_why"] = card
        return card

    try:
        if intent == "WHY":
            card = why_card()
            tool_json["why"] = card
            cards.append({"type": "why_card", "data": card})
            fallback = templates.why(card, lang)
        elif intent == "RECOMMEND":
            card = why_card()
            strat = tr.timed("rank_strategies", lambda: tools.rank_strategies(merchant_id, d.isoformat(), card),
                             lambda r: ", ".join(f"{o['id']} ₹{o['expected_profit']}" for o in r["options"]))
            tr("check_policy", 1, "; ".join(f"{o['id']}: {'pass' if o['policy']['passed'] else 'fail'}" for o in strat["options"]))
            rec = next((o for o in strat["options"] if o["id"] == strat["recommended_id"]), None)
            strat["draft_action_id"] = None
            if rec:
                draft = executor.create_draft(merchant_id, rec)
                strat["draft_action_id"] = draft["id"]
                s["pending_action_id"] = draft["id"]
                pending_action = {"id": draft["id"], "kind": draft["kind"], "title_hi": rec["title_hi"]}
            s["last_strategies"] = strat
            tool_json["strategies"] = strat
            cards.append({"type": "strategy_card", "data": strat})
            fallback = templates.recommend(strat, lang)
        elif intent == "APPROVE":
            if not pending:
                fallback = templates.no_pending(lang)
            else:
                live = tr.timed("execute_action", lambda: executor.approve(pending["id"]),
                                lambda r: f"live: {r['n_treat']} treat, {r['n_holdout']} holdout")
                s["pending_action_id"], s["live_action_id"] = None, live["id"]
                tool_json["action"] = live
                cards.append({"type": "action_live", "data": live})
                fallback = templates.approve(live, lang)
        elif intent == "MODIFY":
            if not pending:
                fallback = templates.no_pending(lang)
            else:
                mp = cls.get("modify") or {}
                act = tr.timed("modify_action", lambda: executor.modify(pending["id"], mp.get("budget"), mp.get("end_hour")),
                               lambda r: f"{r['status']}, cost ₹{r['expected']['expected_cost']}")
                strat = s.get("last_strategies") or {"options": []}
                for o in strat["options"]:
                    if o["kind"] == act["kind"]:
                        o.update(expected_cost=act["expected"]["expected_cost"], expected_profit=act["expected"]["expected_profit"],
                                 n_target=act["expected"]["n_target"], policy=act["policy"])
                tool_json["action"] = {"status": act["status"], **act["expected"]}
                cards.append({"type": "strategy_card", "data": strat})
                pending_action = {"id": act["id"], "kind": act["kind"]} if act["status"] == "draft" else None
                fallback = templates.modify(act, lang)
        elif intent == "UNDO":
            target = s["live_action_id"] or (pending["id"] if pending else None)
            if not target:
                fallback = templates.no_pending(lang)
            else:
                res = tr.timed("undo_action", lambda: executor.undo(target), lambda r: r["status"])
                s["live_action_id"] = s["pending_action_id"] = None
                tool_json["action"] = res
                fallback = templates.undo(lang)
        elif intent == "BRIEF":
            b = tr.timed("brief", lambda: brief_mod.brief(a, merchant_id, d + timedelta(days=1)),
                         lambda r: "with last result" if r["last_action_result"] else "no action result yet")
            tool_json["brief"] = b
            cards.append({"type": "brief_card", "data": b})
            fallback = templates.brief(b, lang)
        elif intent == "OTHER":
            t1 = time.perf_counter()
            seen: list = []

            def run(name, args):
                args = {**args, "merchant_id": merchant_id}
                r = tools.run(name, args)
                seen.append(r)
                tr(name, 1, "read-only tool")
                return r
            try:
                system = (PROMPTS / "system.md").read_text() + "\n" + (PROMPTS / "open_qa.md").read_text() + \
                    f"\nmerchant_id={merchant_id}, today={d.isoformat()}"
                ans = tool_loop(system, text, tools.SCHEMAS, run)
                g = number_guard.check(ans, seen)
                tr("llm_answer", (time.perf_counter() - t1) * 1000, "ok" if g["ok"] else f"rejected {g['unmatched']}")
                fallback = ans if g["ok"] and ans else templates.clarify(lang)
            except LLMUnavailable:
                fallback = templates.clarify(lang)
            cards.append({"type": "idk_card", "data": {"message": fallback}})
            s["last_intent"] = intent
            memory.remember_turn(merchant_id, text, fallback)
            return _response(fallback, lang, intent, cards, pending_action, tr)
        else:  # CLARIFY
            fallback = templates.clarify(lang)
    except ActionError as e:
        fallback = templates.error(e.code, e.message_hi, e.message_en, lang)
        tr("error", 1, e.code)
    except ValueError as e:  # e.g. a window with no completed hours yet
        fallback = templates.clarify(lang)
        tr("error", 1, str(e))

    reply = write_reply(intent, lang, channel, tool_json, fallback, tr, merchant_id) if tool_json else fallback
    s["last_intent"] = intent
    memory.remember_turn(merchant_id, text, reply)
    return _response(reply, lang, intent, cards, pending_action, tr)


def _response(reply, lang, intent, cards, pending_action, tr) -> dict:
    return {"reply_text": reply, "lang": lang, "intent": intent, "cards": cards, "pending_action": pending_action,
            "trace": tr.items, "audio_b64": None, "data_label": "synthetic"}
