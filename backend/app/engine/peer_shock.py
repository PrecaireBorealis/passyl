"""Peer-Shock Test: split a change into market-wide (peers moved too) and shop-specific (spec 8.2)."""
from datetime import date, timedelta

import numpy as np

MIN_PEERS = 10


def find_peers(adapter, merchant_id: str, d: date) -> tuple[list[str], int]:
    """Same category, opened ≥ 8 weeks ago; grow the radius 2 → 5 km until there are ≥ 10."""
    for r in (2, 3, 4, 5):
        peers = adapter.list_peers(merchant_id, r, as_of=d)
        if len(peers) >= MIN_PEERS:
            return peers, r
    return peers, 5


def peer_changes(q: dict, actual: dict, peers: list[str], h1: int, h2: int) -> list[float]:
    out = []
    for p in peers:
        e = q[p][h1:h2, 1].sum()
        if e > 0:
            out.append(actual.get(p, 0) / e - 1)
    return out


def split(shop_change: float | None, changes: list[float]) -> dict:
    if len(changes) < MIN_PEERS:
        return {"state": "no_peers", "n": len(changes)}
    med = float(np.median(changes))
    q1, q3 = np.percentile(changes, [25, 75])
    res = {"state": "ok", "n": len(changes), "median_change_pct": round(100 * med, 1),
           "iqr_pct": [round(float(100 * q1), 1), round(float(100 * q3), 1)]}
    if shop_change is not None:
        res["market_pct"] = round(100 * med, 1)
        res["shop_pct"] = round(100 * shop_change - round(100 * med, 1), 1)
    return res


SC_DAYS = 120
SC_RIDGE = 1.0      # pull toward equal weights; 120 rows of ~1.0-scaled data
SC_MIN_R2 = 0.2     # below this the twin doesn't track the shop and we fall back to the peer median


def synthetic_control(adapter, merchant_id: str, peers: list[str], d: date, h1: int, h2: int) -> dict | None:
    """'Synthetic shop': non-negative peer weights fitted on the same hours of the last 120 days, ridge-pulled
    toward equal weights. The counterfactual for today is the weighted peers' actual sales today, so weekday,
    season and today's market shocks are in it without any baseline model.

    Returns {cf, shop_part (actual/cf − 1), r2, resid_sd, n_days, top_weights} or None if it can't be fitted."""
    from scipy.optimize import nnls
    h = adapter.get_hourly([merchant_id] + peers, d - timedelta(days=SC_DAYS), d)
    h = h[(h["hour"] >= h1) & (h["hour"] < h2)]
    ws = h.pivot_table(index="date", columns="merchant_id", values="revenue", aggfunc="sum").fillna(0)
    if d not in ws.index or merchant_id not in ws:
        return None
    today, past = ws.loc[d], ws.drop(index=d)
    cols = [p for p in peers if p in past and past[p].mean() > 0]
    past = past[(past[merchant_id] > 0)]
    if len(cols) < MIN_PEERS or len(past) < 30:
        return None
    ym, xm = past[merchant_id].mean(), past[cols].mean()
    y, X = (past[merchant_id] / ym).to_numpy(), (past[cols] / xm).to_numpy()
    P = len(cols)
    A = np.vstack([X, np.sqrt(SC_RIDGE) * np.eye(P)])
    b = np.concatenate([y, np.sqrt(SC_RIDGE) * np.full(P, 1.0 / P)])
    w, _ = nnls(A, b)
    fit = X @ w
    r2 = 1 - ((y - fit) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-9)
    cf = float(ym * (today[cols] / xm).to_numpy() @ w)
    if cf <= 0:
        return None
    top = sorted(zip(cols, w), key=lambda t: -t[1])[:3]
    return {"cf": cf, "shop_part": float(today[merchant_id] / cf - 1), "r2": float(r2),
            "resid_sd": float(np.std(y / np.maximum(fit, 1e-9) - 1)), "n_days": int(len(past)),
            "weights_top3_share": round(float(sum(x for _, x in top) / max(w.sum(), 1e-9)), 2)}
