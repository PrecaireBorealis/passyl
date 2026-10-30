"""Seeded customer response for a live action (demo control). The only reader of campaign_truth (spec 11.2)."""
import zlib

import numpy as np
import yaml

from ..config import SCENARIO


def campaign_truth() -> dict:
    return yaml.safe_load(SCENARIO.read_text())["campaign_truth"]["family_combo_lapsed"]


def simulate(action_id: str, targets: list[dict]) -> list[dict]:
    """targets: [{payer_hash, arm}] → same with returned, spend."""
    t = campaign_truth()
    rng = np.random.default_rng(zlib.crc32(action_id.encode()))
    out = []
    for x in targets:
        p = t["treat_return_p"] if x["arm"] == "treat" else t["holdout_return_p"]
        ret = bool(rng.random() < p)
        spend = int(round(rng.lognormal(np.log(t["avg_ticket"]), 0.15) / 5) * 5) if ret else None
        out.append({**x, "returned": ret, "spend": spend})
    return out
