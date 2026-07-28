"""Load the next 50 orders from CSV into the shared airflow DB.

Trigger this DAG once per upgrade stage (3 runs total = 150 rows):
  Run 1 (Airflow 2.5.2)  -> rows 1-50
  Run 2 (Airflow 2.11.2) -> rows 51-100
  Run 3 (Airflow 3.3)    -> rows 101-150

Each run inserts only the next BATCH_SIZE rows after MAX(id) already in the DB.
Orders live in the same Postgres database as Airflow metadata (`airflow`).
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from airflow import DAG
from airflow.operators.python import PythonOperator

BATCH_SIZE = 50
HOST = os.getenv("POSTGRES_HOST", "postgres")
PORT = int(os.getenv("POSTGRES_PORT", "5432"))
USER = os.getenv("POSTGRES_USER", "postgres")
PASSWORD = os.getenv("POSTGRES_PASSWORD", "Rampoo@1981")
DEST_DB = os.getenv("DEST_DB", os.getenv("AIRFLOW_DB", "airflow"))
SOURCE_FILE = os.getenv("SOURCE_FILE", "/data/orders.csv")

DDL_DEST = """
CREATE TABLE IF NOT EXISTS orders (
    id              BIGINT       PRIMARY KEY,
    order_code      VARCHAR(64)  NOT NULL UNIQUE,
    customer_name   VARCHAR(255) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    country         VARCHAR(64)  NOT NULL,
    product_sku     VARCHAR(64)  NOT NULL,
    quantity        INTEGER      NOT NULL,
    unit_price      NUMERIC(12,2) NOT NULL,
    amount          NUMERIC(14,2) NOT NULL,
    status          VARCHAR(32)  NOT NULL,
    order_ts        TIMESTAMP    NOT NULL,
    created_at      TIMESTAMP    NOT NULL,
    migration_phase INTEGER      NOT NULL,
    migrated_at     TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dest_orders_phase ON orders (migration_phase);

CREATE TABLE IF NOT EXISTS migration_state (
    phase              INTEGER PRIMARY KEY,
    records_expected   BIGINT  NOT NULL,
    records_migrated   BIGINT  NOT NULL DEFAULT 0,
    last_file_id       BIGINT  NOT NULL DEFAULT 0,
    started_at         TIMESTAMP,
    completed_at       TIMESTAMP,
    notes              TEXT
);
"""


def _connect():
    return psycopg2.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD, dbname=DEST_DB
    )


def _ensure_schema(cur) -> None:
    cur.execute(DDL_DEST)
    for phase in (1, 2, 3):
        cur.execute(
            """
            INSERT INTO migration_state (phase, records_expected)
            VALUES (%s, %s)
            ON CONFLICT (phase) DO NOTHING
            """,
            (phase, BATCH_SIZE),
        )


def _next_rows(path: Path, after_id: int, limit: int):
    rows = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row_id = int(row["id"])
            if row_id <= after_id:
                continue
            rows.append(
                (
                    row_id,
                    row["order_code"],
                    row["customer_name"],
                    row["email"],
                    row["country"],
                    row["product_sku"],
                    int(row["quantity"]),
                    row["unit_price"],
                    row["amount"],
                    row["status"],
                    row["order_ts"],
                    row["created_at"],
                )
            )
            if len(rows) >= limit:
                break
    return rows


def load_next_50_from_file():
    path = Path(SOURCE_FILE)
    if not path.exists():
        raise FileNotFoundError(
            f"Source file not found: {path}. Run scripts\\00-prepare-data.bat first."
        )

    with _connect() as conn:
        with conn.cursor() as cur:
            _ensure_schema(cur)
            cur.execute("SELECT COALESCE(MAX(id), 0), COUNT(*) FROM orders")
            last_id, already = cur.fetchone()
            phase = (already // BATCH_SIZE) + 1
            if phase > 3:
                print(
                    f"All 150 rows already loaded ({already} in {DEST_DB}.orders). Nothing to do."
                )
                conn.commit()
                return

            cur.execute(
                """
                UPDATE migration_state
                SET started_at = COALESCE(started_at, NOW())
                WHERE phase = %s
                """,
                (phase,),
            )

            rows = _next_rows(path, last_id, BATCH_SIZE)
            if not rows:
                raise RuntimeError(
                    f"No rows in {path} after id={last_id}. Seed the CSV first."
                )
            if len(rows) < BATCH_SIZE:
                print(
                    f"Warning: only {len(rows)} rows available (expected {BATCH_SIZE})"
                )

            values = [(*r, phase) for r in rows]
            execute_values(
                cur,
                """
                INSERT INTO orders (
                    id, order_code, customer_name, email, country,
                    product_sku, quantity, unit_price, amount,
                    status, order_ts, created_at, migration_phase
                ) VALUES %s
                ON CONFLICT (id) DO NOTHING
                """,
                values,
                page_size=len(values),
            )
            new_last = rows[-1][0]
            cur.execute(
                """
                UPDATE migration_state
                SET records_migrated = %s,
                    last_file_id = %s,
                    completed_at = NOW(),
                    notes = %s
                WHERE phase = %s
                """,
                (
                    len(rows),
                    new_last,
                    f"Loaded by Airflow DAG file_to_destination (phase {phase})",
                    phase,
                ),
            )
        conn.commit()

    print(
        f"Loaded {len(rows)} rows from {SOURCE_FILE} -> {DEST_DB}.orders "
        f"(phase={phase}, ids {rows[0][0]}-{rows[-1][0]})"
    )


import inspect

_dag_kwargs = {
    "dag_id": "file_to_destination",
    "start_date": datetime(2024, 1, 1),
    "catchup": False,
    "tags": ["upgrade", "file-load"],
    "doc_md": __doc__,
}
if "schedule" in inspect.signature(DAG.__init__).parameters:
    _dag_kwargs["schedule"] = None
else:
    _dag_kwargs["schedule_interval"] = None

with DAG(**_dag_kwargs) as dag:
    PythonOperator(
        task_id="load_next_50",
        python_callable=load_next_50_from_file,
    )
