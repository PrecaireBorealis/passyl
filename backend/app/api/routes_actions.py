from fastapi import APIRouter
from pydantic import BaseModel

from ..actions import executor

router = APIRouter(prefix="/api/actions", tags=["actions"])


class ApproveIn(BaseModel):
    actor: str = "merchant"


@router.post("/{aid}/approve")
def approve(aid: str, body: ApproveIn | None = None):
    from ..agent import memory
    live = executor.approve(aid, (body or ApproveIn()).actor)
    a = executor.store.get_action(aid)
    s = memory.session(a["merchant_id"])
    s["pending_action_id"], s["live_action_id"] = None, aid
    return live


@router.post("/{aid}/undo")
def undo(aid: str):
    return executor.undo(aid)


@router.get("/{aid}")
def get_action(aid: str):
    return executor.full_view(aid)


@router.get("/{aid}/measure")
def measure(aid: str):
    return executor.measure(aid)
