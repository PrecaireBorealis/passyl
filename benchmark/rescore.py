"""Re-score saved cards with the current metrics code, without re-running the models.
python -m benchmark.rescore benchmark/results/cards_seed7.jsonl [--write]
--write updates the engine metrics in the matching benchmark*.json and report*.md (forecast metrics and
latency are kept from the original run)."""
import json
import sys
from pathlib import Path

from .run import report  # importing run also puts backend/ on sys.path
from . import metrics


def main() -> None:
    path = Path(sys.argv[1])
    rows = [json.loads(l) for l in open(path)]
    from app.engine.why import is_flagged
    engine = {}
    for name in sorted({r["baseline"] for r in rows}):
        rs = [r for r in rows if r["baseline"] == name]
        res = [{"kind": r["kind"], "true_effect_pct": r["true_effect_pct"], "card": r["card"],
                "flagged": is_flagged(r["card"]), "cause": metrics.top_cause(r["card"])} for r in rs]
        engine[name] = metrics.engine(res)
        print(name, json.dumps({k: v for k, v in engine[name].items() if k != "by_kind"}))
        for k, v in engine[name]["by_kind"].items():
            print(f"   {k:16s} {v}")
    if "--write" in sys.argv:
        tag = path.stem.removeprefix("cards")
        bj = path.with_name(f"benchmark{tag}.json")
        out = json.loads(bj.read_text())
        for name, e in engine.items():
            out["baselines"][name]["engine"] = e
        bj.write_text(json.dumps(out, indent=2, default=str))
        path.with_name(f"report{tag}.md").write_text(report(out))
        print(f"updated {bj.name} and report{tag}.md")


if __name__ == "__main__":
    main()
