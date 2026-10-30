"""Effect ranges with partial pooling between the shop and its peers (spec 8.4)."""
import warnings
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import context

K_POOL = 8
MIN_WINDOWS = 8
Z80 = 1.28


def window_sums(h: pd.DataFrame, h1: int, h2: int) -> pd.DataFrame:
    """merchant × date table of window revenue."""
    w = h[(h["hour"] >= h1) & (h["hour"] < h2)]
    return w.pivot_table(index="date", columns="merchant_id", values="revenue", aggfunc="sum")


def median_baseline(ws: pd.DataFrame) -> pd.DataFrame:
    """Median of the same window on the previous 8 same weekdays (rows are daily dates)."""
    full = ws.reindex(pd.date_range(ws.index.min(), ws.index.max()).date)
    lags = np.stack([full.shift(7 * k).to_numpy() for k in range(1, 9)])
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # the first weeks have no lags yet
        med = np.nanmedian(lags, axis=0)
    return pd.DataFrame(med, index=full.index, columns=full.columns)


def pooled(shop: list[float], peer: list[float], k: float = K_POOL) -> dict | None:
    ns, npr = len(shop), len(peer)
    if ns + npr < 3:  # one or two past windows can't give a range
        return None
    w = ns / (ns + k)
    ms = float(np.mean(shop)) if ns else 0.0
    mp = float(np.mean(peer)) if npr else ms
    vs = float(np.var(shop, ddof=1)) if ns >= 2 else None
    vp = float(np.var(peer, ddof=1)) if npr >= 2 else (vs or 0.0)
    mean = mp if ns == 0 else w * ms + (1 - w) * mp
    sd = np.sqrt(vp) if vs is None else np.sqrt(w * vs + (1 - w) * vp)
    return {"mean": float(100 * mean), "sd": float(100 * sd),
            "range": [round(float(100 * (mean - Z80 * sd)), 1), round(float(100 * (mean + Z80 * sd)), 1)],
            "basis": {"shop_n": ns, "peer_n": npr}}


def factor_ranges(adapter, merchant: dict, peers: list[str], d: date, h1: int, h2: int, factors: list[str],
                  include_shop: bool = True) -> dict[str, dict | None]:
    """For each factor: changes on past comparable windows (same weekday group, same hours, this factor
    flagged and no other), pooled shop + peers. basis.peer_n counts past windows, not peer-windows.

    ponytail: past windows are compared with the 8-week median baseline, not the app baseline, so pooling
    costs one SQL query instead of a forecast per past day; swap in the app baseline if ranges look biased.
    """
    ids = ([merchant["id"]] if include_shop else []) + peers
    start = d - timedelta(days=365)
    h = adapter.get_hourly(ids, start, d - timedelta(days=1))
    if h.empty:
        return {f: None for f in factors}
    ws = window_sums(h, h1, h2)
    change = (ws / median_baseline(ws).reindex(ws.index)) - 1
    m = adapter.list_merchants().set_index("id")
    group = (lambda x: x.weekday() >= 4) if d.weekday() >= 4 else (lambda x: x.weekday() < 4)
    fest = adapter.get_festivals(start - timedelta(days=15), d)
    out = {}
    flag_cache: dict = {}

    def flagset(mid: str) -> dict[str, set]:
        loc, cat, city = m.loc[mid, "locality_id"], m.loc[mid, "category"], m.loc[mid, "city"]
        key = (loc, cat, city)
        if key not in flag_cache:
            w = adapter.get_weather(loc, start, d - timedelta(days=1))
            flag_cache[key] = {"rain": context.rain_dates(w, h1, h2) if not w.empty else set(),
                               "festival": set(context.festival_hits(fest, cat)),
                               "disruption": set(adapter.get_disruptions(city, start, d)["date"])}
        return flag_cache[key]

    for f in factors:
        # windows where this factor (and no other) was on, per merchant
        hits = {}
        for mid in ws.columns:
            fl = flagset(mid)
            others = set().union(*[v for k, v in fl.items() if k != f])
            hits[mid] = {x for x in fl[f] if x not in others}
        # same weekday group if there are enough windows, else every weekday
        grouped = {mid: {x for x in v if group(x)} for mid, v in hits.items()}
        if len(set().union(*grouped.values())) >= MIN_WINDOWS:
            hits = grouped
        shop_s = []
        if include_shop and merchant["id"] in change:
            col = change[merchant["id"]]
            shop_s = [float(v) for x, v in col.items() if x in hits[merchant["id"]] and np.isfinite(v)]
        # peers: one sample per past window = median change across the peers it hit (market-level, low noise)
        peer_s = []
        for x in change.index:
            vals = [change.at[x, p] for p in peers if p in change and x in hits[p] and np.isfinite(change.at[x, p])]
            if len(vals) >= 3:
                peer_s.append(float(np.median(vals)))
        out[f] = pooled(shop_s, peer_s)
    return out
