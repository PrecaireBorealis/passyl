"""Optional: hand the action to an n8n workflow, which then calls the mock Paytm endpoints."""
import httpx

from ..config import env


def webhook_url() -> str:
    return env("N8N_WEBHOOK_URL")


def send(action: dict) -> dict:
    r = httpx.post(webhook_url(), json=action, timeout=6)
    r.raise_for_status()
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else {"status": r.status_code}
