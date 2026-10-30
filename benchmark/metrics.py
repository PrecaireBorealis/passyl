"""Scoring for the Shock-Injection Benchmark (spec 16.2)."""
import numpy as np

QUANTILES = (0.1, 0.5, 0.9)
# true shock kind → the engine's cause id that counts as correct
CAUSE = {"rain": "rain", "festival": "festival", "bandh": "disruption", "lapsed_regulars": "regulars_missing",
         "competitor_open": "shop_unexplained", "payment_outage": "payment_failures"}
MARKET_KINDS = {"rain", "festival", "bandh"}
FACTOR_OF = {"rain": "rain", "festival": "festival", "bandh": "disruption"}
DRIVER_MIN_PTS = 3.0
MIN_BILLS = 20        # same gate as the engine: too few bills → no cause
SHOP_SIG_PCT = 25.0   # a shop part this large is beyond normal window noise (tuned on seed 7)
FAIL_MIN_PTS = 5.0    # payment_failures only appears when failures are > 2× usual: specific evidence


PRIOR = {"disruption": 0, "festival": 1, "rain": 2}  # tie-break: the more severe kind of news first


def _pick_factor(flagged: list[dict], target: float, tol: float = 3.0) -> dict:
    """Rank: explains_market first; then a range that fits (±tol), then no range (unknown), then a range that
    clearly doesn't fit; then the more severe kind of news."""
    def fit(f):
        r = f.get("effect_range_pct")
        if not r:
            return 1
        return 0 if r[0] - tol <= target <= r[1] + tol else 2
    return min(flagged, key=lambda f: (f["status"] != "explains_market", fit(f), PRIOR.get(f["id"], 9)))


def top_cause(card: dict) -> str | None:
    """The engine's headline cause, or None when the change is within normal noise.

    Market cause: peers moved together (|median| ≥ 5% and the peer IQR excludes 0) → the flagged factor that
    best matches, else 'market_unexplained'. Shop cause: the shop is outside its own p10–p90 band → the top
    driver if it carries at least half of the shop part, else 'shop_unexplained'. With no peers the shop's
    total change is matched against drivers first, then flagged factors."""
    e, sp = card.get("expected"), card.get("split")
    if not e:
        return None
    ticket = next((x["usual"] for x in card.get("shop_drivers", []) if x["id"] == "ticket_size"), None)
    if ticket and e["p50"] / ticket < MIN_BILLS:
        return None  # low volume: the engine says the change is mostly noise
    band = card["actual"] < e["p10"] or card["actual"] > e["p90"]
    flagged = [f for f in card["factors"] if f["status"] != "none" and f["id"] != "unexplained_market"]

    def driver(part: float) -> str | None:
        drv = [x for x in card.get("shop_drivers", []) if np.sign(x["contribution_pts"]) == np.sign(part)
               and abs(x["contribution_pts"]) >= DRIVER_MIN_PTS and abs(x["contribution_pts"]) >= 0.5 * abs(part)]
        return max(drv, key=lambda x: abs(x["contribution_pts"]))["id"] if drv else None

    fail = any(x["id"] == "payment_failures" and x["contribution_pts"] <= -FAIL_MIN_PTS and x["actual"] >= 3 for x in card.get("shop_drivers", []))
    if sp:
        market, shop = sp["market_pct"], sp["shop_pct"]
        iqr = card["peer"].get("iqr_pct") or [0, 0]
        market_sig = abs(market) >= 5 and (iqr[0] > 0 or iqr[1] < 0)
        shop_sig = band or abs(shop) >= SHOP_SIG_PCT
        if fail and not (market_sig and abs(market) >= abs(shop)):
            return "payment_failures"
        if market_sig and (abs(market) >= abs(shop) or not shop_sig):
            return _pick_factor(flagged, market)["id"] if flagged else "market_unexplained"
        if shop_sig:
            return driver(shop) or "shop_unexplained"
        return None
    change = card.get("shop_change_pct") or 0.0
    if fail:
        return "payment_failures"
    if not (band or abs(change) >= SHOP_SIG_PCT):
        return None
    return driver(change) or (_pick_factor(flagged, change)["id"] if flagged else "shop_unexplained")


def pinball(y: float, q: float, tau: float) -> float:
    return max(tau * (y - q), (tau - 1) * (y - q))


def forecast(rows: list[dict]) -> dict:
    """rows: clean windows with actual, p10, p50, p90, holiday flag."""
    if not rows:
        return {}
    y = np.array([r["actual"] for r in rows], float)
    P = np.array([[r["p10"], r["p50"], r["p90"]] for r in rows], float)
    wape = float(np.abs(y - P[:, 1]).sum() / y.sum())
    loss = sum(pinball(yi, P[i, j], t) for i, yi in enumerate(y) for j, t in enumerate(QUANTILES))
    wql = float(2 * loss / (len(QUANTILES) * y.sum()))
    cov = float(np.mean((P[:, 0] <= y) & (y <= P[:, 2])))
    hol = [i for i, r in enumerate(rows) if r["holiday"]]
    hw = float(np.abs(y[hol] - P[hol, 1]).sum() / y[hol].sum()) if hol else None
    return {"wape_p50": round(wape, 4), "wql": round(wql, 4), "coverage_p10_p90": round(cov, 4),
            "holiday_wape": round(hw, 4) if hw is not None else None, "n_holiday_windows": len(hol)}


def engine(results: list[dict]) -> dict:
    """results: one per window with label kind, true effect, card, flagged, cause."""
    shocks = [r for r in results if r["kind"] not in ("none", "thin")]
    clean = [r for r in results if r["kind"] == "none"]
    thin = [r for r in results if r["kind"] == "thin"]
    det = [r for r in shocks if r["flagged"]]
    acc = [r for r in det if r["cause"] == CAUSE[r["kind"]]]
    split_err = [abs(r["card"]["split"]["market_pct"] - r["true_effect_pct"]) for r in shocks
                 if r["kind"] in MARKET_KINDS and r["card"].get("split")]
    cover = []
    for r in shocks:
        if r["kind"] in FACTOR_OF:
            f = next((x for x in r["card"]["factors"] if x["id"] == FACTOR_OF[r["kind"]] and "effect_range_pct" in x), None)
            if f:
                lo, hi = f["effect_range_pct"]
                cover.append(lo <= r["true_effect_pct"] <= hi)
    fa = [r for r in clean if r["flagged"] and r["cause"] is not None]
    by_kind = {}
    for k in sorted({r["kind"] for r in shocks}):
        rs = [r for r in shocks if r["kind"] == k]
        d = [r for r in rs if r["flagged"]]
        by_kind[k] = {"n": len(rs), "detection_rate": round(len(d) / len(rs), 3),
                      "cause_accuracy": round(sum(r["cause"] == CAUSE[k] for r in d) / len(d), 3) if d else None}
    rate = lambda a, b: round(len(a) / len(b), 4) if b else None
    return {"detection_rate": rate(det, shocks), "cause_accuracy": rate(acc, det),
            "split_mae_pts": round(float(np.mean(split_err)), 2) if split_err else None,
            "range_coverage": round(float(np.mean(cover)), 4) if cover else None, "n_ranges": len(cover),
            "false_alarm_rate": rate(fa, clean),
            "idk_rate": rate([r for r in thin if r["card"]["confidence"]["state"] == "thin_history"], thin),
            "by_kind": by_kind}
