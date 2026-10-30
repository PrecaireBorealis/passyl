"""Treated vs holdout, Wilson 80% intervals (spec 11.3)."""
import math

Z80 = 1.2816


def wilson(k: int, n: int, z: float = Z80) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def measure(targets: list[dict], ticket: float, margin: float, discount: float, budget_cap: float | None = None) -> dict:
    t = [x for x in targets if x["arm"] == "treat"]
    h = [x for x in targets if x["arm"] == "holdout"]
    rt, rh = sum(bool(x["returned"]) for x in t), sum(bool(x["returned"]) for x in h)
    nt, nh = len(t), len(h)
    rate_t, rate_h = (rt / nt if nt else 0.0), (rh / nh if nh else 0.0)
    inc_bills = nt * (rate_t - rate_h)
    # hard budget cap at execution: once it is spent, later returners pay full price
    redemptions = rt if not budget_cap or not discount else min(rt, int(budget_cap // discount))
    offer_cost = redemptions * discount
    inc_profit = inc_bills * ticket * margin - offer_cost
    ci_t, ci_h = wilson(rt, nt), wilson(rh, nh)
    overlap = ci_t[0] <= ci_h[1] and ci_h[0] <= ci_t[1]
    return {"n_treat": nt, "returned_treat": rt, "rate_treat": round(rate_t, 3), "rate_treat_ci": ci_t,
            "n_holdout": nh, "returned_holdout": rh, "rate_holdout": round(rate_h, 3), "rate_holdout_ci": ci_h,
            "incremental_bills": round(inc_bills, 1), "incremental_profit": int(round(inc_profit)),
            "offer_cost": int(round(offer_cost)), "redemptions": redemptions,
            "note_hi": "Chhota sample, abhi early signal hai." if overlap else
                       "Offer wale customers saaf taur par zyada laute."}
