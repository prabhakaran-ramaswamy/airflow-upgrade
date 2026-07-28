"""Create the shared airflow database if missing."""
import os
import sys

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

HOST = os.getenv("POSTGRES_HOST", "postgres")
PORT = int(os.getenv("POSTGRES_PORT", "5432"))
USER = os.getenv("POSTGRES_USER", "postgres")
PASSWORD = os.getenv("POSTGRES_PASSWORD", "Rampoo@1981")
DATABASES = [os.getenv("AIRFLOW_DB", "airflow")]


def main() -> int:
    print(f"Connecting to Postgres at {HOST}:{PORT} as {USER}...")
    conn = psycopg2.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD, dbname="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    for db in DATABASES:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db,))
        if cur.fetchone():
            print(f"  OK  database already exists: {db}")
        else:
            cur.execute(f'CREATE DATABASE "{db}"')
            print(f"  CREATED database: {db}")
    cur.close()
    conn.close()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
