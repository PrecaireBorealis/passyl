"""Merchant table: placement, scale, rain sensitivity, trend."""
from datetime import date

import numpy as np
import pandas as pd

ABBR = {"restaurant": "RES", "kirana": "KIR", "cafe": "CAF", "sweet_shop": "SWT", "pharmacy": "PHA",
        "salon": "SAL", "apparel": "APP", "electronics": "ELE"}
NAMES = {"restaurant": ["Annapoorna", "Spice Route", "Udupi Grand", "Biryani House", "Dhaba 47", "Coastal Kitchen"],
         "kirana": ["Sri Ganesh Stores", "Daily Needs", "Lakshmi Provisions", "Fresh Mart"],
         "cafe": ["Brew Point", "Filter Kaapi Co", "Chai Adda", "Bean There"],
         "sweet_shop": ["Mithai Mahal", "Sweet Corner", "Ghee Sweets"],
         "pharmacy": ["Wellness Pharma", "City Medicals", "Apollo-style Chemist"],
         "salon": ["Style Studio", "Looks Unisex", "Trim & Shine"],
         "apparel": ["Fashion Hub", "Ethnic Threads", "Trendz"],
         "electronics": ["Digital World", "Mobile Point", "Gadget Zone"]}


def _offset(lat: float, lon: float, r_km: float, rng) -> tuple[float, float]:
    d = r_km * np.sqrt(rng.random())
    a = rng.random() * 2 * np.pi
    return lat + d * np.cos(a) / 111.0, lon + d * np.sin(a) / (111.0 * np.cos(np.radians(lat)))


def build(world: dict, effects: dict, scen: dict, rng) -> pd.DataFrame:
    start = pd.Timestamp(world["date_start"])
    end = pd.Timestamp(world["date_end"])
    rows = []
    for loc in world["localities"]:
        for cat, n in world["merchants_per_locality"].items():
            for i in range(1, n + 1):
                lat, lon = _offset(loc["lat"], loc["lon"], world["placement_radius_km"], rng)
                # ~5% opened partway through the year
                opened = start if rng.random() > 0.05 else start + pd.Timedelta(days=int(rng.integers(30, 300)))
                rows.append({
                    "id": f"M_{loc['id']}_{ABBR[cat]}_{i:03d}",
                    "name": f"{rng.choice(NAMES[cat])} {loc['name']}",
                    "category": cat, "locality_id": loc["id"], "city": loc["city"],
                    "lat": round(lat, 6), "lon": round(lon, 6), "opened_on": opened.date(),
                    "language": "hi-en", "txn_level": loc["txn_level"],
                    "base_m": effects["daily_txn_base"][cat] * rng.lognormal(0, 0.3),
                    "beta_m": effects["rain_beta_type"][cat] * rng.lognormal(0, 0.35),
                    "trend_per_year": rng.normal(0, 0.10),
                })
    df = pd.DataFrame(rows)

    # demo merchant: fixed name, centre of Koramangala, base tuned to the revenue target, flat trend
    m = scen["merchant"]
    ix = df.index[df["id"] == m["id"]][0]
    kor = next(l for l in world["localities"] if l["id"] == m["locality"])
    mu, sig = effects["ticket_lognorm"][m["category"]]
    fri = effects["dow_profile"][m["category"]][4]
    octo = effects["season"]["all"][9]
    df.loc[ix, ["name", "lat", "lon", "opened_on", "trend_per_year", "beta_m"]] = [
        m["name"], kor["lat"], kor["lon"], start.date(), 0.0, effects["rain_beta_type"][m["category"]]]
    df.loc[ix, "base_m"] = m["base_daily_revenue_target"] / (np.exp(mu + sig ** 2 / 2) * fri * octo * 0.985)

    t = scen["thin_history_merchant"]
    lat, lon = _offset(kor["lat"], kor["lon"], 0.8, rng)
    cat = t["category"]
    df.loc[len(df)] = {"id": t["id"], "name": t["name"], "category": cat, "locality_id": "KOR",
                       "city": kor["city"], "lat": round(lat, 6), "lon": round(lon, 6),
                       "opened_on": pd.Timestamp(t["opened_on"]).date(), "language": "hi-en", "txn_level": True,
                       "base_m": effects["daily_txn_base"][cat] * 0.6, "beta_m": effects["rain_beta_type"][cat],
                       "trend_per_year": 0.0}
    assert (df["opened_on"] <= end.date()).all()
    return df
