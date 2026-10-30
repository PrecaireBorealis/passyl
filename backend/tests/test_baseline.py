from datetime import date

import numpy as np
import pytest

from app.adapters.synthetic import get_adapter

D = date(2026, 9, 18)
IDS = ["M_KOR_RES_001", "M_KOR_RES_002", "M_IND_KIR_001"]


class SpikeAdapter:
    """The real adapter, but revenue on and after D is ×10: a baseline that read it would change."""

    def __init__(self):
        self.a = get_adapter()

    def __getattr__(self, k):
        return getattr(self.a, k)

    def get_hourly(self, ids, d1, d2):
        h = self.a.get_hourly(ids, d1, max(d2, D))
        h.loc[h["date"] >= D, "revenue"] *= 10
        return h[h["date"] <= d2]


def model(name, adapter=None):
    if name == "lgbm":
        from app.engine.baseline_lgbm import LGBMBaseline
        return LGBMBaseline(adapter, cutoff_for=lambda d: date(2026, 8, 31))
    if name == "chronos_bolt":
        try:
            from app.engine.baseline_bolt import BoltBaseline
            return BoltBaseline(adapter)
        except Exception as e:
            pytest.skip(f"Chronos-Bolt weights not cached: {e}")
    from app.engine.baseline_median import MedianBaseline
    return MedianBaseline(adapter)


@pytest.mark.parametrize("name", ["median", "lgbm", "chronos_bolt"])
def test_shape_order_and_closed_hours(name):
    for q in model(name).hourly(IDS, D).values():
        assert q.shape == (24, 3)
        assert (q >= 0).all()
        assert (q[:, 0] <= q[:, 1]).all() and (q[:, 1] <= q[:, 2]).all()
        assert (q[:5] == 0).all()  # all three are closed at night


@pytest.mark.parametrize("name", ["median", "lgbm", "chronos_bolt"])
def test_no_data_on_or_after_date_is_read(name):
    clean, spiked = model(name).hourly(IDS, D), model(name, SpikeAdapter()).hourly(IDS, D)
    for mid in IDS:
        np.testing.assert_allclose(clean[mid], spiked[mid], rtol=1e-5)
