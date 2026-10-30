# VyaparSaathi AI

AI growth partner for Paytm merchants: explains a sales drop (Peer-Shock Test), ranks actions by expected profit,
executes inside guardrails, and measures against a holdout. Spec: `docs/SPEC.md`. All transaction data is synthetic.

```
make data                     # build + load seed 42 into Postgres (DATABASE_URL in .env), ~4 min
cd backend && ../.venv/bin/python -m app.engine.baseline --prefetch-bolt   # once, online
make models                   # LightGBM for the demo date (~40 s)
make api                      # :8000
make web                      # :3000  (open http://localhost:3000/?demo=1 for presenter controls)
make test && make demo-check  # unit + e2e tests (seed-7 DB) and demo targets through the engine
make bench-dev && make bench  # choose the baseline on seed 7, then the held-out seed-42 benchmark
```

Python env: `uv venv .venv && uv pip install -e backend` (CPU torch: `--index-url https://download.pytorch.org/whl/cpu torch`).
No LLM or Sarvam key → replies come from templates and voice uses the browser's speech; the trace says which.
