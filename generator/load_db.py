"""data/generated/seed_N/*.parquet → Postgres (COPY). python -m generator.load_db [--seed 42]  (DATABASE_URL picks the DB)"""
import argparse
import io
import json
import os
import time

import pandas as pd
import psycopg

from .common import GEN, ROOT

TABLES = ["localities", "merchants", "merchant_policy", "products", "customers", "transactions", "hourly",
          "weather_hourly", "festivals", "disruptions", "past_campaigns", "shock_labels"]
INDEXES = ["CREATE INDEX ON transactions(merchant_id, ts)", "CREATE INDEX ON weather_hourly(locality_id, ts)",
           "CREATE INDEX ON hourly(date)", "CREATE INDEX ON festivals(date)", "CREATE INDEX ON action_targets(action_id)"]


def dsn() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql+psycopg://vs:vs@localhost:5432/vyaparsaathi")
    return url.replace("postgresql+psycopg://", "postgresql://")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=int(os.environ.get("DATA_SEED", 42)))
    ap.add_argument("--tables", help="comma list: reload only these tables (no schema reset)")
    ap.add_argument("--merchant", help="with --tables: replace only this merchant's rows")
    a = ap.parse_args()
    src = GEN / f"seed_{a.seed}"
    t0 = time.time()
    with psycopg.connect(dsn()) as con:
        tables = a.tables.split(",") if a.tables else TABLES
        if not a.tables:
            con.execute((ROOT / "generator" / "schema.sql").read_text())
        for t in tables:
            df = pd.read_parquet(src / f"{t}.parquet")
            if a.tables and a.merchant:
                df = df[df["merchant_id"] == a.merchant]
                con.execute(f"DELETE FROM {t} WHERE merchant_id = %s", (a.merchant,))
            elif a.tables:
                con.execute(f"DELETE FROM {t}")
            cols = [r[0] for r in con.execute(f"SELECT column_name FROM information_schema.columns "
                                              f"WHERE table_name = %s ORDER BY ordinal_position", (t,))]
            df = df[[c for c in cols if c in df.columns]]
            buf = io.StringIO()
            df.to_csv(buf, index=False, header=False)
            buf.seek(0)
            with con.cursor().copy(f"COPY {t} ({', '.join(df.columns)}) FROM STDIN WITH (FORMAT csv)") as cp:
                while chunk := buf.read(1 << 20):
                    cp.write(chunk)
            print(f"  {t}: {len(df):,} rows")
        if not a.tables:
            for ix in INDEXES:
                con.execute(ix)
        con.execute("ANALYZE")
    meta = json.loads((src / "meta.json").read_text())
    print(f"loaded seed {meta['seed']} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
