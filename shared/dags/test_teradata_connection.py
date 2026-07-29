"""Test Teradata connectivity (no Airflow hooks).

Uses env vars:
  TERADATA_HOST, TERADATA_PORT, TERADATA_USER, TERADATA_PASSWORD, TERADATA_DATABASE
"""
from __future__ import annotations

import inspect
import os
from datetime import datetime

import teradatasql
from airflow import DAG
from airflow.operators.python import PythonOperator


def test_teradata_connection():
    host = os.getenv("TERADATA_HOST", "192.168.1.33")
    port = os.getenv("TERADATA_PORT", "1025")
    user = os.getenv("TERADATA_USER", "dbc")
    password = os.getenv("TERADATA_PASSWORD", "dbc")
    database = os.getenv("TERADATA_DATABASE", "DBC")

    print(f"Connecting to Teradata {host}:{port}/{database} as {user} ...")
    with teradatasql.connect(
        host=host,
        dbs_port=port,
        user=user,
        password=password,
        database=database,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE, USER")
            current_db, current_user = cur.fetchone()

    print("Teradata connection OK")
    print(f"  database={current_db} user={current_user}")


_dag_kwargs = {
    "dag_id": "test_teradata_connection",
    "start_date": datetime(2024, 1, 1),
    "catchup": False,
    "tags": ["connectivity", "teradata"],
    "doc_md": __doc__,
}
if "schedule" in inspect.signature(DAG.__init__).parameters:
    _dag_kwargs["schedule"] = None
else:
    _dag_kwargs["schedule_interval"] = None

with DAG(**_dag_kwargs) as dag:
    PythonOperator(
        task_id="check_teradata",
        python_callable=test_teradata_connection,
    )
