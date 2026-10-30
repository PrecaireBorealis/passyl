# Shock-Injection Benchmark, seed 42

247 shock windows, 300 clean windows, 7 thin-history windows. App baseline: **lgbm**.

| Metric | lgbm | chronos_bolt |
|---|---|---|
| WAPE (p50), clean | 27.4% | 29.1% |
| Weighted quantile loss | 0.1967 | 0.1949 |
| p10–p90 coverage (nominal 80%) | 99.0% | 95.3% |
| Holiday WAPE | 46.4% | 44.9% |
| Latency p50 / p95 (ms) | 66 / 5795 | 395 / 610 |
| Detection rate | 82.2% | 85.8% |
| Cause accuracy (top-1) | 40.4% | 41.0% |
| Market split MAE (pts) | 22.92 | 17.56 |
| Range coverage (target ~80%) | 93.9% | 93.9% |
| False alarm rate | 23.0% | 25.0% |
| "I don't know" rate (thin history) | 100.0% | 100.0% |

## By shock kind (detection / cause accuracy)

| Kind | lgbm | chronos_bolt |
|---|---|---|
| bandh | n=14: 100% / 93% | n=14: 100% / 93% |
| competitor_open | n=10: 70% / 29% | n=10: 100% / 20% |
| festival | n=80: 100% / 64% | n=80: 95% / 68% |
| lapsed_regulars | n=15: 80% / 8% | n=15: 60% / 11% |
| payment_outage | n=8: 100% / 25% | n=8: 100% / 38% |
| rain | n=120: 68% / 16% | n=120: 79% / 17% |

## Where each model lost

- **LightGBM** lost on: quantile loss 0.197 vs 0.195; holidays (WAPE) 0.464 vs 0.449; payment_outage cause 25% vs 38%.
- **Chronos-Bolt** lost on: competitor_open cause 20% vs 29%; latency p50 395 vs 66 ms.
- LightGBM's p95 latency includes training a new model set the first time each monthly cut-off is used; the app uses one cached model set (≈ 60 ms per call).

_Synthetic data with planted causes. Tests the engine's logic, not real-world accuracy._
