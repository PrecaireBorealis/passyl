"""Last-resort fallback: median of the same weekday and hour over the last 8 weeks, excluding public holidays."""
from datetime import date, timedelta

import numpy as np

from ..adapters.synthetic import get_adapter
from .baseline import closed_hours, tidy


class MedianBaseline:
    name = "median"

    def __init__(self, adapter=None):
        self.a = adapter or get_adapter()

    def hourly(self, merchant_ids: list[str], d: date) -> dict[str, np.ndarray]:
        hol = set(self.a.get_festivals(d - timedelta(days=70), d).query("scope == 'public'")["date"])
        days = [d - timedelta(days=7 * k) for k in range(1, 11)]
        days = [x for x in days if x not in hol][:8]
        h = self.a.get_hourly(merchant_ids, min(days), max(days))
        h = h[h["date"].isin(days)]
        closed = closed_hours(self.a, merchant_ids, d)
        out = {}
        for mid in merchant_ids:
            g = h[h["merchant_id"] == mid]
            grid = np.zeros((len(days), 24))
            if not g.empty:
                rows = g["date"].map({x: i for i, x in enumerate(days)}).to_numpy()
                grid[rows, g["hour"].to_numpy()] = g["revenue"].to_numpy()
            seen = np.isin(days, g["date"].unique())
            grid = grid[seen] if seen.any() else grid
            q = np.stack([np.percentile(grid, 10, axis=0), np.median(grid, axis=0), np.percentile(grid, 90, axis=0)], 1)
            out[mid] = tidy(q, closed[mid])
        return out
