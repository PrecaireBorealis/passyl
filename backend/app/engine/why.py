"""Assembles the Why card (spec 8.6), plus the summary and hourly views that share its baseline."""
import time
from datetime import date, timedelta

import numpy as np

from ..clock import last_full_hour
from . import context, drivers, peer_shock, pooling
from .baseline import get_baseline, window_quantiles

THIN_DAYS = 42           # < 6 weeks of history → no shop-level baseline
MIN_BILLS = 20           # fewer expected bills in the window → a % change is mostly noise
MATCH_PTS = 3.0          # market part within the factor range ± 3 points → "explains_market"
DROP_PCT = -8.0
EVENING = (18, 22)
LABELS = {"rain": "Baarish", "festival": "Tyohaar", "disruption": "Bandh / strike"}


def _noop(*a, **k):
    pass


def _hour_hi(h: int) -> str:
    return f"{h % 12 or 12} baje"


def effective_window(d: date, h1: int, h2: int) -> tuple[int, int]:
    """If the date is today, only hours that are already over count."""
    h2 = min(h2, last_full_hour(d))
    if h2 <= h1:
        raise ValueError(f"window {h1}–{h2} has no completed hours yet")
    return h1, h2


def history_days(merchant: dict, d: date) -> int:
    return (d - merchant["opened_on"]).days


def window_actual(adapter, ids: list[str], d: date, h1: int, h2: int) -> dict[str, int]:
    h = adapter.get_hourly(ids, d, d)
    h = h[(h["hour"] >= h1) & (h["hour"] < h2)]
    return h.groupby("merchant_id")["revenue"].sum().astype(int).to_dict()


