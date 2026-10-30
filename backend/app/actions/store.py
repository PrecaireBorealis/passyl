"""App-state tables: actions, action_targets, audit_log, merchant_memory."""
import json
from datetime import datetime

from psycopg.types.json import Jsonb

from ..clock import now
from ..db import conn


def audit(merchant_id: str, actor: str, event: str, payload: dict) -> None:
    with conn() as c:
        c.execute("INSERT INTO audit_log(ts, merchant_id, actor, event, payload) VALUES (%s, %s, %s, %s, %s)",
                  (now(), merchant_id, actor, event, Jsonb(payload)))


def insert_action(a: dict) -> None:
    with conn() as c:
        c.execute("INSERT INTO actions(id, merchant_id, kind, params, status, created_at, window_start, window_end, "
                  "expected, policy) VALUES (%(id)s, %(merchant_id)s, %(kind)s, %(params)s, %(status)s, %(created_at)s, "
                  "%(window_start)s, %(window_end)s, %(expected)s, %(policy)s)",
                  {**a, "params": Jsonb(a["params"]), "expected": Jsonb(a["expected"]), "policy": Jsonb(a["policy"])})


def update_action(action_id: str, **fields) -> None:
    sets, vals = [], []
    for k, v in fields.items():
        sets.append(f"{k} = %s")
        vals.append(Jsonb(v) if isinstance(v, (dict, list)) else v)
    with conn() as c:
        c.execute(f"UPDATE actions SET {', '.join(sets)} WHERE id = %s", (*vals, action_id))


def get_action(action_id: str) -> dict | None:
    with conn() as c:
        return c.execute("SELECT * FROM actions WHERE id = %s", (action_id,)).fetchone()


def latest_action(merchant_id: str, statuses: tuple[str, ...]) -> dict | None:
    with conn() as c:
        return c.execute("SELECT * FROM actions WHERE merchant_id = %s AND status = ANY(%s) ORDER BY created_at DESC, id DESC "
                         "LIMIT 1", (merchant_id, list(statuses))).fetchone()


def insert_targets(action_id: str, rows: list[dict]) -> None:
    with conn() as c, c.cursor().copy("COPY action_targets(action_id, payer_hash, arm) FROM STDIN") as cp:
        for r in rows:
            cp.write_row((action_id, r["payer_hash"], r["arm"]))


def get_targets(action_id: str) -> list[dict]:
    with conn() as c:
        return c.execute("SELECT * FROM action_targets WHERE action_id = %s ORDER BY payer_hash", (action_id,)).fetchall()


def set_target_results(action_id: str, rows: list[dict]) -> None:
    with conn() as c:
        c.cursor().executemany("UPDATE action_targets SET returned = %s, spend = %s WHERE action_id = %s AND payer_hash = %s",
                               [(r["returned"], r["spend"], action_id, r["payer_hash"]) for r in rows])


def get_memory(merchant_id: str) -> dict:
    with conn() as c:
        rows = c.execute("SELECT key, value FROM merchant_memory WHERE merchant_id = %s", (merchant_id,)).fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_memory(merchant_id: str, key: str, value) -> None:
    with conn() as c:
        c.execute("INSERT INTO merchant_memory(merchant_id, key, value, updated_at) VALUES (%s, %s, %s, %s) "
                  "ON CONFLICT (merchant_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
                  (merchant_id, key, Jsonb(value), now()))


def reset(merchant_ids: list[str]) -> None:
    with conn() as c:
        c.execute("DELETE FROM action_targets WHERE action_id IN (SELECT id FROM actions WHERE merchant_id = ANY(%s))",
                  (merchant_ids,))
        for t in ("actions", "audit_log", "merchant_memory"):
            c.execute(f"DELETE FROM {t} WHERE merchant_id = ANY(%s)", (merchant_ids,))
