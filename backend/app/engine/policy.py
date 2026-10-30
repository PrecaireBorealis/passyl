"""Guardrails: a pure function over an action, the merchant policy and context (spec 10)."""

AUTO_COST_SHARE = 0.5


def check(action: dict, pol: dict, ctx: dict) -> dict:
    p = action.get("params", {})
    checks = []

    def add(cid: str, ok: bool, detail: str):
        checks.append({"id": cid, "passed": bool(ok), "detail_hi": detail})

    offer_price, mrp, cost = p.get("offer_price"), p.get("mrp"), p.get("cost")
    if offer_price is not None and mrp is not None:
        add("mrp_cap", offer_price <= mrp, f"Offer price ₹{offer_price}, MRP ₹{mrp} se upar nahi")
    if offer_price is not None and p.get("price"):
        change = 100 * (offer_price - p["price"]) / p["price"]
        band = pol.get("price_band_pct", 10)
        # a discount offer is a temporary promotion; only price increases are bound by the band
        add("price_band", change <= band, f"Daam {change:+.0f}% (band ±{band:.0f}%, sirf badhane par)")
    if offer_price is not None and cost is not None:
        margin = 100 * (offer_price - cost) / offer_price
        add("margin_floor", margin >= pol.get("margin_floor_pct", 20),
            f"Margin {margin:.0f}% (kam se kam {pol.get('margin_floor_pct', 20):.0f}%)")
    budget = pol.get("daily_offer_budget", 300)
    add("budget", action.get("expected_cost", 0) <= budget,
        f"Andaazan kharcha ₹{action.get('expected_cost', 0)}, budget ₹{budget}")
    if p.get("segment") in ("lapsed_opted_in", "opted_in_regulars"):
        add("consent", True, "Sirf opt-in customers ko message")
    if p.get("start_hour") is not None:
        quiet = pol.get("quiet_after_hour", 22)
        ok = 9 <= p["start_hour"] < quiet and p.get("end_hour", quiet) <= quiet
        add("quiet_hours", ok, f"Message {p['start_hour']}:00 par, {quiet}:00 ke baad nahi")
    level = pol.get("autonomy_level", "L2")
    if level == "L1":
        add("autonomy", False, "L1: sirf salah, khud kuch nahi karenge")
    elif level == "L3":
        auto = action.get("expected_cost", 0) <= AUTO_COST_SHARE * budget
        add("autonomy", True, "L3: policy ke andar auto" if auto else "L3: kharcha zyada, aapki manzoori chahiye")
    else:
        add("autonomy", True, "L2: aapke 'haan' ke baad hi chalega")
    if action.get("kind") in ("refund", "dispute", "fraud"):
        add("escalate", False, "Refund / dispute / fraud: insaan dekhega")
    return {"passed": all(c["passed"] for c in checks), "checks": checks}


def shrink_then_block(action: dict, pol: dict, ctx: dict, recompute) -> tuple[dict, dict]:
    """If a check fails: shrink the target segment once (recompute(action, factor) → new action), re-check;
    still failing → blocked."""
    res = check(action, pol, ctx)
    if res["passed"]:
        return action, res
    failed = {c["id"] for c in res["checks"] if not c["passed"]}
    if failed <= {"budget"}:
        budget = pol.get("daily_offer_budget", 300)
        factor = budget / max(action.get("expected_cost", 1), 1) * 0.95
        smaller = recompute(action, factor)
        res2 = check(smaller, pol, ctx)
        if res2["passed"]:
            res2["shrunk"] = True
            return smaller, res2
        res = res2
    res["blocked"] = True
    return action, res
