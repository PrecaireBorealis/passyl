"""Postgres connections (psycopg 3)."""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .config import DATABASE_URL

DSN = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")


@contextmanager
def conn():
    with psycopg.connect(DSN, row_factory=dict_row, autocommit=True) as c:
        yield c
