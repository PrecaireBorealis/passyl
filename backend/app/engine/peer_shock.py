"""Peer-Shock Test: split a change into market-wide (peers moved too) and shop-specific (spec 8.2)."""
from datetime import date

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

