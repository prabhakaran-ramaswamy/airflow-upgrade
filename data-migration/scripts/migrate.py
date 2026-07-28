"""Phased migration: orders CSV file -> airflow.orders (same DB as metadata)."""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

HOST = os.getenv("POSTGRES_HOST", "postgres")
PORT = int(os.getenv("POSTGRES_PORT", "5432"))
USER = os.getenv("POSTGRES_USER", "postgres")
PASSWORD = os.getenv("POSTGRES_PASSWORD", "Rampoo@1981")
DEST_DB = os.getenv("DEST_DB", os.getenv("AIRFLOW_DB", "airflow"))
SOURCE_FILE = os.getenv("SOURCE_FILE", "/data/orders.csv")

PHASE_LIMITS = {
    1: 50,  # Airflow 2.5.2
    2: 50,  # Airflow 2.11.2
    3: 50,  # Airflow 3.3
}
BATCH_DEFAULT = 50


def connect(dbname: str):
    return psycopg2.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD, dbname=dbname
    )


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        return sum(1 for _ in reader)


def show_status() -> None:
    path = Path(SOURCE_FILE)
    file_count = count_csv_rows(path)

    with connect(DEST_DB) as dst:
        with dst.cursor() as dc:
            dc.execute("SELECT COUNT(*), COALESCE(MAX(id),0) FROM orders")
            dst_count, dst_max = dc.fetchone()
            dc.execute(
                """
                SELECT phase, records_expected, records_migrated,
                       last_file_id, started_at, completed_at
                FROM migration_state
                ORDER BY phase
                """
            )
            phases = dc.fetchall()

    print(f"Source file ({SOURCE_FILE}): {file_count:,} rows")
    print(f"Dest   ({DEST_DB}.orders):   {dst_count:,} rows (max id={dst_max})")
    print("\nPhase progress:")
    for phase, expected, migrated, last_id, started, completed in phases:
        flag = "DONE" if completed else ("RUNNING" if started else "PENDING")
        print(
            f"  phase {phase}: {migrated:,}/{expected:,}  "
            f"last_id={last_id}  [{flag}]"
        )


def iter_rows_after(path: Path, last_id: int, limit: int):
    """Yield up to `limit` CSV rows with id > last_id (ordered by id)."""
    yielded = 0
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row_id = int(row["id"])
            if row_id <= last_id:
                continue
            yield (
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
            yielded += 1
            if yielded >= limit:
                return


def migrate_phase(phase: int, batch_size: int) -> None:
    if phase not in PHASE_LIMITS:
        raise SystemExit(f"Invalid phase {phase}; expected 1, 2, or 3")

    path = Path(SOURCE_FILE)
    if not path.exists():
        raise SystemExit(f"Source file missing: {path}. Run seed first.")

    expected = PHASE_LIMITS[phase]
    print(f"=== Migration phase {phase}: up to {expected:,} records from file ===")

    with connect(DEST_DB) as dst:
        with dst.cursor() as dc:
            dc.execute(
                "SELECT records_migrated, last_file_id, completed_at "
                "FROM migration_state WHERE phase = %s",
                (phase,),
            )
            row = dc.fetchone()
            if not row:
                raise SystemExit(
                    "migration_state missing; run seed first to create schemas"
                )
            already, last_id, completed = row
            if completed:
                print(f"Phase {phase} already completed ({already:,} rows). Skipping.")
                return

            if phase > 1:
                dc.execute(
                    "SELECT completed_at, last_file_id FROM migration_state "
                    "WHERE phase = %s",
                    (phase - 1,),
                )
                prev = dc.fetchone()
                if not prev or not prev[0]:
                    raise SystemExit(
                        f"Phase {phase - 1} must complete before phase {phase}"
                    )
                # Continue from prior phase's file cursor when this phase is fresh
                if last_id == 0:
                    last_id = prev[1]

            dc.execute(
                """
                UPDATE migration_state
                SET started_at = COALESCE(started_at, NOW()),
                    last_file_id = %s
                WHERE phase = %s
                """,
                (last_id, phase),
            )
        dst.commit()

    remaining = expected - already
    if remaining <= 0:
        print(f"Phase {phase} already at target ({already:,}). Marking complete.")
        with connect(DEST_DB) as dst:
            with dst.cursor() as dc:
                dc.execute(
                    "UPDATE migration_state SET completed_at = NOW() WHERE phase = %s",
                    (phase,),
                )
            dst.commit()
        return

    print(f"Already migrated this phase: {already:,}; remaining: {remaining:,}")
    print(f"Continuing after file id > {last_id}")

    t0 = time.time()
    migrated_now = 0

    while migrated_now < remaining:
        chunk = min(batch_size, remaining - migrated_now)
        rows = list(iter_rows_after(path, last_id, chunk))

        if not rows:
            raise SystemExit(
                f"Source file exhausted before phase {phase} target "
                f"({already + migrated_now:,}/{expected:,}). Seed more data."
            )

        values = [
            (
                r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8],
                r[9], r[10], r[11], phase,
            )
            for r in rows
        ]
        new_last = rows[-1][0]

        with connect(DEST_DB) as dst:
            with dst.cursor() as dc:
                execute_values(
                    dc,
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
                migrated_now += len(rows)
                already_total = already + migrated_now
                dc.execute(
                    """
                    UPDATE migration_state
                    SET records_migrated = %s,
                        last_file_id = %s
                    WHERE phase = %s
                    """,
                    (already_total, new_last, phase),
                )
            dst.commit()

        last_id = new_last
        elapsed = time.time() - t0
        rate = migrated_now / elapsed if elapsed else 0
        print(
            f"  phase {phase}: {already + migrated_now:,}/{expected:,} "
            f"(last_id={last_id}, {rate:,.0f} rows/s)"
        )

    with connect(DEST_DB) as dst:
        with dst.cursor() as dc:
            dc.execute(
                """
                UPDATE migration_state
                SET records_migrated = %s,
                    last_file_id = %s,
                    completed_at = NOW(),
                    notes = %s
                WHERE phase = %s
                """,
                (
                    expected,
                    last_id,
                    f"Completed phase {phase} (file -> {DEST_DB})",
                    phase,
                ),
            )
        dst.commit()

    print(f"Phase {phase} complete in {time.time() - t0:.1f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phased file->DB data migration")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3])
    parser.add_argument("--batch-size", type=int, default=BATCH_DEFAULT)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status or args.phase is None:
        show_status()
        if args.phase is None and not args.status:
            return 0
        if args.status and args.phase is None:
            return 0

    migrate_phase(args.phase, args.batch_size)
    print()
    show_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
