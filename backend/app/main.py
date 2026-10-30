"""FastAPI app: uvicorn app.main:app --port 8000 (from backend/)."""
import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .actions import mock_paytm
from .actions.executor import ActionError
from .api import errors, routes_actions, routes_agent, routes_benchmark, routes_demo, routes_merchant, routes_voice

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="VyaparSaathi AI", version="1.1")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["*"], allow_headers=["*"])
app.add_exception_handler(errors.ApiError, errors.handler)
app.add_exception_handler(ActionError, errors.handler)
for r in (routes_merchant, routes_agent, routes_voice, routes_actions, routes_demo, routes_benchmark):
    app.include_router(r.router)
app.include_router(mock_paytm.router)


@app.get("/api/health")
def health():
    from .config import BASELINE_MODEL, OFFLINE_MODE
    from .agent.llm import provider
    from .config import env
    return {"ok": True, "baseline": BASELINE_MODEL, "llm": provider(), "offline": OFFLINE_MODE,
            "sarvam": bool(env("SARVAM_API_KEY")) and not OFFLINE_MODE}


@app.on_event("startup")
def warm():
    """Pre-compute the demo date so the first question is fast (Bolt can take seconds to load)."""
    def run():
        from .adapters.synthetic import get_adapter
        from .clock import today
        from .config import DEMO_MERCHANT_ID
        from .engine.why import explain_change, summary
        try:
            a = get_adapter()
            summary(a, DEMO_MERCHANT_ID, today())
            explain_change(a, DEMO_MERCHANT_ID, today())
            logging.info("warm-up done")
        except Exception as e:
            logging.warning("warm-up failed: %s", e)
    threading.Thread(target=run, daemon=True).start()
