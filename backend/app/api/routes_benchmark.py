import json

from fastapi import APIRouter

from ..config import ROOT
from .errors import not_found

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


@router.get("/latest")
def latest():
    f = ROOT / "benchmark" / "results" / "benchmark.json"
    if not f.exists():
        raise not_found("Benchmark result")
    return json.loads(f.read_text())
