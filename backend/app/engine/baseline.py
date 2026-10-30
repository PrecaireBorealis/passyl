"""Baseline protocol, factory with fallback chain (chronos2 → chronos_bolt → lgbm → median), window sums (spec 8.1).

CLI (from backend/):  python -m app.engine.baseline --prefetch-bolt | --train-lgbm [--cutoff YYYY-MM-DD]
"""
import argparse
import json
import logging
import time
from datetime import date, timedelta
from typing import Protocol

import numpy as np

from ..adapters.synthetic import get_adapter

log = logging.getLogger(__name__)
CHAIN = ["chronos2", "chronos_bolt", "lgbm", "median"]


class Baseline(Protocol):
    name: str

    def hourly(self, merchant_ids: list[str], date: date) -> dict[str, np.ndarray]:
        """Per merchant: (24, 3) hourly revenue quantiles [p10, p50, p90] for `date`, using data < date only."""
        ...


def closed_hours(adapter, merchant_ids: list[str], d: date) -> dict[str, np.ndarray]:
    """Hours with zero revenue on every day of the last 8 weeks → closed (bool mask of 24)."""
    h = adapter.get_hourly(merchant_ids, d - timedelta(days=56), d - timedelta(days=1))
    out = {}
    for mid in merchant_ids:
        g = h[h["merchant_id"] == mid]
        rev = np.zeros(24)
        np.add.at(rev, g["hour"].to_numpy(), g["revenue"].to_numpy())
        out[mid] = rev == 0
    return out


def tidy(q: np.ndarray, closed: np.ndarray) -> np.ndarray:
    """Sort quantiles (separately-fit quantiles can cross), clip negatives, zero closed hours."""
    q = np.sort(np.clip(q, 0, None), axis=1)
    q[closed] = 0
    return q


class Fallback:
    """Tries each model in order; `name` reports the one that actually answered."""

    def __init__(self, names: list[str]):
        self.names = names
        self.name = names[0]
        self._models: dict = {}
        self._cache: dict = {}

    def _model(self, n: str):
        if n not in self._models:
            if n == "lgbm":
                from .baseline_lgbm import LGBMBaseline
                self._models[n] = LGBMBaseline()
            elif n == "chronos2":
                from .baseline_chronos2 import Chronos2Baseline
                self._models[n] = Chronos2Baseline()
            elif n == "chronos_bolt":
                from .baseline_bolt import BoltBaseline
                self._models[n] = BoltBaseline()
            else:
                from .baseline_median import MedianBaseline
                self._models[n] = MedianBaseline()
        return self._models[n]

    def hourly(self, merchant_ids: list[str], d: date) -> dict[str, np.ndarray]:
        errors = []
        for i, n in enumerate(self.names):
            key = [(n, m, d) for m in merchant_ids]
            if all(k in self._cache for k in key):
                self.name = n if i == 0 else f"{n} (fallback)"
                return {m: self._cache[k] for m, k in zip(merchant_ids, key)}
            try:
                t0 = time.perf_counter()
                out = self._model(n).hourly(merchant_ids, d)
                self.last_ms = int((time.perf_counter() - t0) * 1000)
            except Exception as e:  # any model failure → next in the chain, never a crash in the demo
                log.warning("baseline %s failed: %s", n, e)
                errors.append(f"{n}: {e}")
                continue
            for m, q in out.items():
                self._cache[(n, m, d)] = q
            self.name = n if i == 0 else f"{n} (fallback)"
            self.errors = errors
            return out
        raise RuntimeError("all baselines failed: " + "; ".join(errors))


_INSTANCES: dict[str, Fallback] = {}


def get_baseline(name: str | None = None) -> Fallback:
    from ..config import BASELINE_MODEL
    name = name or BASELINE_MODEL
    if name not in _INSTANCES:
        _INSTANCES[name] = Fallback(CHAIN[CHAIN.index(name):])
    return _INSTANCES[name]


Z90 = 1.2816


def conformal_scales(model: str) -> tuple[float, float]:
    """Split-conformal scale factors (lower, upper) for a model, calibrated on clean windows of the dev seed
    (benchmark/run.py --calibrate). 1.0 = uncalibrated."""
    from ..config import ROOT
    f = ROOT / "backend" / "models" / "conformal.json"
    if not f.exists():
        return 1.0, 1.0
    c = json.loads(f.read_text()).get(model.split(" ")[0], {})
    return c.get("lo", 1.0), c.get("hi", 1.0)


def window_sigmas(q: np.ndarray, h1: int, h2: int) -> tuple[float, float]:
    """Window-level spread below / above the median, treating hours as independent (spreads add in quadrature).
    Summing hourly p10/p90 instead assumes every hour misses together, which over-covers badly."""
    w = q[h1:h2]
    lo = float(np.sqrt((((w[:, 1] - w[:, 0]) / Z90) ** 2).sum()))
    hi = float(np.sqrt((((w[:, 2] - w[:, 1]) / Z90) ** 2).sum()))
    return lo, hi


def window_quantiles(q: np.ndarray, h1: int, h2: int, model: str) -> np.ndarray:
    """[p10, p50, p90] for the window: median sum ± conformally scaled independent-hours spread."""
    p50 = float(q[h1:h2, 1].sum())
    lo, hi = window_sigmas(q, h1, h2)
    c_lo, c_hi = conformal_scales(model)
    return np.array([max(0.0, p50 - Z90 * c_lo * lo), p50, p50 + Z90 * c_hi * hi])


def expected(bl: Baseline, merchant_id: str, d: date, h1: int, h2: int) -> dict:
    s = window_quantiles(bl.hourly([merchant_id], d)[merchant_id], h1, h2, bl.name)
    return {"p10": int(round(s[0])), "p50": int(round(s[1])), "p90": int(round(s[2])), "model": bl.name}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefetch-bolt", action="store_true")
    ap.add_argument("--train-lgbm", action="store_true")
    ap.add_argument("--cutoff", help="last day of training data (default: the day before the demo date)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    if a.prefetch_bolt:
        from huggingface_hub import snapshot_download
        from ..config import CHRONOS_MODEL
        print(snapshot_download(CHRONOS_MODEL))
    if a.train_lgbm:
        from ..clock import today
        from .baseline_lgbm import train_all
        cutoff = date.fromisoformat(a.cutoff) if a.cutoff else today() - timedelta(days=1)
        train_all(get_adapter(), cutoff)


if __name__ == "__main__":
    main()
