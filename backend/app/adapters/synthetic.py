"""Postgres implementation of DataAdapter over the synthetic world."""
from datetime import date, datetime, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from ..db import conn

MIN_PEER_AGE_DAYS = 56  # peers opened < 8 weeks ago are excluded (spec 8.2)


def _df(sql: str, params=()) -> pd.DataFrame:
    with conn() as c:
        cur = c.execute(sql, params)
        return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])


def km(lat1, lon1, lat2, lon2):
    """Haversine distance in km (vectorised)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


class SyntheticAdapter:
    @lru_cache(maxsize=1)
    def list_merchants(self) -> pd.DataFrame:
        return _df("SELECT m.*, l.city FROM merchants m JOIN localities l ON l.id = m.locality_id ORDER BY m.id")

    def get_merchant(self, merchant_id: str) -> dict | None:
        m = self.list_merchants()
        r = m[m["id"] == merchant_id]
        return None if r.empty else r.iloc[0].to_dict()

    def list_peers(self, merchant_id: str, radius_km: float, as_of: date | None = None) -> list[str]:
        me = self.get_merchant(merchant_id)
        m = self.list_merchants()
        cutoff = (as_of or date.max - timedelta(days=MIN_PEER_AGE_DAYS + 1)) - timedelta(days=MIN_PEER_AGE_DAYS)
        c = m[(m["category"] == me["category"]) & (m["id"] != merchant_id) & (m["opened_on"] <= cutoff)]
        d = km(me["lat"], me["lon"], c["lat"].to_numpy(), c["lon"].to_numpy())
        return c.loc[d <= radius_km, "id"].tolist()

    def get_hourly(self, merchant_ids: list[str], date_from: date, date_to: date) -> pd.DataFrame:
        return _df("SELECT * FROM hourly WHERE merchant_id = ANY(%s) AND date BETWEEN %s AND %s "
                   "ORDER BY merchant_id, date, hour", (list(merchant_ids), date_from, date_to))

    def get_transactions(self, merchant_id: str, start: datetime, end: datetime) -> pd.DataFrame:
        return _df("SELECT * FROM transactions WHERE merchant_id = %s AND ts >= %s AND ts < %s ORDER BY ts",
                   (merchant_id, start, end))

    @lru_cache(maxsize=512)
    def has_transactions(self, merchant_id: str) -> bool:
        return not _df("SELECT 1 FROM transactions WHERE merchant_id = %s LIMIT 1", (merchant_id,)).empty

    def get_customers(self, merchant_id: str, payer_hashes: list[str] | None = None) -> pd.DataFrame:
        if payer_hashes is None:
            return _df("SELECT * FROM customers WHERE merchant_id = %s", (merchant_id,))
        return _df("SELECT * FROM customers WHERE merchant_id = %s AND payer_hash = ANY(%s)",
                   (merchant_id, list(payer_hashes)))

    def get_weather(self, locality_id: str, date_from: date, date_to: date) -> pd.DataFrame:
        df = _df("SELECT * FROM weather_hourly WHERE locality_id = %s AND ts >= %s AND ts < %s ORDER BY ts",
                 (locality_id, f"{date_from}T00:00:00+05:30", f"{date_to + timedelta(days=1)}T00:00:00+05:30"))
        if not df.empty:
            ts = pd.to_datetime(df["ts"]).dt.tz_convert("Asia/Kolkata")
            df["date"], df["hour"] = ts.dt.date, ts.dt.hour
        return df

    def get_festivals(self, date_from: date, date_to: date) -> pd.DataFrame:
        return _df("SELECT * FROM festivals WHERE date BETWEEN %s AND %s ORDER BY date", (date_from, date_to))

    def get_disruptions(self, city: str, date_from: date, date_to: date) -> pd.DataFrame:
        return _df("SELECT * FROM disruptions WHERE city = %s AND date BETWEEN %s AND %s", (city, date_from, date_to))

    def get_products(self, merchant_id: str) -> list[dict]:
        return _df("SELECT * FROM products WHERE merchant_id = %s", (merchant_id,)).to_dict("records")

    def get_policy(self, merchant_id: str) -> dict:
        r = _df("SELECT * FROM merchant_policy WHERE merchant_id = %s", (merchant_id,))
        return r.iloc[0].to_dict() if not r.empty else {}

    @lru_cache(maxsize=1)
    def get_past_campaigns(self) -> pd.DataFrame:
        return _df("SELECT p.*, l.city FROM past_campaigns p JOIN merchants m ON m.id = p.merchant_id "
                   "JOIN localities l ON l.id = m.locality_id")


_ADAPTER = SyntheticAdapter()


def get_adapter() -> SyntheticAdapter:
    return _ADAPTER
