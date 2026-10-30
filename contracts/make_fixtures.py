"""Regenerate contracts/fixtures/*.json from the running API (real engine output, never hand-typed).
python contracts/make_fixtures.py   (API on :8000, demo DB loaded). Resets the demo merchants afterwards."""
import json
import shutil
from pathlib import Path

import httpx

API = "http://localhost:8000"
OUT = Path(__file__).parent / "fixtures"
M, THIN = "M_KOR_RES_001", "M_KOR_CAF_NEW"


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def main():
    c = httpx.Client(base_url=API, timeout=60)
    c.post("/api/demo/reset")
    save("summary.json", c.get(f"/api/merchants/{M}/summary").json())
    save("hourly.json", c.get(f"/api/merchants/{M}/hourly").json())
    save("why.json", c.get(f"/api/merchants/{M}/why").json())
    save("why_thin.json", c.get(f"/api/merchants/{THIN}/why").json())
    msg = lambda t: c.post("/api/agent/message", json={"merchant_id": M, "text": t, "channel": "chat"}).json()
    save("agent_response.json", msg("Bhai, aaj sales itni kam kyun hai?"))
    rec = msg("kya karun?")
    save("strategies.json", rec["cards"][0]["data"])
    live = msg("haan, kar do")["cards"][0]["data"]
    save("action_live.json", live)
    c.post(f"/api/demo/simulate/{live['id']}")
    save("measure.json", c.get(f"/api/actions/{live['id']}/measure").json())
    save("brief.json", c.get(f"/api/merchants/{M}/brief").json())
    b = c.get("/api/benchmark/latest")
    if b.status_code == 200:
        save("benchmark.json", b.json())
    c.post("/api/demo/reset")
    pub = Path(__file__).parents[1] / "frontend" / "public" / "fixtures"
    pub.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.json"):
        shutil.copy(f, pub / f.name)
    print("fixtures:", sorted(p.name for p in OUT.glob("*.json")))


if __name__ == "__main__":
    main()
