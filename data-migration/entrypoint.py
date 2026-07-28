#!/usr/bin/env python3
"""Entrypoint for data-ops image."""
from __future__ import annotations

import subprocess
import sys

HELP = """
Data migration image commands:

  init-db              Create shared airflow DB (metadata + orders)
  seed                 Write 150 order rows to /data/orders.csv (+ orders schema)
  migrate --phase N    Load records from file into airflow.orders (1|2|3)
  status               Show file/destination counts and migration progress

Phases (file -> airflow.orders):
  1  -> 50 records  (while on Airflow 2.5.2)
  2  -> 50 records  (after upgrade to Airflow 2.11.2)
  3  -> 50 records  (after upgrade to Airflow 3.3)
"""


def main(argv: list[str]) -> int:
    if not argv:
        print(HELP)
        return 0

    cmd, *rest = argv
    mapping = {
        "init-db": ["python", "/app/scripts/init_databases.py"],
        "seed": ["python", "/app/scripts/seed_file.py"],
        "migrate": ["python", "/app/scripts/migrate.py"],
        "status": ["python", "/app/scripts/migrate.py", "--status"],
        "help": None,
        "--help": None,
        "-h": None,
    }

    if cmd in ("help", "--help", "-h"):
        print(HELP)
        return 0

    if cmd not in mapping or mapping[cmd] is None:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(HELP)
        return 1

    return subprocess.call(mapping[cmd] + rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
