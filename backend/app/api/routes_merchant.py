from datetime import date

from fastapi import APIRouter

from ..adapters.synthetic import get_adapter
from ..clock import today
from ..engine import brief as brief_mod
from ..engine import strategy, why
from ..engine.why import THIN_DAYS, history_days
from .errors import ApiError, not_found

router = APIRouter(prefix="/api/merchants", tags=["merchants"])


def _merchant(mid: str) -> dict:
    m = get_adapter().get_merchant(mid)
    if m is None:
        raise not_found("Merchant")
    return m


@router.get("")
def merchants():
    from ..config import DEMO_MERCHANT_ID
    m = get_adapter().list_merchants()
    demo = [DEMO_MERCHANT_ID, "M_KOR_CAF_NEW"]
    rows = m[m["id"].isin(demo)]
    return [{"id": r.id, "name": r.name, "category": r.category, "locality": r.locality_id,
             "history_days": history_days(r._asdict(), today())} for r in rows.itertuples()]


@router.get("/{mid}/summary")
def summary(mid: str, date: date | None = None):
    _merchant(mid)
    return why.summary(get_adapter(), mid, date or today())


@router.get("/{mid}/hourly")
def hourly(mid: str, date: date | None = None):
    _merchant(mid)
    return why.hourly_view(get_adapter(), mid, date or today())


@router.get("/{mid}/why")
def why_card(mid: str, date: date | None = None, start_hour: int | None = None, end_hour: int | None = None):
    _merchant(mid)
    try:
        return why.explain_change(get_adapter(), mid, date or today(), start_hour, end_hour)
    except ValueError as e:
        raise ApiError("NOT_FOUND", "Is waqt ka data abhi nahi aaya.", str(e), 400)


@router.get("/{mid}/strategies")
def strategies(mid: str, date: date | None = None):
    from ..actions import executor
    m = _merchant(mid)
    d = date or today()
    if history_days(m, d) < THIN_DAYS:
        raise ApiError("THIN_HISTORY", "Abhi itna data nahi ki offer ka andaaza laga sakein.",
                       "Not enough history yet to estimate offers.", 422)
    a = get_adapter()
    card = why.explain_change(a, mid, d)
    res = strategy.rank(a, mid, d, card)
    rec = next((o for o in res["options"] if o["id"] == res["recommended_id"]), None)
    res["draft_action_id"] = executor.create_draft(mid, rec)["id"] if rec else None
    return res


@router.get("/{mid}/brief")
def brief(mid: str, date: date | None = None):
    from datetime import timedelta
    _merchant(mid)
    return brief_mod.brief(get_adapter(), mid, date or today() + timedelta(days=1))
