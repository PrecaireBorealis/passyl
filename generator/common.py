"""Shared paths and config loading for the generator."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "data" / "reference"
GEN = ROOT / "data" / "generated"
CFG = Path(__file__).resolve().parent / "config"


def load(name: str) -> dict:
    return yaml.safe_load((CFG / name).read_text())
