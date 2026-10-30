"""Tests run against the dev-seed database (seed 7), never the demo DB: the e2e test resets demo state."""
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://vs:vs@localhost:5432/vyaparsaathi_seed7")
os.environ["DATA_SEED"] = "7"
os.environ.setdefault("OFFLINE_MODE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
