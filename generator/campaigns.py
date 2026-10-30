"""~200 synthetic past campaigns with true uplift drawn around the priors (spec 7.6, 9.2)."""
import numpy as np
import pandas as pd


def build(merchants: pd.DataFrame, effects: dict, rng, n: int = 200) -> pd.DataFrame:
    pri = effects["priors"]
    kinds = ["combo_lapsed", "winback_message", "delivery_combo_rain"]
    pool = merchants[merchants["category"].isin(["restaurant", "cafe", "sweet_shop", "kirana"])
                     & ~merchants["id"].isin(["M_KOR_RES_001", "M_KOR_CAF_NEW"])]
    rows = []
    for i in range(n):
        m = pool.iloc[int(rng.integers(len(pool)))]
        kind = kinds[int(rng.choice(3, p=[0.45, 0.35, 0.20]))]
        pt, pc = pri[kind]["p_t"], pri[kind]["p_c"]
        true_c = float(np.clip(rng.normal(pc, 0.03), 0.02, 0.6))
        true_t = float(np.clip(true_c + rng.normal(pt - pc, 0.05), 0.02, 0.9))
        nt, nh = int(rng.integers(20, 90)), int(rng.integers(20, 90))
        rows.append({"id": f"C_{i:04d}", "merchant_id": m["id"], "kind": kind, "category": m["category"],
                     "n_treat": nt, "n_hold": nh,
                     "treat_rate": round(rng.binomial(nt, true_t) / nt, 4),
                     "hold_rate": round(rng.binomial(nh, true_c) / nh, 4),
                     "date": (pd.Timestamp("2025-11-01") + pd.Timedelta(days=int(rng.integers(0, 330)))).date()})
    return pd.DataFrame(rows)
