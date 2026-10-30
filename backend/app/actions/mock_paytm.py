"""Simulated Paytm action API (/mock-paytm/*). Logs only: no real offers or messages."""
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from ..clock import now
from . import store

router = APIRouter(prefix="/mock-paytm", tags=["mock-paytm"])


class OfferIn(BaseModel):
    merchant_id: str
    product_id: str
    discount: int
    valid_from: str
    valid_to: str


class MessageIn(BaseModel):
    merchant_id: str
    payer_hashes: list[str]
    template_id: str
    text: str


def create_offer(o: dict) -> dict:
    oid = "OF_" + uuid.uuid4().hex[:10]
    store.audit(o["merchant_id"], "mock_paytm", "offer_created", {**o, "offer_id": oid})
    return {"offer_id": oid, "status": "created"}


def send_message(m: dict) -> dict:
    store.audit(m["merchant_id"], "mock_paytm", "messages_sent",
                {"template_id": m["template_id"], "text": m["text"], "n": len(m["payer_hashes"])})
    return {"queued": len(m["payer_hashes"])}


def cancel_offer(merchant_id: str, offer_id: str) -> dict:
    store.audit(merchant_id, "mock_paytm", "offer_cancelled", {"offer_id": offer_id})
    return {"status": "cancelled"}


@router.post("/offers")
def post_offer(o: OfferIn):
    return create_offer(o.model_dump())


@router.post("/messages")
def post_messages(m: MessageIn):
    return send_message(m.model_dump())


@router.delete("/offers/{offer_id}")
def delete_offer(offer_id: str, merchant_id: str = ""):
    return cancel_offer(merchant_id, offer_id)
