"""Playbook + expected incremental profit, uplift pooled over past campaigns (spec 9)."""
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd
import yaml

from ..config import EFFECTS, SCENARIO
from . import policy
from .baseline import get_baseline

K_UPLIFT = 5
LAPSE_RECENT_DAYS = 21
LAPSE_BEFORE_DAYS = 90


@lru_cache(maxsize=1)
def priors() -> dict:
    return yaml.safe_load(EFFECTS.read_text())["priors"]


@lru_cache(maxsize=1)
def offer_config() -> dict:
    """Which product the combo offer uses and its ₹ discount (merchant setup, not campaign truth)."""
    s = yaml.safe_load(SCENARIO.read_text())
    return {s["merchant"]["id"]: s["offer"]}


def lapsed_segment(adapter, merchant_id: str, d: date) -> pd.DataFrame:
    """≥ 3 visits in the 90 days before the last 21 days, and none in the last 21 days (spec 8.5)."""
    end = pd.Timestamp(d, tz="Asia/Kolkata")
    tx = adapter.get_transactions(merchant_id, (end - pd.Timedelta(days=LAPSE_RECENT_DAYS + LAPSE_BEFORE_DAYS)).to_pydatetime(),
                                  end.to_pydatetime())
    tx = tx[tx["status"] == "success"]
    if tx.empty:
        return pd.DataFrame(columns=["payer_hash", "opted_in", "visits"])
    recent_cut = end - pd.Timedelta(days=LAPSE_RECENT_DAYS)
    recent = set(tx.loc[tx["ts"] >= recent_cut, "payer_hash"])
    old = tx[tx["ts"] < recent_cut].groupby("payer_hash").size()
    seg = old[(old >= 3) & ~old.index.isin(recent)]
    cust = adapter.get_customers(merchant_id, list(seg.index)).set_index("payer_hash")
    return pd.DataFrame({"payer_hash": seg.index, "visits": seg.values,
                         "opted_in": cust.reindex(seg.index)["opted_in"].fillna(False).astype(bool).values})


def uplift(adapter, merchant: dict, kind: str) -> dict:
    """Partial pooling (k = 5): merchant's own campaigns → same category in the city → global; priors if < 5."""
    pc = adapter.get_past_campaigns()
    pc = pc[pc["kind"] == kind]
    own = pc[pc["merchant_id"] == merchant["id"]]
    local = pc[(pc["category"] == merchant["category"]) & (pc["city"] == merchant["city"])]
    pri = priors()[kind]
    if len(own) + len(local) + len(pc) < 5:
        return {"p_t": pri["p_t"], "p_c": pri["p_c"], "source": "default", "n_campaigns": 0}
    glob_t, glob_c = float(pc["treat_rate"].mean()), float(pc["hold_rate"].mean())
    # local level shrinks to global, own level shrinks to local
    wl = len(local) / (len(local) + K_UPLIFT)
    lt = wl * float(local["treat_rate"].mean()) + (1 - wl) * glob_t if len(local) else glob_t
    lc = wl * float(local["hold_rate"].mean()) + (1 - wl) * glob_c if len(local) else glob_c
    wo = len(own) / (len(own) + K_UPLIFT)
    pt = wo * float(own["treat_rate"].mean()) + (1 - wo) * lt if len(own) else lt
    pcr = wo * float(own["hold_rate"].mean()) + (1 - wo) * lc if len(own) else lc
    source = "your past campaigns" if len(own) >= 5 else "similar shops" if len(local) >= 5 else "all shops"
    ref = own if len(own) >= 5 else local if len(local) >= 5 else pc
    # how much the rates vary from shop to shop: the uncertainty for *this* shop
    sd_t, sd_c = float(ref["treat_rate"].std(ddof=1)), float(ref["hold_rate"].std(ddof=1))
    return {"p_t": round(pt, 3), "p_c": round(pcr, 3), "source": source, "n_campaigns": int(len(own) + len(local)),
            "sd_t": round(sd_t, 3), "sd_c": round(sd_c, 3)}


MC_DRAWS = 4000


def profit_risk(n_treat: int, u: dict, ticket: float, margin: float, discount: float, seed: int = 0) -> dict:
    """Monte Carlo of realised profit: return rates drawn from the across-shop spread, then binomial luck in a
    segment of n_treat customers. Returns P(profit > 0) and the 80% range."""
    rng = np.random.default_rng(seed)
    pt = np.clip(rng.normal(u["p_t"], u.get("sd_t", 0.05), MC_DRAWS), 0, 1)
    pc = np.clip(rng.normal(u["p_c"], u.get("sd_c", 0.03), MC_DRAWS), 0, 1)
    came = rng.binomial(n_treat, pt)                 # offered customers who return (all redeem)
    would = rng.binomial(n_treat, pc)                # of them, how many would have come anyway
    profit = (came - would) * (ticket * margin - discount) - would * discount
    lo, hi = np.percentile(profit, [10, 90])
    return {"p_profit_positive": round(float((profit > 0).mean()), 2), "profit_p10": int(lo), "profit_p90": int(hi)}


def gross_margin(merchant: dict, product: dict | None) -> float:
    if product:
        return (product["price"] - product["cost"]) / product["price"]
    return priors()["gross_margin"][merchant["category"]]


