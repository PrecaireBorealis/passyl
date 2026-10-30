"""Baseline protocol, factory with fallback chain (chronos_bolt → lgbm → median), window sums (spec 8.1).

CLI (from backend/):  python -m app.engine.baseline --prefetch-bolt | --train-lgbm [--cutoff YYYY-MM-DD]
"""
import argparse
import logging
import time
from datetime import date, timedelta
from typing import Protocol

import numpy as np

from ..adapters.synthetic import get_adapter

log = logging.getLogger(__name__)
CHAIN = ["chronos_bolt", "lgbm", "median"]


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


def expected(bl: Baseline, merchant_id: str, d: date, h1: int, h2: int) -> dict:
    """Window = sum of hourly quantiles (over-wide by design; the benchmark measures the coverage)."""
    s = bl.hourly([merchant_id], d)[merchant_id][h1:h2].sum(axis=0)
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
