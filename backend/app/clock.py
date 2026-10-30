"""The demo clock: the app runs on DEMO_NOW, never the real clock (spec 4.3)."""
from datetime import date, datetime

from .config import DEMO_NOW


def now() -> datetime:
    return datetime.fromisoformat(DEMO_NOW)


def today() -> date:
    return now().date()


def last_full_hour(d: date) -> int:
    """Hours < this are complete on date d (24 for past dates)."""
    return now().hour if d == today() else 24
