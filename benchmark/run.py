"""Shock-Injection Benchmark (spec 16).  From the repo root:
   DATABASE_URL=... DATA_SEED=42 python -m benchmark.run --seed 42 --baselines lgbm,chronos_bolt
The engine runs through the same function the API uses; shock_labels is read here for scoring only."""
import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.adapters.synthetic import get_adapter  # noqa: E402
from app.config import CHRONOS_MODEL  # noqa: E402
from app.db import conn  # noqa: E402
from app.engine.why import explain_change, is_flagged  # noqa: E402

from . import metrics  # noqa: E402

CAVEAT = "Synthetic data with planted causes. Tests the engine's logic, not real-world accuracy."


class Timed:
    """Wraps a baseline model; records the latency of each uncached hourly() call (shop + peers)."""

    def __init__(self, model):
        self.m, self.name, self.ms = model, model.name, []

    def hourly(self, ids, d):
        t0 = time.perf_counter()
        out = self.m.hourly(ids, d)
        self.ms.append((time.perf_counter() - t0) * 1000)
        return out


def make_baseline(name: str):
    if name == "lgbm":
        from app.engine.baseline_lgbm import LGBMBaseline
        # monthly rolling origins: the model for a window is trained up to the last day of the previous month
        return LGBMBaseline(cutoff_for=lambda d: d.replace(day=1) - timedelta(days=1))
    if name == "chronos_bolt":
        from app.engine.baseline_bolt import BoltBaseline
        return BoltBaseline()
    from app.engine.baseline_median import MedianBaseline
    return MedianBaseline()