def offer_window(d: date) -> tuple[int, int]:
    """7–10 PM; if the evening has already started, from now."""
    from ..clock import now, today
    start = max(19, now().hour) if d == today() else 19
    return min(start, 21), 22


def rank(adapter, merchant_id: str, d: date, why: dict | None = None, window: tuple[int, int] | None = None) -> dict:
    window = window or offer_window(d)
    m = adapter.get_merchant(merchant_id)
    pol = adapter.get_policy(merchant_id)
    offer = offer_config().get(merchant_id)
    products = {p["id"]: p for p in adapter.get_products(merchant_id)}
    product = products.get(offer["product_id"]) if offer else None
    top_driver = (why or {}).get("shop_drivers", [{}])[0].get("id") if (why or {}).get("shop_drivers") else None
    options = []

    # 1. combo for lapsed regulars
    seg = lapsed_segment(adapter, merchant_id, d)
    opted = seg[seg["opted_in"]]
    if product and offer and len(opted) >= 4:
        u = uplift(adapter, m, "combo_lapsed")
        c = offer["discount"]
        T, g = product["price"], gross_margin(m, product)
        n_treat = len(opted) // 2
        profit = n_treat * ((u["p_t"] - u["p_c"]) * (T * g - c) - u["p_c"] * c)
        cost = n_treat * u["p_t"] * c
        options.append({
            "id": "combo_lapsed", "kind": "combo_lapsed",
            "title_hi": f"{product['name']} offer: purane regular customers ke liye",
            "description_hi": f"{window[0] % 12 or 12} se {window[1] % 12 or 12} baje tak {product['name']} par ₹{c} off, "
                              f"sirf un {len(opted)} customers ko jo pehle aate the aur 3 hafte se nahi aaye (opt-in).",
            "expected_profit": int(round(profit)), "expected_cost": int(round(cost)), "n_target": int(len(opted)),
            "assumptions": {"p_t": u["p_t"], "p_c": u["p_c"], "source": u["source"], "ticket": T,
                            "gross_margin": round(g, 3), "discount": c, "n_treat": n_treat,
                            "n_holdout": int(len(opted) - n_treat), **profit_risk(n_treat, u, T, g, c)},
            "params": {"product_id": product["id"], "discount": c, "price": T, "mrp": product["mrp"],
                       "cost": product["cost"], "offer_price": T - c, "start_hour": window[0], "end_hour": window[1],
                       "segment": "lapsed_opted_in", "n_target": int(len(opted))},
            "relevant": top_driver in (None, "regulars_missing"),
        })

    # 2. flat discount on all bills in the window (always shown as the comparison)
    d_pct = 0.20
    bl = get_baseline()
    q = bl.hourly([merchant_id], d)[merchant_id] if (d - m["opened_on"]).days >= 42 else None
    if q is not None:
        past = adapter.get_hourly([merchant_id], d - timedelta(days=56), d - timedelta(days=1))
        past = past[(past["hour"] >= window[0]) & (past["hour"] < window[1])]
        T = float(past["revenue"].sum() / max(past["success_txns"].sum(), 1))
        B = float(q[window[0]:window[1], 1].sum() / T) if T else 0.0
        g = gross_margin(m, None)
        e = priors()["flat_discount_uplift_per_d"] * d_pct
        profit = B * e * T * (g - d_pct) - B * T * d_pct
        options.append({
            "id": "flat_discount", "kind": "flat_discount", "title_hi": "Sab bills par 20% off",
            "description_hi": f"{window[0] % 12 or 12} se {window[1] % 12 or 12} baje tak har bill par 20% chhoot, sabke liye.",
            "expected_profit": int(round(profit)), "expected_cost": int(round(B * (1 + e) * T * d_pct)),
            "n_target": int(round(B)),
            "assumptions": {"discount_pct": 20, "expected_bills": round(B, 1), "uplift": round(e, 3), "ticket": round(T),
                            "gross_margin": g, "source": "default"},
            "params": {"discount_pct": 20, "start_hour": window[0], "end_hour": window[1], "segment": "everyone"},
            "relevant": True,
        })

    # 3. message only (cheap fallback, no discount)
    if len(opted) >= 4:
        u = uplift(adapter, m, "winback_message")
        T = product["price"] if product else 0
        g = gross_margin(m, product)
        n_treat = len(opted) // 2
        options.append({
            "id": "winback_message", "kind": "winback_message", "title_hi": "Sirf yaad dilane wala message",
            "description_hi": f"{len(opted)} purane customers ko ek message, bina discount ke.",
            "expected_profit": int(round(n_treat * (u["p_t"] - u["p_c"]) * T * g)), "expected_cost": 0,
            "n_target": int(len(opted)),
            "assumptions": {"p_t": u["p_t"], "p_c": u["p_c"], "source": u["source"], "n_treat": n_treat,
                            **profit_risk(n_treat, u, T, g, 0)},
            "params": {"start_hour": window[0], "end_hour": window[1], "segment": "lapsed_opted_in", "n_target": int(len(opted))},
            "relevant": True,
        })

    for o in options:
        o["policy"] = policy.check(o, pol, {"merchant": m, "now_hour": None})
    options.sort(key=lambda o: o["expected_profit"], reverse=True)
    rec = next((o for o in options if o["policy"]["passed"] and o["relevant"] and o["expected_profit"] > 0), None)
    return {"options": options, "recommended_id": rec["id"] if rec else None}
