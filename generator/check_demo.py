"""Demo targets checked through the real engine on the loaded DB (not the generator's proxy).
python -m generator.check_demo [--baseline lgbm]"""
import argparse
import sys
from datetime import date

from .common import ROOT, load

sys.path.insert(0, str(ROOT / "backend"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=None)
    a = ap.parse_args()
    from app.adapters.synthetic import get_adapter
    from app.engine.baseline import get_baseline
    from app.engine.why import explain_change
    scen = load("scenarios/raju_demo.yaml")
    t = scen["targets_check"]
    card = explain_change(get_adapter(), scen["merchant"]["id"], date.fromisoformat(str(scen["demo_date"])),
                          baseline=get_baseline(a.baseline))
    shop, peer = card["shop_change_pct"], card["peer"]["median_change_pct"]
    ok = lambda v, r: "OK " if v is not None and r[0] <= v <= r[1] else "OUT"
    print(f"baseline {card['baseline_model']}, window {card['window']}")
    print(f"  {ok(shop, t['evening_drop_pct'])} shop change {shop}%  (target {t['evening_drop_pct']})")
    print(f"  {ok(peer, t['peer_drop_pct'])} peer median {peer}%  (target {t['peer_drop_pct']})")
    print(f"  split {card['split']}, top driver {card['shop_drivers'][:1]}, confidence {card['confidence']['state']}")


if __name__ == "__main__":
    main()
