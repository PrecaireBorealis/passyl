"""reset → WHY → RECOMMEND → APPROVE → simulate → BRIEF; every number comes from the engine."""
from datetime import date

from fastapi.testclient import TestClient

from app.adapters.synthetic import get_adapter
from app.engine.why import explain_change
from app.main import app

M = "M_KOR_RES_001"


def say(c, text, m=M):
    r = c.post("/api/agent/message", json={"merchant_id": m, "text": text, "channel": "chat"})
    assert r.status_code == 200, r.text
    return r.json()


def test_demo_flow():
    with TestClient(app) as c:
        assert c.post("/api/demo/reset").status_code == 200
        assert c.get(f"/api/merchants/{M}/summary").status_code == 200
        w = say(c, "Bhai, aaj sales itni kam kyun hai?")
        assert w["intent"] == "WHY"
        card = w["cards"][0]["data"]
        engine = explain_change(get_adapter(), M, date(2026, 10, 30))
        assert card["split"] == engine["split"] and card["actual"] == engine["actual"]
        assert any(t["tool"] == "peer_shock" for t in w["trace"])

        rec = say(c, "kya karun?")
        assert rec["intent"] == "RECOMMEND" and rec["pending_action"]
        assert rec["cards"][0]["data"]["recommended_id"] == "combo_lapsed"

        ok = say(c, "Haan, kar do")
        assert ok["intent"] == "APPROVE"
        live = ok["cards"][0]["data"]
        assert live["status"] == "live" and live["n_treat"] > 0 and live["n_holdout"] > 0

        m = c.post(f"/api/demo/simulate/{live['id']}").json()
        assert m == c.get(f"/api/actions/{live['id']}/measure").json()
        b = c.get(f"/api/merchants/{M}/brief").json()
        assert b["last_action_result"]["incremental_profit"] == m["incremental_profit"]
        assert say(c, "aaj ka report")["intent"] == "BRIEF"


def test_thin_history_says_idk():
    with TestClient(app) as c:
        r = say(c, "aaj sales kam kyun hai?", "M_KOR_CAF_NEW")
        assert r["cards"][0]["data"]["confidence"]["state"] == "thin_history"
