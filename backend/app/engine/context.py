"""Context flags: rain, festival, disruption (spec 8.3). Vectorised over dates so pooling can reuse them."""
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
import yaml

from ..config import EFFECTS

RAIN_MM = 1.0


@lru_cache(maxsize=1)
def festival_effects() -> dict:
    """Domain knowledge: which festivals move which category, and on which day offsets."""
    return yaml.safe_load(EFFECTS.read_text())["festival_effects"]


def rain_hours(weather: pd.DataFrame, d: date, h1: int, h2: int) -> list[int]:
    w = weather[(weather["date"] == d) & (weather["hour"] >= h1 - 1) & (weather["hour"] < h2)
                & (weather["precip_mm"] >= RAIN_MM)]
    return sorted(w["hour"].tolist())


def rain_dates(weather: pd.DataFrame, h1: int, h2: int) -> set[date]:
    w = weather[(weather["hour"] >= h1 - 1) & (weather["hour"] < h2) & (weather["precip_mm"] >= RAIN_MM)]
    n = w.groupby("date").size()
    return set(n[n >= 2].index)


def festival_hits(fest: pd.DataFrame, category: str) -> dict[date, list[str]]:
    """date → festival names in effect for this category (falls back to public holidays for other categories)."""
    out: dict[date, list[str]] = {}
    fx = festival_effects().get(category) or {}
    for _, r in fest.iterrows():
        if r["name"] in fx:
            lo, hi = fx[r["name"]]["days"]
            for k in range(lo, hi + 1):
                out.setdefault(r["date"] + timedelta(days=k), []).append(r["name"])
        elif r["scope"] == "public":
            out.setdefault(r["date"], []).append(r["name"])
    return out


def flags(adapter, merchant: dict, d: date, h1: int, h2: int) -> dict:
    w = adapter.get_weather(merchant["locality_id"], d, d)
    rh = rain_hours(w, d, h1, h2) if not w.empty else []
    mm = float(w.loc[w["hour"].isin(rh), "precip_mm"].max()) if rh else 0.0
    fest = festival_hits(adapter.get_festivals(d - timedelta(days=15), d + timedelta(days=15)), merchant["category"])
    dis = adapter.get_disruptions(merchant["city"], d, d)
    return {
        "rain": {"on": len(rh) >= 2, "hours": rh, "max_mm": round(mm, 1), "first_hour": rh[0] if rh else None},
        "festival": {"on": d in fest, "names": fest.get(d, [])},
        "disruption": {"on": not dis.empty, "kinds": dis["kind"].tolist(),
                       "severity": float(dis["severity"].max()) if not dis.empty else None},
    }
