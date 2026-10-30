"""Planted shocks for the benchmark (spec 7.6). Every shock gets a shock_labels row with its true effect."""
import numpy as np
import pandas as pd

EVAL_START = pd.Timestamp("2026-01-01")
EVAL_END = pd.Timestamp("2026-10-29")       # the demo date is never a benchmark window
WINDOWS = {"lunch": (12, 16), "evening": (18, 22)}


def plan(merchants: pd.DataFrame, dates: pd.DatetimeIndex, scen: dict, rng) -> dict:
    """Decide which shocks happen where. Effects on λ are applied by `mult`, labels by `labels`."""
    idx = {d: i for i, d in enumerate(dates)}
    ev = dates[(dates >= EVAL_START) & (dates <= EVAL_END)]
    weekdays = ev[ev.weekday < 5]
    demo = {scen["merchant"]["id"], scen["thin_history_merchant"]["id"]}
    # Merchant-level shocks never touch KOR restaurants/cafés: they are the demo merchant's peers.
    eligible = merchants[~merchants["id"].isin(demo)
                         & ~((merchants["locality_id"] == "KOR") & merchants["category"].isin(["restaurant", "cafe"]))
                         & (merchants["opened_on"] <= pd.Timestamp("2025-12-01").date())]

    bandh = []
    for city in merchants["city"].unique():
        for d in rng.choice(weekdays, 2, replace=False):
            bandh.append({"city": city, "date": pd.Timestamp(d), "severity": float(rng.uniform(0.4, 0.7))})

    rc = eligible[eligible["category"].isin(["restaurant", "cafe"])]
    competitor = {}
    for mid in rng.choice(rc["id"], 10, replace=False):
        start = pd.Timestamp(rng.choice(ev[(ev >= "2026-02-01") & (ev <= "2026-09-15")]))
        competitor[mid] = {"start": idx[start], "effect": float(-rng.uniform(0.08, 0.15))}

    lap_pool = eligible[eligible["txn_level"] & eligible["category"].isin(
        ["kirana", "sweet_shop", "pharmacy", "salon"])]
    lapsed = {}
    for mid in rng.choice(lap_pool["id"], 15, replace=False):
        start = pd.Timestamp(rng.choice(ev[(ev >= "2026-02-01") & (ev <= "2026-08-15")]))
        weeks = int(rng.integers(2, 7))
        lapsed[mid] = {"start": idx[start], "end": idx[start] + 7 * weeks, "fraction": float(rng.uniform(0.3, 0.45))}

    taken = set(competitor) | set(lapsed)
    outage = {}
    for mid in rng.choice(eligible.loc[~eligible["id"].isin(taken), "id"], 8, replace=False):
        d = pd.Timestamp(rng.choice(ev))
        h1 = int(rng.integers(11, 18))
        outage[mid] = {"day": idx[d], "h1": h1, "h2": h1 + int(rng.integers(2, 5))}

    return {"bandh": bandh, "competitor": competitor, "lapsed": lapsed, "outage": outage, "dates": dates}


def mult(m: pd.Series, p: dict) -> np.ndarray:
    """(D,24) λ multiplier from bandh and competitor shocks (lapse and outage act at transaction level)."""
    dates = p["dates"]
    out = np.ones((len(dates), 24))
    for b in p["bandh"]:
        if b["city"] == m["city"]:
            sev = 0.10 if m["category"] == "pharmacy" else b["severity"]
            out[dates.get_loc(b["date"])] *= 1 - sev
    c = p["competitor"].get(m["id"])
    if c:
        out[c["start"]:, 18:22] *= 1 + c["effect"]
    return out


def disruptions(p: dict) -> pd.DataFrame:
    return pd.DataFrame([{"city": b["city"], "date": b["date"].date(), "kind": "bandh",
                          "severity": round(b["severity"], 3), "source": "synthetic"} for b in p["bandh"]])
