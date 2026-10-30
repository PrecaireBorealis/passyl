"""LightGBM quantile regression (α = 0.1/0.5/0.9), one model set per category (spec 8.1 A)."""
import json
import logging
import time
from datetime import date, timedelta

import lightgbm as lgb
import numpy as np
import pandas as pd

from ..adapters.synthetic import get_adapter
from ..config import MODELS_DIR
from .baseline import closed_hours, tidy

log = logging.getLogger(__name__)
ALPHAS = (0.1, 0.5, 0.9)
ORIGIN = date(2025, 10, 1)  # week_index counts from the first day of data
PARAMS = {"objective": "quantile", "learning_rate": 0.08, "num_leaves": 63, "min_data_in_leaf": 40,
          "feature_fraction": 0.9, "verbose": -1, "num_threads": 0}
ROUNDS = 250
FEATURES = ["merchant", "hour", "weekday", "week_index", "month", "is_public_holiday"]


def features(merchant_codes: dict[str, int], mids: np.ndarray, dates: pd.Series, hours: np.ndarray, public: set) -> pd.DataFrame:
    dt = pd.to_datetime(dates)
    return pd.DataFrame({
        "merchant": pd.Categorical([merchant_codes[m] for m in mids], categories=range(len(merchant_codes))),
        "hour": hours, "weekday": dt.dt.day_of_week.to_numpy(),
        "week_index": ((dt - pd.Timestamp(ORIGIN)).dt.days // 7).to_numpy(),
        "month": dt.dt.month.to_numpy(), "is_public_holiday": dates.isin(public).astype(int).to_numpy()})


def _dir(cutoff: date):
    return MODELS_DIR / "lgbm" / cutoff.isoformat()


def train(adapter, category: str, cutoff: date) -> None:
    t0 = time.time()
    m = adapter.list_merchants()
    mids = sorted(m.loc[(m["category"] == category) & (m["opened_on"] <= cutoff), "id"])
    h = adapter.get_hourly(mids, ORIGIN, cutoff)
    public = set(adapter.get_festivals(ORIGIN, cutoff + timedelta(days=400)).query("scope == 'public'")["date"])
    codes = {x: i for i, x in enumerate(mids)}
    X = features(codes, h["merchant_id"].to_numpy(), h["date"], h["hour"].to_numpy(), public)
    y = h["revenue"].to_numpy(float)
    out = _dir(cutoff)
    out.mkdir(parents=True, exist_ok=True)
    ds = lgb.Dataset(X, y, categorical_feature=["merchant"], free_raw_data=False)
    for a in ALPHAS:
        b = lgb.train({**PARAMS, "alpha": a}, ds, ROUNDS)
        b.save_model(str(out / f"{category}_q{int(a * 100)}.txt"))
    (out / f"{category}.json").write_text(json.dumps({"codes": codes, "rows": len(y)}))
    log.info("lgbm %s cutoff %s: %d rows, %.1fs", category, cutoff, len(y), time.time() - t0)


def train_all(adapter, cutoff: date) -> None:
    for cat in sorted(adapter.list_merchants()["category"].unique()):
        train(adapter, cat, cutoff)


class LGBMBaseline:
    name = "lgbm"

    def __init__(self, adapter=None, cutoff_for=None):
        """cutoff_for(date) → training cut-off; default: the newest cached model set with cutoff < date."""
        self.a = adapter or get_adapter()
        self.cutoff_for = cutoff_for
        self._boosters: dict = {}

    def _cutoff(self, d: date) -> date:
        if self.cutoff_for:
            return self.cutoff_for(d)
        cands = sorted(date.fromisoformat(p.name) for p in (MODELS_DIR / "lgbm").glob("*") if p.is_dir())
        cands = [c for c in cands if c < d]
        if not cands:
            raise FileNotFoundError(f"no LightGBM models trained before {d}; run python -m app.engine.baseline --train-lgbm")
        return cands[-1]

    def _load(self, category: str, cutoff: date):
        key = (category, cutoff)
        if key not in self._boosters:
            p = _dir(cutoff)
            meta = p / f"{category}.json"
            if not meta.exists():
                train(self.a, category, cutoff)
            self._boosters[key] = ([lgb.Booster(model_file=str(p / f"{category}_q{int(a * 100)}.txt")) for a in ALPHAS],
                                   json.loads(meta.read_text())["codes"])
        return self._boosters[key]

    def hourly(self, merchant_ids: list[str], d: date) -> dict[str, np.ndarray]:
        cutoff = self._cutoff(d)
        assert cutoff < d, "the baseline must never see the forecast date"
        m = self.a.list_merchants().set_index("id")
        public = set(self.a.get_festivals(d, d).query("scope == 'public'")["date"])
        closed = closed_hours(self.a, merchant_ids, d)
        out = {}
        for cat, ids in pd.Series(merchant_ids).groupby(m.loc[merchant_ids, "category"].to_numpy()):
            boosters, codes = self._load(cat, cutoff)
            ids = list(ids)
            missing = [x for x in ids if x not in codes]
            if missing:
                raise KeyError(f"lgbm has no history for {missing} at cutoff {cutoff}")
            mids = np.repeat(ids, 24)
            X = features(codes, mids, pd.Series([d] * len(mids)), np.tile(np.arange(24), len(ids)), public)
            preds = np.stack([b.predict(X) for b in boosters], axis=1).reshape(len(ids), 24, 3)
            for i, mid in enumerate(ids):
                out[mid] = tidy(preds[i], closed[mid])
        return out
