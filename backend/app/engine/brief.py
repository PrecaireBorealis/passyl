"""Morning brief: yesterday vs normal, last action vs holdout, today's outlook, next suggestion."""
from datetime import date, timedelta

from ..actions import store
from ..db import conn
from . import strategy, why


def last_ended_action(merchant_id: str) -> dict | None:
    with conn() as c:
        return c.execute("SELECT * FROM actions WHERE merchant_id = %s AND status = 'ended' ORDER BY created_at DESC LIMIT 1",
                         (merchant_id,)).fetchone()


def brief(adapter, merchant_id: str, d: date) -> dict:
    from ..actions.executor import measure
    m = adapter.get_merchant(merchant_id)
    y = d - timedelta(days=1)
    yesterday = why.summary(adapter, merchant_id, y, full_day=True)
    a = last_ended_action(merchant_id)
    result = measure(a["id"]) if a else None
    if result:
        result = {**result, "action_id": a["id"], "kind": a["kind"], "title_hi": a["expected"].get("title_hi")}

    w = adapter.get_weather(m["locality_id"], d, d)
    rainy = w[(w["precip_mm"] >= 1.0) & (w["hour"] >= 9)] if not w.empty else w
    weather_note = (None if w.empty else
                    f"Aaj {int(rainy['hour'].min()) % 12 or 12} baje ke aas-paas baarish ka anumaan." if len(rainy) else
                    "Aaj baarish ka anumaan nahi.")
    fest = adapter.get_festivals(d, d + timedelta(days=3))
    fest_note = None
    if not fest.empty:
        r = fest.iloc[0]
        when = "Aaj" if r["date"] == d else f"{(r['date'] - d).days} din baad"
        fest_note = f"{when} {r['name']} hai."

    suggestion = None
    try:
        opts = strategy.rank(adapter, merchant_id, d)["options"]
        done = a["kind"] if a else None
        suggestion = next((o for o in opts if o["kind"] != done and o["expected_profit"] > 0 and o["policy"]["passed"]), None)
    except Exception:  # a brief without a suggestion is still a brief
        suggestion = None
    return {"date": d.isoformat(), "yesterday": yesterday, "last_action_result": result,
            "today": {"weather_note_hi": weather_note, "festival_note_hi": fest_note}, "suggestion": suggestion,
            "data_label": "synthetic"}
