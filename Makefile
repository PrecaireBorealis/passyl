# All targets run from the repo root. Seed 42 = demo + test, seed 7 = dev/tuning (separate DB).
PY := .venv/bin/python
SEED ?= 42
DEV_DB := postgresql+psycopg://vs:vs@localhost:5432/vyaparsaathi_seed7

.PHONY: data models api web bench bench-dev test demo-reset demo-check fixtures

data:          ## build + load the dataset (≈ 4 min)
	$(PY) -m generator.build_dataset --seed $(SEED)
	$(PY) -m generator.load_db --seed $(SEED)

models:        ## train LightGBM for the demo date; Bolt weights must be cached (--prefetch-bolt, online, once)
	cd backend && ../$(PY) -m app.engine.baseline --train-lgbm

api:
	cd backend && HF_HUB_OFFLINE=1 ../.venv/bin/uvicorn app.main:app --port 8000

web:
	cd frontend && npm run build && npm run start

bench:         ## held-out benchmark on seed 42 with the app baseline frozen from seed 7
	HF_HUB_OFFLINE=1 OFFLINE_MODE=1 $(PY) -m benchmark.run --seed 42 --app-baseline $$(grep ^BASELINE_MODEL .env | cut -d= -f2 | cut -d' ' -f1)

bench-dev:     ## choose the app baseline on seed 7
	DATABASE_URL=$(DEV_DB) DATA_SEED=7 HF_HUB_OFFLINE=1 OFFLINE_MODE=1 $(PY) -m benchmark.run --seed 7

test:
	cd backend && ../$(PY) -m pytest -q

demo-reset:
	curl -s -XPOST localhost:8000/api/demo/reset

demo-check:    ## e2e test + demo targets through the real engine
	cd backend && ../$(PY) -m pytest -q tests/test_e2e_demo.py
	HF_HUB_OFFLINE=1 $(PY) -m generator.check_demo

fixtures:
	$(PY) contracts/make_fixtures.py