def explain_change(adapter, merchant_id: str, d: date, start_hour: int | None = None, end_hour: int | None = None,
                   baseline=None, trace=_noop) -> dict:
    m = adapter.get_merchant(merchant_id)
    if m is None:
        raise KeyError(merchant_id)
    h1, h2 = effective_window(d, start_hour if start_hour is not None else EVENING[0],
                              end_hour if end_hour is not None else EVENING[1])
    thin = history_days(m, d) < THIN_DAYS
    bl = baseline or get_baseline()

    t0 = time.perf_counter()
    peers, radius = peer_shock.find_peers(adapter, merchant_id, d)
    ids = ([] if thin else [merchant_id]) + peers
    q = bl.hourly(ids, d) if ids else {}
    actual = window_actual(adapter, [merchant_id] + peers, d, h1, h2)
    shop_actual = actual.get(merchant_id, 0)
    expected, shop_change = None, None
    if not thin:
        s = window_quantiles(q[merchant_id], h1, h2, bl.name)
        expected = {"p10": int(round(s[0])), "p50": int(round(s[1])), "p90": int(round(s[2]))}
        shop_change = shop_actual / expected["p50"] - 1 if expected["p50"] > 0 else None
    ms = int((time.perf_counter() - t0) * 1000)
    trace("baseline", ms, f"{bl.name}: " + (f"expected ₹{expected['p50']:,} for {h1}–{h2}" if expected
                                             else f"shop skipped (only {history_days(m, d)} days of history)"))

    t0 = time.perf_counter()
    sp = peer_shock.split(shop_change, peer_shock.peer_changes(q, actual, peers, h1, h2))
    trace("peer_shock", int((time.perf_counter() - t0) * 1000) + 1,
          f"{sp['n']} peers within {radius} km, median {sp['median_change_pct']:+.1f}%" if sp["state"] == "ok"
          else f"only {sp['n']} peers within 5 km")

    t0 = time.perf_counter()
    fl = context.flags(adapter, m, d, h1, h2)
    r = fl["rain"]
    trace("weather", int((time.perf_counter() - t0) * 1000) + 1,
          f"rain {r['hours'][0]}:00–{r['hours'][-1] + 1}:00, up to {r['max_mm']} mm/h" if r["on"] else "no rain in window")
    trace("calendar", 1, ", ".join(fl["festival"]["names"]) if fl["festival"]["on"] else "no festival")

    t0 = time.perf_counter()
    on = [f for f in ("rain", "festival", "disruption") if fl[f]["on"]]
    ranges = pooling.factor_ranges(adapter, m, peers, d, h1, h2, on, include_shop=not thin) if on else {}
    market = sp.get("median_change_pct")
    factors = []
    for f in ("rain", "festival", "disruption"):
        rg = ranges.get(f)
        if not fl[f]["on"]:
            evidence = {"rain": "Is waqt baarish nahi", "festival": "Aaj koi tyohaar nahi", "disruption": "Koi khabar nahi"}[f]
            factors.append({"id": f, "label_hi": LABELS[f], "evidence": evidence, "status": "none"})
            continue
        label = LABELS[f]
        if f == "rain":
            label += f" ({_hour_hi(r['first_hour'])} se)"
        elif f == "festival":
            label += f": {', '.join(fl['festival']['names'])}"
        evidence = (f"Peers within {radius} km {market:+.1f}% same hours" if market is not None
                    else "Aas-paas ke shops ka data kam hai")
        status = "partial"
        if rg and market is not None and rg["range"][0] - MATCH_PTS <= market <= rg["range"][1] + MATCH_PTS:
            status = "explains_market"
        item = {"id": f, "label_hi": label, "evidence": evidence, "status": status}
        if rg:
            item["effect_range_pct"] = rg["range"]
            item["basis"] = rg["basis"]
        factors.append(item)
    if market is not None and not on and abs(market) >= 5:
        factors.append({"id": "unexplained_market", "label_hi": "Poore area mein badlav",
                        "evidence": f"Peers within {radius} km {market:+.1f}%, koi wajah nahi mili", "status": "partial"})
    elif market is not None and on and all(x.get("status") != "explains_market" for x in factors if x["id"] in on) \
            and abs(market) >= 5:
        factors.append({"id": "unexplained_market", "label_hi": "Kuch aur bhi", "status": "partial",
                        "evidence": "Poore area par kuch aur bhi asar daal raha hai"})
    trace("pooling", int((time.perf_counter() - t0) * 1000) + 1,
          "; ".join(f"{f} {ranges[f]['range'][0]}% to {ranges[f]['range'][1]}%" for f in on if ranges.get(f)) or "no factor to range")

    shop_drivers = []
    if not thin and expected:
        t0 = time.perf_counter()
        shop_drivers = drivers.breakdown(adapter, merchant_id, d, h1, h2, market or 0.0, expected["p50"],
                                         txn_level=adapter.has_transactions(merchant_id))
        top = shop_drivers[0] if shop_drivers else None
        trace("drivers", int((time.perf_counter() - t0) * 1000) + 1,
              f"{top['id']}: {top['actual']} vs usual {top['usual']}" if top else "no transaction-level data")

    conf = {"state": "ok", "note": None}
    ticket = next((x["usual"] for x in shop_drivers if x["id"] == "ticket_size"), None)
    low_volume = bool(expected and ticket and expected["p50"] / ticket < MIN_BILLS)
    if thin:
        conf = {"state": "thin_history", "note": f"Sirf {history_days(m, d)} din ka data hai; abhi apna normal nahi bana. "
                                                  f"Aas-paas ki similar dukaanon ka range dikha rahe hain."}
    elif sp["state"] == "no_peers":
        conf = {"state": "no_peers", "note": "5 km mein 10 similar dukaanein nahi mili; market vs dukaan ka split nahi kar sakte."}
    elif low_volume:
        conf = {"state": "wide", "note": f"Is waqt aam taur par sirf ~{int(expected['p50'] / ticket)} bills hote hain; "
                                         f"itne kam bills mein badlav zyada tar shor hai."}
    else:
        main = next((ranges[f] for f in on if ranges.get(f)), None)
        if main and (sum(main["basis"].values()) < 8 or main["range"][1] - main["range"][0] > 20):
            conf = {"state": "wide", "note": "Andaaza kam pakka hai: range chauda hai."}

    return {
        "merchant_id": merchant_id, "date": d.isoformat(), "window": {"start_hour": h1, "end_hour": h2},
        "actual": int(shop_actual), "expected": expected, "baseline_model": bl.name,
        "shop_change_pct": round(100 * shop_change, 1) if shop_change is not None else None,
        "peer": {"n": sp["n"], "radius_km": radius, "median_change_pct": sp.get("median_change_pct"),
                 "iqr_pct": sp.get("iqr_pct")},
        "split": {"market_pct": sp["market_pct"], "shop_pct": sp["shop_pct"]} if "market_pct" in sp else None,
        "factors": factors, "shop_drivers": shop_drivers, "confidence": conf, "data_label": "synthetic",
    }


