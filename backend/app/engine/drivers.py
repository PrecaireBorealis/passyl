"""Shop-specific drivers: regulars, other customers, ticket size, payment failures (spec 8.5)."""
from datetime import date, timedelta

import numpy as np


def breakdown(adapter, merchant_id: str, d: date, h1: int, h2: int, market_pct: float, expected_p50: float,
              txn_level: bool = True) -> list[dict]:
    """Change vs the median of the same window over the last 8 same weekdays, with the market-wide part
    taken out of the customer counts. Usual counts are rescaled to the baseline's expected revenue so the
    contributions add up to roughly the shop-specific part of the Why card. Regulars / other customers need
    payer-level data (txn_level); ticket size and payment failures come from hourly totals."""
    days = [d - timedelta(days=7 * k) for k in range(0, 9)]
    h = adapter.get_hourly([merchant_id], days[-1], d)
    h = h[h["date"].isin(days) & (h["hour"] >= h1) & (h["hour"] < h2)]
    g = h.groupby("date")[["revenue", "txns", "success_txns", "regular_txns"]].sum()
    if d not in g.index or len(g) < 4:
        return []
    now, past = g.loc[d], g.drop(index=d)
    past = past[past["success_txns"] > 0]
    usual = past.median()
    usual_ticket = float((past["revenue"] / past["success_txns"]).median())
    if float(usual["revenue"]) <= 0 or expected_p50 <= 0:
        return []
    scale = expected_p50 / float(usual["revenue"])
    usual_rev = float(expected_p50)
    m = 1 + market_pct / 100
    reg_now, reg_usual = float(now["regular_txns"]), float(usual["regular_txns"]) * scale
    oth_now, oth_usual = float(now["success_txns"] - now["regular_txns"]), float(usual["success_txns"] - usual["regular_txns"]) * scale
    ticket_now = float(now["revenue"] / now["success_txns"]) if now["success_txns"] else usual_ticket
    fail_now = float(now["txns"] - now["success_txns"])
    fail_rate = fail_now / max(float(now["txns"]), 1)
    usual_fail_rate = float(((past["txns"] - past["success_txns"]) / past["txns"].clip(lower=1)).median())
    pts = lambda rupees: round(float(100 * rupees / usual_rev), 1)
    out = [] if not txn_level else [
        {"id": "regulars_missing" if reg_now < reg_usual * m else "regulars_up", "usual": int(round(reg_usual)),
         "actual": int(reg_now), "contribution_pts": pts((reg_now - reg_usual * m) * usual_ticket)},
        {"id": "other_customers", "usual": int(round(oth_usual)), "actual": int(oth_now),
         "contribution_pts": pts((oth_now - oth_usual * m) * usual_ticket)}]
    out += [
        {"id": "ticket_size", "usual": int(round(usual_ticket)), "actual": int(round(ticket_now)),
         "contribution_pts": pts((ticket_now - usual_ticket) * now["success_txns"])},
    ]
    if fail_now >= 3 and fail_rate > max(2 * usual_fail_rate, 0.08):
        out.append({"id": "payment_failures", "usual": int(round(usual_fail_rate * float(now["txns"]))),
                    "actual": int(fail_now), "contribution_pts": pts(-fail_now * usual_ticket)})
    return sorted(out, key=lambda x: x["contribution_pts"])
