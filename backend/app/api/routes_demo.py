from fastapi import APIRouter

from ..actions import executor, store
from ..agent import memory
from ..config import DEMO_MERCHANT_ID

router = APIRouter(prefix="/api/demo", tags=["demo"])
DEMO_MERCHANTS = [DEMO_MERCHANT_ID, "M_KOR_CAF_NEW"]


@router.post("/reset")
def reset():
    store.reset(DEMO_MERCHANTS)
    memory.reset(DEMO_MERCHANTS)
    return {"status": "reset", "merchants": DEMO_MERCHANTS}


@router.post("/simulate/{aid}")
def simulate(aid: str):
    return executor.run_simulation(aid)
