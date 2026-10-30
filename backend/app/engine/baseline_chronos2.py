"""Chronos-2 baseline: zero-shot, the public-holiday calendar as a known future covariate, and the shop forecast
jointly with its peers (cross-learning: the batch shares information through group attention)."""
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from ..adapters.synthetic import get_adapter
from ..config import CHRONOS_DEVICE, env
from .baseline import closed_hours, tidy

CHRONOS2_MODEL = env("CHRONOS2_MODEL", "amazon/chronos-2")
CONTEXT_DAYS = 56            # 1,344 hours: eight weeks of weekly rhythm (CPU: ~1.7 s per shop + peers batch)
_PIPE = None


def pipeline():
    global _PIPE
    if _PIPE is None:
        import torch
        from chronos import Chronos2Pipeline
        _PIPE = Chronos2Pipeline.from_pretrained(CHRONOS2_MODEL, device_map=CHRONOS_DEVICE, torch_dtype=torch.float32)
    return _PIPE


class Chronos2Baseline:
    name = "chronos2"

    def __init__(self, adapter=None):
        self.a = adapter or get_adapter()
        pipeline()

    def hourly(self, merchant_ids: list[str], d: date) -> dict[str, np.ndarray]:
        import torch
        start = d - timedelta(days=CONTEXT_DAYS)
        h = self.a.get_hourly(merchant_ids, start, d - timedelta(days=1))
        idx = pd.date_range(datetime.combine(start, datetime.min.time()), periods=CONTEXT_DAYS * 24, freq="h")
        public = set(self.a.get_festivals(start, d).query("scope == 'public'")["date"])
        hol_past = np.array([x.date() in public for x in idx], dtype=np.float32)
        hol_future = np.full(24, float(d in public), dtype=np.float32)
        inputs = []
        for mid in merchant_ids:
            g = h[h["merchant_id"] == mid]
            s = pd.Series(g["revenue"].to_numpy(float), index=pd.to_datetime(g["date"]) + pd.to_timedelta(g["hour"], "h"))
            s = s.reindex(idx)
            first = s.first_valid_index()
            keep = slice(idx.get_loc(first), None) if first is not None else slice(-24, None)
            inputs.append({"target": torch.tensor(s.fillna(0).to_numpy()[keep], dtype=torch.float32),
                           "past_covariates": {"holiday": torch.tensor(hol_past[keep])},
                           "future_covariates": {"holiday": torch.tensor(hol_future)}})
        q, _ = pipeline().predict_quantiles(inputs, prediction_length=24, quantile_levels=[0.1, 0.5, 0.9],
                                            cross_learning=True)
        closed = closed_hours(self.a, merchant_ids, d)
        return {mid: tidy(q[i][0].numpy(), closed[mid]) for i, mid in enumerate(merchant_ids)}
