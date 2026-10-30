"""Settings from the environment (and the repo-root .env, if present)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.split("#", 1)[0].strip() if not line.lstrip().startswith("#") else ""
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_env()


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default) or default


DATABASE_URL = env("DATABASE_URL", "postgresql+psycopg://vs:vs@localhost:5432/vyaparsaathi")
DEMO_NOW = env("DEMO_NOW", "2026-10-30T20:05:00+05:30")
DEMO_MERCHANT_ID = env("DEMO_MERCHANT_ID", "M_KOR_RES_001")
BASELINE_MODEL = env("BASELINE_MODEL", "lgbm")
CHRONOS_MODEL = env("CHRONOS_MODEL", "amazon/chronos-bolt-small")
CHRONOS_DEVICE = env("CHRONOS_DEVICE", "cpu")
OFFLINE_MODE = env("OFFLINE_MODE", "0") == "1"
DATA_SEED = env("DATA_SEED", "42")
MODELS_DIR = ROOT / "backend" / "models" / f"seed_{DATA_SEED}"  # trained models belong to one dataset
SCENARIO = ROOT / "generator" / "config" / "scenarios" / "raju_demo.yaml"
EFFECTS = ROOT / "generator" / "config" / "effects.yaml"
