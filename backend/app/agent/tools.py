"""Read-only tools for the agent (spec 12.3). Write tools are never exposed to the LLM."""
from datetime import date, timedelta

from ..adapters.synthetic import get_adapter
from ..engine import context, strategy, why

SCHEMAS = [
    {"name": "get_summary", "description": "Today's sales vs a normal same weekday for the merchant",
     "input_schema": {"type": "object", "properties": {"merchant_id": {"type": "string"}, "date": {"type": "string"}},
                      "required": ["merchant_id", "date"]}},
    {"name": "explain_change", "description": "Why-Engine: split a sales change into market-wide vs shop-specific, with causes and ranges",
     "input_schema": {"type": "object", "properties": {"merchant_id": {"type": "string"}, "date": {"type": "string"},
                                                       "start_hour": {"type": "integer"}, "end_hour": {"type": "integer"}},
                      "required": ["merchant_id", "date"]}},
    {"name": "rank_strategies", "description": "Rank possible actions by expected incremental profit; includes policy checks",
     "input_schema": {"type": "object", "properties": {"merchant_id": {"type": "string"}, "date": {"type": "string"}},
                      "required": ["merchant_id", "date"]}},
    {"name": "get_weather", "description": "Hourly rain and temperature for the merchant's area (past or forecast)",
     "input_schema": {"type": "object", "properties": {"merchant_id": {"type": "string"}, "date": {"type": "string"}},
                      "required": ["merchant_id", "date"]}},
    {"name": "get_calendar", "description": "Festivals and holidays near a date, with expected effect for this category",
     "input_schema": {"type": "object", "properties": {"merchant_id": {"type": "string"}, "date": {"type": "string"},
                                                       "days_ahead": {"type": "integer"}}, "required": ["merchant_id", "date"]}},
    {"name": "get_customer_stats", "description": "Regular / new / lapsed customer counts for a window",
     "input_schema": {"type": "object", "properties": {"merchant_id": {"type": "string"}, "date": {"type": "string"},
                                                       "start_hour": {"type": "integer"}, "end_hour": {"type": "integer"}},
                      "required": ["merchant_id", "date"]}},
]


def get_summary(merchant_id: str, date: str) -> dict:
    return why.summary(get_adapter(), merchant_id, _d(date))


def explain_change(merchant_id: str, date: str, start_hour: int | None = None, end_hour: int | None = None, trace=None) -> dict:
    kw = {"trace": trace} if trace else {}
    return why.explain_change(get_adapter(), merchant_id, _d(date), start_hour, end_hour, **kw)


def rank_strategies(merchant_id: str, date: str, why_card: dict | None = None) -> dict:
    return strategy.rank(get_adapter(), merchant_id, _d(date), why_card)


def get_weather(merchant_id: str, date: str) -> dict:
    a = get_adapter()
    m = a.get_merchant(merchant_id)
    w = a.get_weather(m["locality_id"], _d(date), _d(date))
    if w.empty:
        return {"date": date, "hours": [], "note": "no weather data for this date"}
    return {"date": date, "hours": [{"hour": int(r.hour), "precip_mm": float(r.precip_mm), "temp_c": float(r.temp_c)}
                                    for r in w.itertuples()]}


def get_calendar(merchant_id: str, date: str, days_ahead: int = 7) -> dict:
    a = get_adapter()
    m = a.get_merchant(merchant_id)
    d = _d(date)
    f = a.get_festivals(d, d + timedelta(days=days_ahead))
    fx = context.festival_effects().get(m["category"]) or {}
    return {"festivals": [{"date": str(r.date), "name": r.name, "scope": r.scope,
                           "expected_mult": fx.get(r.name, {}).get("mult")} for r in f.itertuples()]}


def get_customer_stats(merchant_id: str, date: str, start_hour: int = 0, end_hour: int = 24) -> dict:
    a = get_adapter()
    d = _d(date)
    h = a.get_hourly([merchant_id], d, d)
    h = h[(h["hour"] >= start_hour) & (h["hour"] < end_hour)]
    seg = strategy.lapsed_segment(a, merchant_id, d)
    return {"regular_txns": int(h["regular_txns"].sum()), "new_txns": int(h["new_txns"].sum()),
            "bills": int(h["success_txns"].sum()), "lapsed_customers": int(len(seg)),
            "lapsed_opted_in": int(seg["opted_in"].sum()) if len(seg) else 0}


READ_ONLY = {f.__name__: f for f in (get_summary, explain_change, rank_strategies, get_weather, get_calendar, get_customer_stats)}


def run(name: str, args: dict) -> dict:
    if name not in READ_ONLY:
        return {"error": f"unknown tool {name}"}
    try:
        return READ_ONLY[name](**args)
    except Exception as e:  # tool errors go back to the model as data
        return {"error": str(e)}


def _d(s) -> date:
    return s if isinstance(s, date) else date.fromisoformat(str(s)[:10])
