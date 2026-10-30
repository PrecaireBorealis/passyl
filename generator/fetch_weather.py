"""Open-Meteo hourly precipitation + temperature → data/reference/weather_hourly.csv (fetch once, commit)."""
import io
import sys
import time
from datetime import date, timedelta

import httpx
import pandas as pd

from .common import REF, load

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"
OUT = REF / "weather_hourly.csv"


def get(url: str, params: dict) -> dict:
    for attempt in range(5):
        try:
            r = httpx.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            wait = 2 ** attempt * 3
            print(f"  {e}; retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit(f"giving up on {url}")


def frame(js: dict, loc: str, source: str) -> pd.DataFrame:
    h = js["hourly"]
    return pd.DataFrame({"locality_id": loc, "ts": h["time"], "precip_mm": h["precipitation"],
                         "temp_c": h["temperature_2m"], "source": source})


def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT} exists, skipping (use --force to refetch)")
        return
    world = load("world.yaml")
    start, end = str(world["date_start"]), str(world["date_end"])
    parts = []
    for loc in world["localities"]:
        common = {"latitude": loc["lat"], "longitude": loc["lon"], "hourly": "precipitation,temperature_2m",
                  "timezone": "Asia/Kolkata"}
        arch = frame(get(ARCHIVE, {**common, "start_date": start, "end_date": end}), loc["id"], "open-meteo-archive")
        # the archive lags a few days: fill the tail from the forecast API's past_days
        fc = frame(get(FORECAST, {**common, "past_days": 14, "forecast_days": 1}), loc["id"], "open-meteo-forecast")
        missing = arch["precip_mm"].isna()
        fc = fc[fc["ts"].isin(arch.loc[missing, "ts"])]
        df = pd.concat([arch[~missing], fc]).sort_values("ts")
        print(f"{loc['id']}: {len(df)} hours ({missing.sum()} filled from forecast, {len(fc)} found)")
        parts.append(df)
        time.sleep(1)
    out = pd.concat(parts)
    out["ts"] = out["ts"] + ":00+05:30"
    out = out[out["ts"] <= f"{end}T23:00:00+05:30"].fillna({"precip_mm": 0.0})
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(out)} rows)")


if __name__ == "__main__":
    main()
