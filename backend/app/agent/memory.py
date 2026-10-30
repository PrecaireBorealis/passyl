"""Per-merchant conversation state (in process) + durable merchant memory (DB) (spec 12.2)."""
from ..actions import store

_SESSIONS: dict[str, dict] = {}


def session(merchant_id: str) -> dict:
    return _SESSIONS.setdefault(merchant_id, {"lang": "hi-en", "last_why": None, "last_strategies": None,
                                              "pending_action_id": None, "live_action_id": None,
                                              "last_intent": None, "history": []})


def remember_turn(merchant_id: str, user: str, reply: str) -> None:
    s = session(merchant_id)
    s["history"] = (s["history"] + [{"user": user, "reply": reply}])[-6:]


def durable(merchant_id: str) -> dict:
    return store.get_memory(merchant_id)


def reset(merchant_ids: list[str] | None = None) -> None:
    for m in merchant_ids or list(_SESSIONS):
        _SESSIONS.pop(m, None)