def is_flagged(card: dict) -> bool:
    """Drop (or spike) detection: actual outside p10–p90, or shop change beyond ±8%."""
    e, c = card["expected"], card["shop_change_pct"]
    if e is None or c is None:
        return False
    return card["actual"] < e["p10"] or card["actual"] > e["p90"] or abs(c) >= -DROP_PCT


def _past_same_weekdays(adapter, merchant_id: str, d: date, n: int = 8):
    days = [d - timedelta(days=7 * k) for k in range(1, n + 1)]
    h = adapter.get_hourly([merchant_id], days[-1], days[0])
    return h[h["date"].isin(days)]


def hourly_view(adapter, merchant_id: str, d: date, baseline=None) -> dict:
    m = adapter.get_merchant(merchant_id)
    hmax = last_full_hour(d)
    today = adapter.get_hourly([merchant_id], d, d).set_index("hour")["revenue"]
    q = None
    if history_days(m, d) >= THIN_DAYS:
        q = (baseline or get_baseline()).hourly([merchant_id], d)[merchant_id]
    past = _past_same_weekdays(adapter, merchant_id, d)
    open_h = sorted(set(past.loc[past["revenue"] > 0, "hour"]) | set(today[today > 0].index))
    hours = []
    for h in open_h:
        row = {"hour": int(h), "today": int(today.get(h, 0)) if h < hmax else None,
               "normal_p50": None, "normal_p10": None, "normal_p90": None}
        if q is not None:
            row.update(normal_p10=int(round(q[h, 0])), normal_p50=int(round(q[h, 1])), normal_p90=int(round(q[h, 2])))
        hours.append(row)
    return {"hours": hours}


def summary(adapter, merchant_id: str, d: date, baseline=None, full_day: bool = False) -> dict:
    m = adapter.get_merchant(merchant_id)
    hmax = 24 if full_day else last_full_hour(d)
    t = adapter.get_hourly([merchant_id], d, d)
    t = t[t["hour"] < hmax]
    past = _past_same_weekdays(adapter, merchant_id, d)
    past = past[past["hour"] < hmax].groupby("date")[["revenue", "success_txns", "regular_txns"]].sum()
    rev, bills, reg = int(t["revenue"].sum()), int(t["success_txns"].sum()), int(t["regular_txns"].sum())
    out = {"date": d.isoformat(), "revenue_today": rev, "revenue_normal": None, "change_pct": None, "bills": bills,
           "bills_change_pct": None, "regular_share": round(reg / bills, 3) if bills else None,
           "regular_share_usual": None, "alert": None, "data_label": "synthetic"}
    if not past.empty:
        nb = float(past["success_txns"].median())
        out["bills_change_pct"] = round(100 * (bills / nb - 1), 1) if nb else None
        out["regular_share_usual"] = round(float((past["regular_txns"] / past["success_txns"].clip(lower=1)).median()), 3)
    if history_days(m, d) < THIN_DAYS:
        return out
    bl = baseline or get_baseline()
    q = bl.hourly([merchant_id], d)[merchant_id]
    normal = int(round(q[:hmax, 1].sum()))
    out["revenue_normal"] = normal
    out["change_pct"] = round(100 * (rev / normal - 1), 1) if normal else None
    try:
        h1, h2 = EVENING if full_day else effective_window(d, *EVENING)
        e = window_quantiles(q, h1, h2, bl.name)
        a = int(t.loc[(t["hour"] >= h1) & (t["hour"] < h2), "revenue"].sum())
        ch = 100 * (a / e[1] - 1) if e[1] else 0
        if a < e[0] or ch <= DROP_PCT:
            out["alert"] = {"window": {"start_hour": h1, "end_hour": h2}, "change_pct": round(float(ch), 1)}
    except ValueError:
        pass
    return out
