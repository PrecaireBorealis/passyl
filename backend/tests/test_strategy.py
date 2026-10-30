from datetime import date

from app.adapters.synthetic import get_adapter
from app.engine import strategy


def test_flat_discount_loses_to_combo_under_default_priors():
    pri = strategy.priors()
    n, T, g, c = 40, 649, (649 - 290) / 649, 100
    pt, pc = pri["combo_lapsed"]["p_t"], pri["combo_lapsed"]["p_c"]
    combo = n * ((pt - pc) * (T * g - c) - pc * c)
    B, d, Tf, gf = 60, 0.20, 330, pri["gross_margin"]["restaurant"]
    e = pri["flat_discount_uplift_per_d"] * d
    assert B * e * Tf * (gf - d) - B * Tf * d < combo


def test_ranker_on_demo_merchant():
    r = strategy.rank(get_adapter(), "M_KOR_RES_001", date(2026, 10, 30))
    by = {o["id"]: o for o in r["options"]}
    assert by["flat_discount"]["expected_profit"] < by["combo_lapsed"]["expected_profit"]
    assert r["recommended_id"] == "combo_lapsed"
