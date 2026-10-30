from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from ..agent.orchestrator import handle
from .errors import not_found

router = APIRouter(prefix="/api/agent", tags=["agent"])


class MessageIn(BaseModel):
    merchant_id: str
    text: str
    lang: str | None = None
    channel: Literal["chat", "voice"] = "chat"


@router.post("/message")
def message(m: MessageIn):
    try:
        return handle(m.text, m.merchant_id, m.lang, m.channel)
    except KeyError:
        raise not_found("Merchant")
