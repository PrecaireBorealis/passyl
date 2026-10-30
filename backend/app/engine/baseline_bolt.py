"""Chronos-Bolt zero-shot baseline (spec 8.1 B): 2,048-hour context ending the day before, one batch."""
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from ..adapters.synthetic import get_adapter
from ..config import CHRONOS_MODEL, chronos_device
from .baseline import closed_hours, tidy

CONTEXT = 2048
_PIPE = None


def pipeline():
    global _PIPE
    if _PIPE is None:
        import torch
        from chronos import BaseChronosPipeline
        _PIPE = BaseChronosPipeline.from_pretrained(CHRONOS_MODEL, device_map=chronos_device(), dtype=torch.float32)
    return _PIPE


class BoltBaseline:
    name = "chronos_bolt"

    def __init__(self, adapter=None):
        self.a = adapter or get_adapter()
        pipeline()  # load at construction so a missing model fails over immediately

    def contexts(self, merchant_ids: list[str], d: date) -> list[np.ndarray]:
        start = d - timedelta(days=CONTEXT // 24 + 1)
        h = self.a.get_hourly(merchant_ids, start, d - timedelta(days=1))
        idx = pd.date_range(datetime.combine(start, datetime.min.time()), periods=(d - start).days * 24, freq="h")
        out = []
        for mid in merchant_ids:
            g = h[h["merchant_id"] == mid]
            s = pd.Series(g["revenue"].to_numpy(float), index=pd.to_datetime(g["date"]) + pd.to_timedelta(g["hour"], "h"))
            s = s.reindex(idx)
            s = s[s.first_valid_index():] if s.first_valid_index() is not None else s.iloc[-24:]
            out.append(s.fillna(0).to_numpy()[-CONTEXT:])
        return out

    def hourly(self, merchant_ids: list[str], d: date) -> dict[str, np.ndarray]:
        import torch
        ctx = [torch.tensor(c, dtype=torch.float32) for c in self.contexts(merchant_ids, d)]
        q, _ = pipeline().predict_quantiles(inputs=ctx, prediction_length=24, quantile_levels=[0.1, 0.5, 0.9])
        q = q.numpy()
        closed = closed_hours(self.a, merchant_ids, d)
        return {mid: tidy(q[i], closed[mid]) for i, mid in enumerate(merchant_ids)}
