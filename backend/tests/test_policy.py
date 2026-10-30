from datetime import date

from app.actions.executor import recompute
from app.engine.policy import check, shrink_then_block

POL = {"price_band_pct": 10, "margin_floor_pct": 20, "daily_offer_budget": 300, "quiet_after_hour": 22,
       "autonomy_level": "L2"}


def offer(cost=280, **kw):
    p = {"offer_price": 549, "mrp": 699, "price": 649, "cost": 290, "start_hour": 19, "end_hour": 22,
         "segment": "lapsed_opted_in", "n_target": 40, **kw}
    return {"kind": "combo_lapsed", "params": p, "expected_cost": cost,
            "expected": {"n_target": 40, "expected_cost": cost, "expected_profit": 900}}


def ids(res):
    return {c["id"]: c["passed"] for c in res["checks"]}


def test_price_above_mrp_blocked():
    r = check(offer(offer_price=749), POL, {})
    assert not r["passed"] and not ids(r)["mrp_cap"]


def test_budget_overflow_shrinks():
    a2, r = shrink_then_block(offer(cost=600), POL, {}, recompute)
    assert r["passed"] and r.get("shrunk") and a2["expected_cost"] <= 300 and a2["params"]["n_target"] < 40


def test_budget_overflow_blocks_when_shrinking_cannot_fix_it():
    _, r = shrink_then_block(offer(cost=600, offer_price=749), POL, {}, recompute)
    assert r.get("blocked")


def test_quiet_hours():
    assert not ids(check(offer(start_hour=23, end_hour=23), POL, {}))["quiet_hours"]


def test_non_opted_in_never_targeted():
    from app.adapters.synthetic import get_adapter
    from app.engine.strategy import lapsed_segment
    a = get_adapter()
    opted = lapsed_segment(a, "M_KOR_RES_001", date(2026, 10, 30)).query("opted_in")
    assert a.get_customers("M_KOR_RES_001", list(opted["payer_hash"]))["opted_in"].all()
