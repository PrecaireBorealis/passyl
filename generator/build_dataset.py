"""Main entry: python -m generator.build_dataset --seed 42  → data/generated/seed_42/*.parquet"""
import argparse
import json
import time
import zlib

import numpy as np
import pandas as pd

from . import campaigns, customers, demand, merchants as merchants_mod, shocks
from .common import GEN, REF, load


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    t0 = time.time()
    world, effects, scen = load("world.yaml"), load("effects.yaml"), load("scenarios/raju_demo.yaml")
    rng = np.random.default_rng(args.seed)
    dates = pd.date_range(str(world["date_start"]), str(world["date_end"]), freq="D")
    D = len(dates)
    didx = {d: i for i, d in enumerate(dates)}

    mer = merchants_mod.build(world, effects, scen, rng)

    weather = pd.read_csv(REF / "weather_hourly.csv")
    ov = scen["weather_override"]
    wt = pd.to_datetime(weather["ts"].str[:16])
    for hh, mm in ov["hours"].items():
        sel = (weather["locality_id"] == ov["locality"]) & (wt == pd.Timestamp(f"{ov['date']} {hh:02d}:00"))
        weather.loc[sel, ["precip_mm", "source"]] = [float(mm), ov["label"]]
    wt = pd.to_datetime(weather["ts"].str[:16])
    precip = {}
    for loc, g in weather.assign(_d=wt.dt.normalize(), _h=wt.dt.hour).groupby("locality_id"):
        arr = np.zeros((D, 24))
        ok = g["_d"].isin(didx)
        arr[g.loc[ok, "_d"].map(didx).to_numpy(), g.loc[ok, "_h"].to_numpy()] = g.loc[ok, "precip_mm"].to_numpy()
        precip[loc] = arr

    fest = pd.read_csv(REF / "festivals.csv")
    fmult = demand.festival_mult(effects, fest, dates)
    shares = demand.hour_shares(effects)
    plan = shocks.plan(mer, dates, scen, rng)

    demo_id = scen["merchant"]["id"]
    lap_cfg = scen["lapsed_regulars"]
    hourly_parts, tx_parts, cust_parts, info = [], [], [], {}
    base_store, rain_store = {}, {}
    for _, m in mer.iterrows():
        # one stream per merchant: tuning one merchant's scenario never reshuffles the others
        rng = np.random.default_rng([args.seed, zlib.crc32(m["id"].encode())])
        base = demand.lam_parts(m, dates, effects, shares, fmult)
        rm = demand.rain_mult(m, precip[m["locality_id"]], effects)
        noise = rng.gamma(20, 1 / 20, base.shape)
        if m["locality_id"] == ov["locality"]:  # the scripted demo day is calmer than a random day
            k = scen.get("demo_day_noise_shape", 20)
            noise[-1] = rng.gamma(k, 1 / k, 24)
        lam = base * rm * shocks.mult(m, plan) * noise
        counts = rng.poisson(lam)
        if m["locality_id"] == ov["locality"] and scen.get("demo_day_counts") == "expected":
            counts[-1] = np.round(lam[-1])  # scripted day: no Poisson luck in a 2-hour demo window
        sp = np.full((D, 24), 0.985)
        o = plan["outage"].get(m["id"])
        if o:
            sp[o["day"], o["h1"]:o["h2"]] = 0.6
        base_store[m["id"]], rain_store[m["id"]] = base, rm
        if m["txn_level"]:
            lapse, pinned = None, None
            if m["id"] == demo_id:
                pinned = {"weekday": 4, "band": (18, 22), "n": lap_cfg["friday_evening_regulars"]}
                lapse = {"start": didx[pd.Timestamp(lap_cfg["lapse_start"])], "end": D,
                         "who": np.arange(lap_cfg["lapse_count"])}
            elif m["id"] in plan["lapsed"]:
                lapse = plan["lapsed"][m["id"]]
            tx, cust, inf = customers.simulate(m, counts, sp, dates, effects, rng, lapse, pinned)
            hourly_parts.append(customers.hourly_from_txns(tx, m["id"], D, dates))
            tx_parts.append(tx)
            cust_parts.append(cust)
            info[m["id"]] = inf
        else:
            succ = rng.binomial(counts, sp)
            mu, sig = effects["ticket_lognorm"][m["category"]]
            step = 5 if m["category"] in ("restaurant", "cafe") else 1
            flat = succ.ravel()
            tick = np.maximum(step, np.round(rng.lognormal(mu, sig, flat.sum()) / step) * step)
            rev = np.zeros(flat.size)
            nz = flat > 0
            rev[nz] = np.add.reduceat(tick, np.concatenate([[0], np.cumsum(flat[nz])[:-1]]))
            share = effects["customers"]["regular_share_of_txns"][m["category"]]
            h = pd.DataFrame({"merchant_id": m["id"], "date": np.repeat(dates.date, 24), "hour": np.tile(np.arange(24), D),
                              "revenue": rev.astype(int), "txns": counts.ravel(), "success_txns": flat,
                              "regular_txns": rng.binomial(flat, share), "new_txns": rng.binomial(flat, 0.08)})
            h["unique_payers"] = h["success_txns"] - rng.binomial(h["success_txns"], 0.03)
            hourly_parts.append(h)

    rng = np.random.default_rng([args.seed, 1])
    hourly = pd.concat(hourly_parts, ignore_index=True)
    hourly = hourly[hourly["date"] >= hourly["merchant_id"].map(mer.set_index("id")["opened_on"])]
    tx = pd.concat(tx_parts, ignore_index=True)
    cust = pd.concat(cust_parts, ignore_index=True)
    labels = build_labels(mer, dates, plan, precip, fmult, effects, base_store, rain_store, hourly, info, fest, scen, rng)

    out_dir = GEN / f"seed_{args.seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pol = pd.DataFrame({"merchant_id": mer["id"], "price_band_pct": 10.0, "margin_floor_pct": 20.0,
                        "daily_offer_budget": 300, "quiet_after_hour": 22, "autonomy_level": "L2",
                        "allow_price_changes": True})
    for k, v in scen.get("policy", {}).items():
        pol.loc[pol["merchant_id"] == demo_id, k] = v
    products = pd.DataFrame([{**p, "merchant_id": demo_id, "category": "combo"} for p in scen["products"]])
    out = {
        "localities": pd.read_csv(REF / "localities.csv"),
        "merchants": mer[["id", "name", "category", "locality_id", "lat", "lon", "opened_on", "language"]],
        "merchant_policy": pol, "products": products,
        "customers": cust, "transactions": tx.drop(columns=["_day", "_hour", "_payer"]), "hourly": hourly,
        "weather_hourly": weather, "festivals": fest, "disruptions": shocks.disruptions(plan),
        "past_campaigns": campaigns.build(mer, effects, rng), "shock_labels": labels,
    }
    for name, df in out.items():
        df.to_parquet(out_dir / f"{name}.parquet", index=False)
    (out_dir / "meta.json").write_text(json.dumps({"seed": args.seed, "built": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    print(f"seed {args.seed}: {len(mer)} merchants, {len(tx):,} transactions, {len(hourly):,} hourly rows, "
          f"{len(labels)} shock labels ({labels['kind'].value_counts().to_dict()}) in {time.time() - t0:.0f}s")
    targets_check(hourly, mer, tx, cust, scen)


def window_sum(arr: np.ndarray, d: int, h1: int, h2: int) -> float:
    return float(arr[d, h1:h2].sum())


def build_labels(mer, dates, plan, precip, fmult, effects, base, rain, hourly, info, fest, scen, rng) -> pd.DataFrame:
    rows = []
    didx = {d: i for i, d in enumerate(dates)}
    ev = [i for i, d in enumerate(dates) if shocks.EVAL_START <= d <= shocks.EVAL_END]
    shocked = set(plan["competitor"]) | set(plan["lapsed"]) | set(plan["outage"])
    demo = {scen["merchant"]["id"], scen["thin_history_merchant"]["id"]}
    opened = mer.set_index("id")["opened_on"]
    pick_pool = mer[~mer["id"].isin(shocked | demo)]

    def add(mid, city, d, h1, h2, kind, eff, scope):
        rows.append({"id": f"S_{len(rows):05d}", "merchant_id": mid, "city": city, "date": dates[d].date(),
                     "start_hour": h1, "end_hour": h2, "kind": kind, "true_effect_pct": round(100 * eff, 2),
                     "scope": scope})

    def pick(loc, cat, d):
        c = pick_pool[(pick_pool["locality_id"] == loc) & (pick_pool["category"] == cat)
                      & (pick_pool["opened_on"] <= (dates[d] - pd.Timedelta(days=120)).date())]
        return None if c.empty else c.iloc[int(rng.integers(len(c)))]

    # rain: every window with ≥2 rainy hours (≥1 mm/h) in the window or the hour before
    for loc, arr in precip.items():
        for d in ev:
            for h1, h2 in shocks.WINDOWS.values():
                if (arr[d, h1 - 1:h2] >= 1.0).sum() < 2:
                    continue
                for cat in ("restaurant", "cafe"):
                    ms = mer[(mer["locality_id"] == loc) & (mer["category"] == cat)]["id"]
                    effs = [window_sum(base[x] * rain[x], d, h1, h2) / max(window_sum(base[x], d, h1, h2), 1e-9) - 1
                            for x in ms if window_sum(base[x], d, h1, h2) > 0]
                    m = pick(loc, cat, d)
                    if m is not None and effs:
                        add(m["id"], m["city"], d, h1, h2, "rain", float(np.median(effs)), "locality")
    # festival: category-wide multipliers
    for cat in effects["festival_effects"]:
        if cat not in fmult:
            continue
        o, c = effects["open_hours"][cat]
        for d in ev:
            if fmult[cat][d] != 1.0:
                for loc in mer["locality_id"].unique():
                    m = pick(loc, cat, d)
                    if m is not None:
                        add(m["id"], m["city"], d, o, c, "festival", fmult[cat][d] - 1, "category")
    # bandh: city-wide, whole day
    for b in plan["bandh"]:
        d = didx[b["date"]]
        for loc in mer.loc[mer["city"] == b["city"], "locality_id"].unique():
            for cat in ("restaurant", "kirana"):
                m = pick(loc, cat, d)
                if m is not None:
                    o, c = effects["open_hours"][cat]
                    add(m["id"], m["city"], d, o, c, "bandh", -b["severity"], "city")
    city = mer.set_index("id")["city"]
    cat_of = mer.set_index("id")["category"]
    for mid, c in plan["competitor"].items():
        d = c["start"] + int(rng.integers(7, 21))
        add(mid, city[mid], d, 18, 22, "competitor_open", c["effect"], "merchant")
    rev = hourly.groupby(["merchant_id", "date"])["revenue"].sum()
    for mid, lp in plan["lapsed"].items():
        d = int(rng.integers(lp["start"] + 7, lp["end"]))
        o, c = effects["open_hours"][cat_of[mid]]
        lost = info[mid]["lost_by_day"][d]
        act = rev.get((mid, dates[d].date()), 0)
        add(mid, city[mid], d, o, c, "lapsed_regulars", -lost / max(act + lost, 1), "merchant")
    for mid, o in plan["outage"].items():
        add(mid, city[mid], o["day"], o["h1"], o["h2"], "payment_outage", 0.6 / 0.985 - 1, "merchant")
    # demo truth (outside the benchmark period; for the record)
    did = scen["merchant"]["id"]
    add(did, "Bengaluru", len(dates) - 1, 18, 22, "lapsed_regulars", float("nan"), "merchant")

    # clean windows: no rain, festival, holiday, bandh or merchant-level shock
    bandh = {(b["city"], b["date"]) for b in plan["bandh"]}
    n = 0
    while n < 300:
        m = pick_pool.iloc[int(rng.integers(len(pick_pool)))]
        d = int(rng.choice(ev))
        if m["opened_on"] > (dates[d] - pd.Timedelta(days=120)).date():
            continue
        o, c = effects["open_hours"][m["category"]]
        h1, h2 = [(12, 16), (18, 22), (o, c)][int(rng.integers(3))]
        # public holidays with no planted effect for this category stay eligible: they test holiday WAPE
        # and whether the engine wrongly blames the calendar
        near = [fmult[m["category"]][x] != 1.0 for x in (d - 1, d, d + 1) if 0 <= x < len(dates)]
        if ((precip[m["locality_id"]][d, max(h1 - 1, 0):h2] >= 0.5).any() or any(near)
                or (m["city"], dates[d]) in bandh):
            continue
        add(m["id"], m["city"], d, h1, h2, "none", 0.0, "merchant")
        n += 1
    return pd.DataFrame(rows)


def targets_check(hourly: pd.DataFrame, mer: pd.DataFrame, tx: pd.DataFrame, cust: pd.DataFrame, scen: dict) -> None:
    """Demo targets: evening drop of the demo merchant and its peers, vs the median of the last 8 Fridays."""
    demo_date = pd.Timestamp(scen["demo_date"]).date()
    now_h = pd.Timestamp(scen["demo_now"]).hour
    h1, h2 = 18, min(22, now_h)
    ev = hourly[(hourly["hour"] >= h1) & (hourly["hour"] < h2)].groupby(["merchant_id", "date"])["revenue"].sum()

    def change(mid):
        s = ev.loc[mid]
        past = [demo_date - pd.Timedelta(days=7 * k).to_pytimedelta() for k in range(1, 9)]
        normal = np.median([s.get(p, 0) for p in past])
        return 100 * (s.get(demo_date, 0) / normal - 1), s.get(demo_date, 0), normal

    did = scen["merchant"]["id"]
    m = mer.set_index("id")
    me = m.loc[did]
    peers = m[(m["category"] == me["category"]) & (m.index != did)]
    dist = np.hypot((peers["lat"] - me["lat"]) * 111, (peers["lon"] - me["lon"]) * 111 * np.cos(np.radians(me["lat"])))
    peers = peers[dist <= 2.0]
    shop, act, normal = change(did)
    peer = float(np.median([change(p)[0] for p in peers.index]))
    t = scen["targets_check"]
    ok = lambda v, r: "OK " if r[0] <= v <= r[1] else "OUT"
    print(f"targets_check (hours {h1}-{h2} on {demo_date}):")
    print(f"  {ok(shop, t['evening_drop_pct'])} demo merchant change {shop:+.1f}%  (₹{act:,.0f} vs normal ₹{normal:,.0f}; target {t['evening_drop_pct']})")
    print(f"  {ok(peer, t['peer_drop_pct'])} peer median change    {peer:+.1f}%  ({len(peers)} peers ≤2 km; target {t['peer_drop_pct']})")
    # offer segment: ≥3 visits in the 90 days before the last 21 days, none in the last 21
    t_m = tx[(tx["merchant_id"] == did) & (tx["status"] == "success")]
    day = pd.to_datetime(t_m["ts"]).dt.tz_localize(None).dt.normalize()
    end = pd.Timestamp(demo_date)
    recent = set(t_m.loc[day > end - pd.Timedelta(days=21), "payer_hash"])
    old = t_m[(day <= end - pd.Timedelta(days=21)) & (day > end - pd.Timedelta(days=111))]
    lapsed = set(old.groupby("payer_hash").size().loc[lambda s: s >= 3].index) - recent
    c = cust[cust["merchant_id"] == did].set_index("payer_hash")
    print(f"  lapsed customers {len(lapsed)}, opted-in {int(c.loc[list(lapsed), 'opted_in'].sum())} (expect ~60–100 opted-in)")
    fd = hourly[(hourly["merchant_id"] == did)]
    fri = fd[pd.to_datetime(fd["date"]).dt.day_of_week == 4].groupby("date")["revenue"].sum()
    print(f"  normal Friday revenue (median of last 8 before demo): ₹{fri.iloc[-9:-1].median():,.0f} (target ₹{scen['merchant']['base_daily_revenue_target']:,})")


if __name__ == "__main__":
    main()
