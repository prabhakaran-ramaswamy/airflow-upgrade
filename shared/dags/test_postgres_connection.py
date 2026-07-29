"""Test Postgres connectivity (no Airflow hooks).

Uses env vars:
  POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
"""
from __future__ import annotations

import inspect
import os
from datetime import datetime

import psycopg2
from airflow import DAG
from airflow.operators.python import PythonOperator


def test_postgres_connection():
    host = os.getenv("POSTGRES_HOST", "192.168.1.36")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "Rampoo@1981")
    dbname = os.getenv("POSTGRES_DB", os.getenv("AIRFLOW_DB", "airflow"))

    print(f"Connecting to Postgres {host}:{port}/{dbname} as {user} ...")
    with psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        connect_timeout=10,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version(), current_database(), current_user")
            version, database, current_user = cur.fetchone()

    print("Postgres connection OK")
    print(f"  database={database} user={current_user}")
    print(f"  version={version}")


_dag_kwargs = {
    "dag_id": "test_postgres_connection",
    "start_date": datetime(2024, 1, 1),
    "catchup": False,
    "tags": ["connectivity", "postgres"],
    "doc_md": __doc__,
}
if "schedule" in inspect.signature(DAG.__init__).parameters:
    _dag_kwargs["schedule"] = None
else:
    _dag_kwargs["schedule_interval"] = None

with DAG(**_dag_kwargs) as dag:
    PythonOperator(
        task_id="check_postgres",
        python_callable=test_postgres_connection,
    )
