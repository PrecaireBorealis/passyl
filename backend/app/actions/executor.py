"""Draft → approve (freeze targets, 50/50 holdout, mock Paytm or n8n) → undo (spec 11.1)."""
import uuid
import zlib
from datetime import datetime, timedelta

import numpy as np

from ..adapters.synthetic import get_adapter
from ..clock import now
from ..engine import measure as measure_mod
from ..engine import policy, strategy
from ..engine.simulate import simulate
from . import mock_paytm, n8n, store


class ActionError(Exception):
    def __init__(self, code: str, message_hi: str, message_en: str, status: int = 409):
        self.code, self.message_hi, self.message_en, self.status = code, message_hi, message_en, status


def _ts(hour: int) -> datetime:
    n = now()
    return n.replace(hour=min(hour, 23), minute=0, second=0, microsecond=0)


def create_draft(merchant_id: str, option: dict) -> dict:
    p = option["params"]
    a = {"id": "A_" + uuid.uuid4().hex[:10], "merchant_id": merchant_id, "kind": option["kind"], "params": p,
         "status": "draft", "created_at": now(), "window_start": _ts(p.get("start_hour", now().hour)),
         "window_end": _ts(p.get("end_hour", 22)),
         "expected": {k: option[k] for k in ("expected_profit", "expected_cost", "n_target", "assumptions", "title_hi")},
         "policy": option["policy"]}
    store.insert_action(a)
    store.audit(merchant_id, "agent", "draft_created", {"action_id": a["id"], "kind": a["kind"]})
    return a


def recompute(action: dict, factor: float) -> dict:
    """Shrink the segment (for the budget check): fewer targets, proportional expected cost and profit."""
    e = dict(action["expected"])
    n = max(2, int(e["n_target"] * factor))
    scale = n / e["n_target"]
    e.update(n_target=n, expected_cost=int(e["expected_cost"] * scale), expected_profit=int(e["expected_profit"] * scale))
    return {**action, "expected": e, "params": {**action["params"], "n_target": n},
            "expected_cost": e["expected_cost"]}


def modify(action_id: str, budget: int | None = None, end_hour: int | None = None) -> dict:
    a = store.get_action(action_id)
    if not a or a["status"] != "draft":
        raise ActionError("NO_PENDING_ACTION", "Badalne ke liye koi pending offer nahi hai.", "No pending action to change.")
    pol = get_adapter().get_policy(a["merchant_id"])
    if budget is not None:
        pol = {**pol, "daily_offer_budget": budget}
        a["params"]["budget_cap"] = budget
    if end_hour is not None:
        a["params"]["end_hour"] = end_hour
        a["window_end"] = _ts(end_hour)
    act = {"kind": a["kind"], "params": a["params"], "expected": a["expected"], "expected_cost": a["expected"]["expected_cost"]}
    act, res = policy.shrink_then_block(act, pol, {}, recompute)
    status = "blocked" if res.get("blocked") else "draft"
    store.update_action(action_id, params=act["params"], expected=act["expected"], policy=res, status=status,
                        window_end=a["window_end"])
    store.audit(a["merchant_id"], "merchant", "modified", {"action_id": action_id, "budget": budget, "end_hour": end_hour,
                                                           "status": status})
    return store.get_action(action_id)


