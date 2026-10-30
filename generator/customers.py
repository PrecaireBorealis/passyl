"""Payer-level transactions for txn-level localities: regulars, Zipf walk-ins, natural churn, lapses."""
import hashlib

import numpy as np
import pandas as pd


def _hash(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def simulate(m: pd.Series, counts: np.ndarray, success_p: np.ndarray, dates: pd.DatetimeIndex,
             effects: dict, rng, lapse: dict | None = None, pinned: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """counts: (D,24) attempted txns from λ. Returns (transactions, customers, info).

    lapse = {"start": day_idx, "end": day_idx, "who": regular indices or None, "fraction": f}
    pinned = {"weekday": 4, "band": (18, 22), "n": 30}: force n regulars to prefer that slot (demo).
    Lapsed regulars' visits are dropped (lost revenue), not refilled.
    """
    cat, mid = m["category"], m["id"]
    # one child stream per array: txns are ordered by day, so changing the last (demo) day leaves
    # every earlier day's draws untouched and the scenario can be tuned without reshuffling history
    g_setup, g_reg, g_slot, g_zipf, g_lapse, g_amt, g_ok, g_min, g_opt = rng.spawn(9)
    cc = effects["customers"]
    pool = cc["pool_size"][cat]
    n_reg = max(5, int(round(pool * cc["regulars_fraction_of_pool"])))
    n_non = pool - n_reg
    share = cc["regular_share_of_txns"][cat]
    o, c = effects["open_hours"][cat]
    hw = np.array(effects["hour_profile"][cat], float)
    hw[:o] = 0
    hw[c:] = 0
    dw = np.array(effects["dow_profile"][cat])

    # regulars: a preferred weekday and hour band
    pref_wd = g_setup.choice(7, n_reg, p=dw / dw.sum())
    pref_h = g_setup.choice(24, n_reg, p=hw / hw.sum())
    if pinned:
        k = pinned["n"]
        pref_wd[:k] = pinned["weekday"]
        pref_h[:k] = g_setup.integers(pinned["band"][0], pinned["band"][1], k)
    # slot weight: strong on the preferred weekday ±2 h, weak elsewhere
    wd_grid, h_grid = np.arange(7)[:, None, None], np.arange(24)[None, :, None]
    slot_w = np.where((pref_wd[None, None, :] == wd_grid) & (np.abs(pref_h[None, None, :] - h_grid) <= 2), 1.0, 0.03)
    slot_cum = np.cumsum(slot_w / slot_w.sum(axis=2, keepdims=True), axis=2)  # (7,24,R)

    # non-regulars: Zipf-like propensity; a share of the frequent ones churn away (natural churn)
    zipf = 1.0 / (np.arange(1, n_non + 1) + 300.0)   # Zipf-like with an offset: busiest walk-in ≈ 3 visits/month
    zcum = np.cumsum(zipf / zipf.sum())
    end_day = np.full(n_non, len(dates))
    top = np.arange(min(400, n_non))
    churners = g_setup.choice(top, int(len(top) * cc["churn_fraction"]), replace=False)
    end_day[churners] = g_setup.integers(len(dates) - 150, len(dates) - 22, len(churners))

    D = len(dates)
    day_i, hour_i = np.nonzero(counts)
    n_per = counts[day_i, hour_i]
    d = np.repeat(day_i, n_per)
    h = np.repeat(hour_i, n_per)
    T = len(d)
    wd = dates.weekday.values[d]
    is_reg = g_reg.random(T) < share
    payer = np.empty(T, dtype=np.int64)              # regulars 0..R-1, non-regulars R.., walk-ins ≥ pool
    r_ix = np.nonzero(is_reg)[0]
    u = g_slot.random(len(r_ix))
    cum = slot_cum[wd[r_ix], h[r_ix]]
    payer[r_ix] = (cum < u[:, None]).sum(axis=1)
    n_ix = np.nonzero(~is_reg)[0]
    pick = np.minimum(np.searchsorted(zcum, g_zipf.random(len(n_ix))), n_non - 1)
    gone = (d[n_ix] >= end_day[pick]) | (g_zipf.random(len(n_ix)) < cc["walkin_share"])  # churned or one-off → walk-in
    payer[n_ix] = n_reg + pick
    payer[n_ix[gone]] = pool + np.arange(gone.sum())

    keep = np.ones(T, bool)
    lapsed_who = np.array([], int)
    if lapse:
        lapsed_who = lapse.get("who")
        if lapsed_who is None:
            lapsed_who = g_lapse.choice(n_reg, int(round(n_reg * lapse["fraction"])), replace=False)
        hit = is_reg & np.isin(payer, lapsed_who) & (d >= lapse["start"]) & (d < lapse.get("end", D))
        keep &= ~hit
    mu, sig = effects["ticket_lognorm"][cat]
    step = 5 if cat in ("restaurant", "cafe") else 1
    amount = np.maximum(step, np.round(g_amt.lognormal(mu, sig, T) / step) * step).astype(int)
    ok = g_ok.random(T) < success_p[d, h]
    lost = int(amount[~keep & ok].sum())
    lost_by_day = np.bincount(d[~keep & ok], weights=amount[~keep & ok], minlength=D)

    d, h, payer, amount, ok = d[keep], h[keep], payer[keep], amount[keep], ok[keep]
    minute = g_min.integers(0, 60, len(d))
    ts = (dates.values[d] + (h * 60 + minute).astype("timedelta64[m]"))
    order = np.argsort(ts, kind="stable")
    d, h, payer, amount, ok, ts = d[order], h[order], payer[order], amount[order], ok[order], ts[order]

    uniq = np.unique(payer)
    names = {p: _hash(f"P_{mid}_{p}" if p < pool else f"P_{mid}_w{p - pool}") for p in uniq}
    ph = np.array([names[p] for p in payer])
    tx = pd.DataFrame({"txn_id": [f"T_{mid}_{i:07d}" for i in range(len(d))], "merchant_id": mid,
                       "ts": pd.to_datetime(ts).tz_localize("Asia/Kolkata"), "amount": amount, "payer_hash": ph,
                       "status": np.where(ok, "success", "failed"), "product_id": None,
                       "_day": d, "_hour": h, "_payer": payer})
    first = tx.groupby("_payer")["ts"].min()
    opted = g_opt.random(len(uniq)) < effects["customers"]["opt_in_rate"]
    cust = pd.DataFrame({"payer_hash": [names[p] for p in uniq], "merchant_id": mid,
                         "first_seen": first.loc[uniq].dt.date.values, "is_regular": uniq < n_reg,
                         "opted_in": opted})
    info = {"lost_revenue": lost, "lost_by_day": lost_by_day, "n_regulars": n_reg, "lapsed_who": lapsed_who}
    return tx, cust, info


def hourly_from_txns(tx: pd.DataFrame, mid: str, D: int, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Hourly aggregates on a full 24-hour grid. regular = ≥4 visits in the previous 56 days (spec 8.5)."""
    succ = tx[tx["status"] == "success"]
    p, day = succ["_payer"].to_numpy(), succ["_day"].to_numpy()
    key = p * 100000 + day
    sk = np.sort(key)
    prior = np.searchsorted(sk, key, "left") - np.searchsorted(sk, p * 100000 + day - 56, "left")
    first_day = succ.groupby("_payer")["_day"].transform("min").to_numpy()
    s = succ.assign(_reg=prior >= 4, _new=day == first_day)
    g = s.groupby(["_day", "_hour"])
    agg = pd.DataFrame({"revenue": g["amount"].sum(), "success_txns": g.size(), "regular_txns": g["_reg"].sum(),
                        "new_txns": g["_new"].sum(), "unique_payers": g["_payer"].nunique()})
    full = pd.MultiIndex.from_product([range(D), range(24)], names=["_day", "_hour"])
    agg = agg.reindex(full).fillna(0)
    agg["txns"] = tx.groupby(["_day", "_hour"]).size().reindex(full).fillna(0)
    agg = agg.astype(int).reset_index()
    agg.insert(0, "merchant_id", mid)
    agg.insert(1, "date", dates.date[agg["_day"]])
    return agg.rename(columns={"_hour": "hour"}).drop(columns="_day")
