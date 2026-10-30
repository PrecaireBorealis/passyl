from app.agent import templates
from app.agent.number_guard import check

TOOL = {"shop_change_pct": -18.1, "split": {"market_pct": -12.3, "shop_pct": -5.8}, "peer": {"n": 14},
        "expected": {"p50": 20200}, "window": {"start_hour": 18, "end_hour": 22}}


def test_good_reply_passes():
    r = check("Shaam ki sales 18% kam hain. Aas-paas ke 14 restaurants bhi 12% gire. 6 se 10 baje. Normal ₹20,200.", TOOL)
    assert r["ok"], r


def test_invented_number_rejected():
    r = check("Sales 25% kam hain aur 30 customers nahi aaye.", TOOL)
    assert not r["ok"] and "25" in r["unmatched"]


def test_templates_pass_their_own_guard():
    card = {"window": {"start_hour": 18, "end_hour": 20}, "shop_change_pct": -25.7, "confidence": {"state": "wide"},
            "peer": {"n": 13, "median_change_pct": -11.1}, "split": {"market_pct": -11.1, "shop_pct": -14.6},
            "factors": [{"id": "rain", "label_hi": "Baarish (5 baje se)", "status": "explains_market"}],
            "shop_drivers": [{"id": "regulars_missing", "usual": 6, "actual": 3, "contribution_pts": -9.0}]}
    for lang in ("hi-en", "en"):
        assert check(templates.why(card, lang), card)["ok"]