def approve(action_id: str, actor: str = "merchant") -> dict:
    a = store.get_action(action_id)
    if not a:
        raise ActionError("NOT_FOUND", "Yeh action nahi mila.", "Action not found.", 404)
    if a["status"] != "draft":
        raise ActionError("NO_PENDING_ACTION", "Yeh action pehle se chalu ya band hai.", f"Action is already {a['status']}.")
    if not a["policy"].get("passed"):
        raise ActionError("POLICY_BLOCKED", "Guardrail fail: yeh offer nahi chala sakte.", "A guardrail check failed.")
    adapter = get_adapter()
    m = a["merchant_id"]
    p = a["params"]
    seg = strategy.lapsed_segment(adapter, m, now().date())
    seg = seg[seg["opted_in"]].sort_values("payer_hash")         # consent: opted-in only, always
    hashes = seg["payer_hash"].tolist()[: p.get("n_target", len(seg))]
    rng = np.random.default_rng(zlib.crc32(action_id.encode()))
    arms = np.array(["treat", "holdout"] * (len(hashes) // 2 + 1))[: len(hashes)]
    rng.shuffle(arms)
    rows = [{"payer_hash": h, "arm": arm} for h, arm in zip(hashes, arms)]
    store.insert_targets(action_id, rows)
    store.audit(m, actor, "approved", {"action_id": action_id})
    treat = [r["payer_hash"] for r in rows if r["arm"] == "treat"]
    payload = {"merchant_id": m, "product_id": p.get("product_id", ""), "discount": int(p.get("discount", 0)),
               "valid_from": a["window_start"].isoformat(), "valid_to": a["window_end"].isoformat()}
    text = (f"Namaste! Aaj raat {p.get('end_hour', 22) % 12 or 12} baje tak Family combo par ₹{p.get('discount', 0)} off. "
            f"Aapka intezaar hai.")
    offer_id = None
    if n8n.webhook_url():
        n8n.send({"action_id": action_id, "offer": payload, "payer_hashes": treat, "text": text})
        store.audit(m, "agent", "sent_to_n8n", {"action_id": action_id})
    else:
        if a["kind"] != "winback_message":
            offer_id = mock_paytm.create_offer(payload)["offer_id"]
        mock_paytm.send_message({"merchant_id": m, "payer_hashes": treat, "template_id": a["kind"], "text": text})
    budget = int(p.get("budget_cap") or adapter.get_policy(m).get("daily_offer_budget", 300))
    store.update_action(action_id, status="live", params={**p, "offer_id": offer_id, "budget_cap": budget})
    return status_view(action_id)


def undo(action_id: str) -> dict:
    a = store.get_action(action_id)
    if not a:
        raise ActionError("NOT_FOUND", "Yeh action nahi mila.", "Action not found.", 404)
    if a["status"] not in ("live", "draft"):
        raise ActionError("NO_PENDING_ACTION", "Band karne ke liye kuch chalu nahi hai.", "Nothing live to stop.")
    if a["params"].get("offer_id"):
        mock_paytm.cancel_offer(a["merchant_id"], a["params"]["offer_id"])
    store.update_action(action_id, status="undone")
    store.audit(a["merchant_id"], "merchant", "undone", {"action_id": action_id})
    return {"id": action_id, "status": "undone"}


def status_view(action_id: str) -> dict:
    a = store.get_action(action_id)
    t = store.get_targets(action_id)
    return {"id": action_id, "status": a["status"], "n_treat": sum(x["arm"] == "treat" for x in t),
            "n_holdout": sum(x["arm"] == "holdout" for x in t),
            "budget_cap": int(a["params"].get("budget_cap") or 0), "ends_at": a["window_end"].isoformat(),
            "policy": a["policy"]}


def full_view(action_id: str) -> dict:
    a = store.get_action(action_id)
    if not a:
        raise ActionError("NOT_FOUND", "Yeh action nahi mila.", "Action not found.", 404)
    v = status_view(action_id)
    return {**{k: (x.isoformat() if isinstance(x, datetime) else x) for k, x in a.items()}, **v}


def _measure(a: dict, targets: list[dict]) -> dict:
    p = a["params"]
    price = p.get("price", 0)
    cost = p.get("cost", 0)
    margin = (price - cost) / price if price else 0.0
    return measure_mod.measure(targets, ticket=price, margin=margin, discount=p.get("discount", 0),
                               budget_cap=p.get("budget_cap"))


def run_simulation(action_id: str) -> dict:
    a = store.get_action(action_id)
    if not a:
        raise ActionError("NOT_FOUND", "Yeh action nahi mila.", "Action not found.", 404)
    if a["status"] not in ("live", "ended"):
        raise ActionError("NO_PENDING_ACTION", "Pehle offer chalu karein.", "Approve the action first.")
    res = simulate(action_id, [{"payer_hash": t["payer_hash"], "arm": t["arm"]} for t in store.get_targets(action_id)])
    store.set_target_results(action_id, res)
    store.update_action(action_id, status="ended")
    out = _measure(a, res)
    store.set_memory(a["merchant_id"], f"last_results.{a['kind']}", {**out, "action_id": action_id,
                                                                      "date": a["window_start"].date().isoformat()})
    store.audit(a["merchant_id"], "demo", "simulated", {"action_id": action_id, **out})
    return out


def measure(action_id: str) -> dict:
    a = store.get_action(action_id)
    if not a:
        raise ActionError("NOT_FOUND", "Yeh action nahi mila.", "Action not found.", 404)
    t = store.get_targets(action_id)
    if not t or all(x["returned"] is None for x in t):
        raise ActionError("NOT_FOUND", "Abhi result nahi aaya.", "No results yet.", 404)
    return _measure(a, t)