def windows(seed: int, max_rain: int, rng) -> pd.DataFrame:
    with conn() as c:
        lab = pd.DataFrame(c.execute("SELECT * FROM shock_labels WHERE date BETWEEN '2026-01-01' AND '2026-10-29'").fetchall())
    lab = lab.drop_duplicates(["merchant_id", "date", "start_hour", "end_hour", "kind"])
    # windows carrying two different shocks can't be scored for cause: keep the first kind only
    lab = lab.drop_duplicates(["merchant_id", "date", "start_hour", "end_hour"])
    rain = lab[lab["kind"] == "rain"]
    if len(rain) > max_rain:
        lab = pd.concat([lab[lab["kind"] != "rain"], rain.sample(max_rain, random_state=seed)])
    # thin-history windows: merchants that opened during the evaluation period, 1–5 weeks after opening
    m = get_adapter().list_merchants()
    late = m[m["opened_on"] >= date(2026, 1, 1)]
    thin = [{"merchant_id": r.id, "date": r.opened_on + timedelta(days=int(rng.integers(7, 36))), "start_hour": 18,
             "end_hour": 22, "kind": "thin", "true_effect_pct": None, "scope": "merchant"} for r in late.itertuples()]
    thin = [t for t in thin if t["date"] <= date(2026, 10, 29)]
    return pd.concat([lab, pd.DataFrame(thin)], ignore_index=True).sort_values(["date", "merchant_id"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--baselines", default="lgbm,chronos_bolt")
    ap.add_argument("--out", default=str(ROOT / "benchmark" / "results"))
    ap.add_argument("--max-rain", type=int, default=120)
    ap.add_argument("--limit", type=int, default=0, help="debug: only the first N windows")
    ap.add_argument("--app-baseline", default=None, help="the frozen app default (chosen on seed 7)")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    adapter = get_adapter()
    W = windows(a.seed, a.max_rain, rng)
    if a.limit:
        W = W.groupby("kind").head(max(1, a.limit // 8))
    with conn() as c:
        public = {r["date"] for r in c.execute("SELECT date FROM festivals WHERE scope = 'public'").fetchall()}
    print(f"seed {a.seed}: {len(W)} windows {W['kind'].value_counts().to_dict()}", flush=True)
    out = {"seed": a.seed, "n_shock_windows": int((~W["kind"].isin(["none", "thin"])).sum()),
           "n_clean_windows": int((W["kind"] == "none").sum()), "n_thin_windows": int((W["kind"] == "thin").sum()),
           "app_baseline": a.app_baseline, "baselines": {}, "caveat": CAVEAT}
    rows_out, cards_out = [], []
    for name in a.baselines.split(","):
        bl = Timed(make_baseline(name))
        results, fc = [], []
        t0 = time.time()
        for i, w in enumerate(W.itertuples()):
            try:
                card = explain_change(adapter, w.merchant_id, w.date, int(w.start_hour), int(w.end_hour), baseline=bl)
            except Exception as e:
                print(f"  {name} {w.merchant_id} {w.date} {w.kind}: {e}", flush=True)
                continue
            r = {"kind": w.kind, "true_effect_pct": w.true_effect_pct, "card": card, "flagged": is_flagged(card),
                 "cause": metrics.top_cause(card)}
            results.append(r)
            cards_out.append({"baseline": name, "kind": w.kind, "true_effect_pct": w.true_effect_pct, "card": card,
                              "holiday": w.date in public})
            rows_out.append({"baseline": name, "merchant_id": w.merchant_id, "date": str(w.date), "window": f"{w.start_hour}-{w.end_hour}",
                             "kind": w.kind, "true_effect_pct": w.true_effect_pct, "shop_change_pct": card["shop_change_pct"],
                             "market_pct": (card.get("split") or {}).get("market_pct"), "flagged": r["flagged"],
                             "cause": r["cause"], "confidence": card["confidence"]["state"]})
            if w.kind == "none" and card["expected"]:
                fc.append({"actual": card["actual"], **{k: card["expected"][k] for k in ("p10", "p50", "p90")},
                           "holiday": w.date in public})
            if i % 50 == 0:
                print(f"  {name}: {i}/{len(W)} windows, {time.time() - t0:.0f}s", flush=True)
        f = metrics.forecast(fc)
        f["latency_ms_p50"] = int(np.percentile(bl.ms, 50)) if bl.ms else None
        f["latency_ms_p95"] = int(np.percentile(bl.ms, 95)) if bl.ms else None
        res = {"forecast": f, "engine": metrics.engine(results), "n_windows_scored": len(results),
               "runtime_s": int(time.time() - t0)}
        if name == "chronos_bolt":
            res["model_id"] = CHRONOS_MODEL
        out["baselines"][name] = res
        print(json.dumps({name: {k: v for k, v in res.items() if k != "engine"} | {"engine": {k: v for k, v in res["engine"].items() if k != "by_kind"}}}, indent=1), flush=True)
    if not out["app_baseline"]:
        # the rule from 16.1: lowest WQL on clean windows, tie-break cause accuracy then latency
        out["app_baseline"] = min(out["baselines"], key=lambda n: (out["baselines"][n]["forecast"].get("wql", 9),
                                                                   -(out["baselines"][n]["engine"]["cause_accuracy"] or 0),
                                                                   out["baselines"][n]["forecast"].get("latency_ms_p50") or 0))
    od = Path(a.out)
    od.mkdir(parents=True, exist_ok=True)
    tag = "" if a.seed == 42 else f"_seed{a.seed}"
    (od / f"benchmark{tag}.json").write_text(json.dumps(out, indent=2, default=str))
    pd.DataFrame(rows_out).to_csv(od / f"windows{tag}.csv", index=False)
    (od / f"report{tag}.md").write_text(report(out))
    with open(od / f"cards{tag}.jsonl", "w") as fh:  # full cards: re-score offline with benchmark.rescore
        for c in cards_out:
            fh.write(json.dumps(c, default=str) + "\n")
    print(f"wrote {od}/benchmark{tag}.json; app baseline: {out['app_baseline']}")


def report(o: dict) -> str:
    names = list(o["baselines"])
    rows = [("WAPE (p50), clean", "forecast", "wape_p50"), ("Weighted quantile loss", "forecast", "wql"),
            ("p10–p90 coverage (nominal 80%)", "forecast", "coverage_p10_p90"), ("Holiday WAPE", "forecast", "holiday_wape"),
            ("Latency p50 / p95 (ms)", "forecast", "latency"), ("Detection rate", "engine", "detection_rate"),
            ("Cause accuracy (top-1)", "engine", "cause_accuracy"), ("Market split MAE (pts)", "engine", "split_mae_pts"),
            ("Range coverage (target ~80%)", "engine", "range_coverage"), ("False alarm rate", "engine", "false_alarm_rate"),
            ("\"I don't know\" rate (thin history)", "engine", "idk_rate")]
    s = [f"# Shock-Injection Benchmark, seed {o['seed']}", "",
         f"{o['n_shock_windows']} shock windows, {o['n_clean_windows']} clean windows, {o['n_thin_windows']} thin-history windows. "
         f"App baseline: **{o['app_baseline']}**.", "", "| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for label, sec, key in rows:
        cells = []
        for n in names:
            b = o["baselines"][n][sec]
            v = f"{b.get('latency_ms_p50')} / {b.get('latency_ms_p95')}" if key == "latency" else b.get(key)
            cells.append("–" if v is None else (f"{v:.1%}" if isinstance(v, float) and key not in ("wql", "split_mae_pts") else str(v)))
        s.append(f"| {label} | " + " | ".join(cells) + " |")
    s += ["", "## By shock kind (detection / cause accuracy)", "", "| Kind | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    kinds = sorted({k for n in names for k in o["baselines"][n]["engine"]["by_kind"]})
    for k in kinds:
        cells = []
        for n in names:
            b = o["baselines"][n]["engine"]["by_kind"].get(k)
            if not b:
                cells.append("–")
                continue
            ca = "–" if b["cause_accuracy"] is None else f"{b['cause_accuracy']:.0%}"
            cells.append(f"n={b['n']}: {b['detection_rate']:.0%} / {ca}")
        s.append(f"| {k} | " + " | ".join(cells) + " |")
    s += ["", "## Where each model lost", ""] + notes(o) + ["", f"_{o['caveat']}_", ""]
    return "\n".join(s)


def notes(o: dict) -> list[str]:
    """One line per model on where it did worse, from by_kind and the forecast metrics."""
    names = list(o["baselines"])
    if len(names) < 2:
        return []
    label = {"lgbm": "LightGBM", "chronos_bolt": "Chronos-Bolt"}
    out = []
    for n in names:
        other = next(x for x in names if x != n)
        a, b = o["baselines"][n], o["baselines"][other]
        lost = []
        for key, what in (("wql", "quantile loss"), ("holiday_wape", "holidays (WAPE)")):
            if a["forecast"].get(key) is not None and b["forecast"].get(key) is not None and a["forecast"][key] > b["forecast"][key]:
                lost.append(f"{what} {a['forecast'][key]:.3f} vs {b['forecast'][key]:.3f}")
        for k, x in a["engine"]["by_kind"].items():
            y = b["engine"]["by_kind"].get(k)
            if y and x["cause_accuracy"] is not None and y["cause_accuracy"] is not None and x["cause_accuracy"] + 0.05 < y["cause_accuracy"]:
                lost.append(f"{k} cause {x['cause_accuracy']:.0%} vs {y['cause_accuracy']:.0%}")
        if (a["forecast"].get("latency_ms_p50") or 0) > (b["forecast"].get("latency_ms_p50") or 0):
            lost.append(f"latency p50 {a['forecast']['latency_ms_p50']} vs {b['forecast']['latency_ms_p50']} ms")
        out.append(f"- **{label.get(n, n)}** lost on: " + ("; ".join(lost) if lost else "nothing material") + ".")
    if "lgbm" in names:
        out.append("- LightGBM's p95 latency includes training a new model set the first time each monthly cut-off is used; "
                   "the app uses one cached model set (≈ 60 ms per call).")
    return out


if __name__ == "__main__":
    main()
