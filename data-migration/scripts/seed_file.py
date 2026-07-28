"""Generate orders CSV and ensure orders schema exists in the airflow DB."""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
from faker import Faker

HOST = os.getenv("POSTGRES_HOST", "postgres")
PORT = int(os.getenv("POSTGRES_PORT", "5432"))
USER = os.getenv("POSTGRES_USER", "postgres")
PASSWORD = os.getenv("POSTGRES_PASSWORD", "Rampoo@1981")
DEST_DB = os.getenv("DEST_DB", os.getenv("AIRFLOW_DB", "airflow"))
SOURCE_FILE = os.getenv("SOURCE_FILE", "/data/orders.csv")

TOTAL_DEFAULT = int(os.getenv("SEED_TOTAL", "150"))
PHASE_LIMITS = (50, 50, 50)

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

CSV_COLUMNS = [
    "id",
    "order_code",
    "customer_name",
    "email",
    "country",
    "product_sku",
    "quantity",
    "unit_price",
    "amount",
    "status",
    "order_ts",
    "created_at",
]

STATUSES = ["pending", "paid", "shipped", "delivered", "cancelled"]
COUNTRIES = [
    "US", "IN", "GB", "DE", "FR", "AU", "CA", "SG", "JP", "BR",
]


def connect(dbname: str):
    return psycopg2.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD, dbname=dbname
    )


def ensure_dest_schema() -> None:
    with connect(DEST_DB) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL_DEST)
            # Migrate old column name if present
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'migration_state' AND column_name = 'last_source_id'
                """
            )
            if cur.fetchone():
                cur.execute(
                    """
                    ALTER TABLE migration_state
                    RENAME COLUMN last_source_id TO last_file_id
                    """
                )
            for phase, expected in enumerate(PHASE_LIMITS, start=1):
                cur.execute(
                    """
                    INSERT INTO migration_state (phase, records_expected)
                    VALUES (%s, %s)
                    ON CONFLICT (phase) DO UPDATE
                    SET records_expected = EXCLUDED.records_expected
                    """,
                    (phase, expected),
                )
        conn.commit()


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        return sum(1 for _ in reader)


def seed(total: int, reset: bool) -> None:
    fake = Faker()
    Faker.seed(42)
    random.seed(42)

    ensure_dest_schema()

    path = Path(SOURCE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)

    if reset and path.exists():
        print(f"Removing existing file {path} ...")
        path.unlink()

    existing = count_csv_rows(path)
    if existing >= total:
        print(f"Source file already has {existing:,} rows (>= {total:,}). Skipping seed.")
        return

    print(f"Writing {total:,} rows to {path} ...")
    t0 = time.time()
    base_ts = datetime(2024, 1, 1)
    created_at = datetime.utcnow().replace(microsecond=0)

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for seq in range(1, total + 1):
            qty = random.randint(1, 20)
            price = round(random.uniform(5.0, 499.99), 2)
            order_ts = base_ts + timedelta(minutes=seq)
            writer.writerow(
                {
                    "id": seq,
                    "order_code": f"ORD-{seq:08d}",
                    "customer_name": fake.name(),
                    "email": fake.email(),
                    "country": random.choice(COUNTRIES),
                    "product_sku": f"SKU-{random.randint(1000, 9999)}",
                    "quantity": qty,
                    "unit_price": f"{price:.2f}",
                    "amount": f"{round(qty * price, 2):.2f}",
                    "status": random.choice(STATUSES),
                    "order_ts": order_ts.isoformat(sep=" "),
                    "created_at": created_at.isoformat(sep=" "),
                }
            )

    print(f"Seed complete: {total:,} rows in {time.time() - t0:.1f}s -> {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed orders CSV for file->DB migration")
    parser.add_argument("--total", type=int, default=TOTAL_DEFAULT)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Recreate the source CSV from scratch",
    )
    args = parser.parse_args()
    print(
        f"Postgres {HOST}:{PORT} dest={DEST_DB} file={SOURCE_FILE} total={args.total}"
    )
    seed(args.total, args.reset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
