# Shock-Injection Benchmark, seed 7

247 shock windows, 300 clean windows, 10 thin-history windows. App baseline: **lgbm**.

| Metric | lgbm | chronos_bolt |
|---|---|---|
| WAPE (p50), clean | 24.9% | 27.2% |
| Weighted quantile loss | 0.1841 | 0.1885 |
| p10–p90 coverage (nominal 80%) | 97.7% | 95.0% |
| Holiday WAPE | 20.3% | 16.9% |
| Latency p50 / p95 (ms) | 54 / 80 | 363 / 536 |
| Detection rate | 82.2% | 82.6% |
| Cause accuracy (top-1) | 43.4% | 38.2% |
| Market split MAE (pts) | 10.08 | 12.1 |
| Range coverage (target ~80%) | 96.5% | 96.5% |
| False alarm rate | 23.0% | 29.0% |
| "I don't know" rate (thin history) | 100.0% | 100.0% |

## By shock kind (detection / cause accuracy)

| Kind | lgbm | chronos_bolt |
|---|---|---|
| bandh | n=14: 93% / 100% | n=14: 93% / 100% |
| competitor_open | n=10: 70% / 71% | n=10: 80% / 25% |
| festival | n=80: 100% / 62% | n=80: 98% / 56% |
| lapsed_regulars | n=15: 67% / 30% | n=15: 73% / 9% |
| payment_outage | n=8: 100% / 50% | n=8: 100% / 50% |
| rain | n=120: 71% / 15% | n=120: 72% / 16% |

## Where each model lost

- **LightGBM** lost on: holidays (WAPE) 0.203 vs 0.169.
- **Chronos-Bolt** lost on: quantile loss 0.189 vs 0.184; competitor_open cause 25% vs 71%; festival cause 56% vs 62%; lapsed_regulars cause 9% vs 30%; latency p50 363 vs 54 ms.
- LightGBM's p95 latency includes training a new model set the first time each monthly cut-off is used; the app uses one cached model set (≈ 60 ms per call).

_Synthetic data with planted causes. Tests the engine's logic, not real-world accuracy._
