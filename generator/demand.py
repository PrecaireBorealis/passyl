"""λ(m,d,h) = base × hour × dow × season × trend × festival × rain × shock × noise  (spec 7.3)."""
import numpy as np
import pandas as pd


def hour_shares(effects: dict) -> dict[str, np.ndarray]:
    out = {}
    for cat, w in effects["hour_profile"].items():
        w = np.array(w, float)
        o, c = effects["open_hours"][cat]
        w[:o] = 0
        w[c:] = 0
        out[cat] = w / w.sum()
    return out


def festival_mult(effects: dict, fest: pd.DataFrame, dates: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    """Per category: (D,) multiplier from festival_effects."""
    out = {cat: np.ones(len(dates)) for cat in effects["open_hours"]}
    idx = {d: i for i, d in enumerate(dates)}
    for cat, fx in effects["festival_effects"].items():
        if cat not in out:
            continue
        for name, spec in (fx or {}).items():
            for fd in pd.to_datetime(fest.loc[fest["name"] == name, "date"]).unique():
                for off in range(spec["days"][0], spec["days"][1] + 1):
                    i = idx.get(fd + pd.Timedelta(days=off))
                    if i is not None:
                        out[cat][i] *= spec["mult"]
    return out


def rain_mult(m: pd.Series, precip: np.ndarray, effects: dict) -> np.ndarray:
    """(D,24) multiplier; only where precip ≥ 1 mm/h."""
    eff = np.where(precip >= 1.0, np.exp(m["beta_m"] * np.minimum(precip, 10) / 10), 1.0)
    late = effects.get("rain_late_factor", {}).get(m["category"])
    if late is not None:  # delivery demand softens the late-evening penalty
        eff[:, 21:] = 1 + (eff[:, 21:] - 1) * late
    return eff


def lam_parts(m: pd.Series, dates: pd.DatetimeIndex, effects: dict, shares: dict, fest: dict) -> np.ndarray:
    """Normal-day λ without rain, shocks or noise: (D,24)."""
    cat = m["category"]
    dow = np.array(effects["dow_profile"][cat])[dates.weekday]
    season = np.array(effects["season"]["all"])[dates.month - 1]
    years = (dates - dates[0]).days.values / 365.0
    trend = np.exp(m["trend_per_year"] * (years - years[-1]))  # = 1 on the last day
    day = m["base_m"] * dow * season * trend * fest[cat]
    lam = day[:, None] * shares[cat][None, :]
    lam[dates.date < m["opened_on"]] = 0.0
    return lam
