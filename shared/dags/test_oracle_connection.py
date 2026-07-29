"""Test Oracle connectivity (no Airflow hooks).

Uses env vars:
  ORA_HOST, ORA_PORT, ORA_SID, ORA_USER, ORA_PASSWORD, ORA_SCHEMA
"""
from __future__ import annotations

import inspect
import os
from datetime import datetime

import oracledb
from airflow import DAG
from airflow.operators.python import PythonOperator


def test_oracle_connection():
    host = os.environ.get("ORA_HOST", "192.168.1.36")
    port = int(os.environ.get("ORA_PORT", "1521"))
    sid = os.environ.get("ORA_SID", "orcl")
    user = os.environ.get("ORA_USER", "sys")
    password = os.environ.get("ORA_PASSWORD", "Rampoo@1981")
    schema = os.environ.get("ORA_SCHEMA", "SYS")

    dsn = oracledb.makedsn(host, port, sid=sid)
    mode = oracledb.AUTH_MODE_SYSDBA if user.lower() == "sys" else oracledb.AUTH_MODE_DEFAULT

    print(f"Connecting to Oracle {host}:{port} sid={sid} as {user} ...")
    with oracledb.connect(user=user, password=password, dsn=dsn, mode=mode) as conn:
        with conn.cursor() as cur:
            if schema:
                cur.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {schema}")
            cur.execute("SELECT USER FROM dual")
            (current_user,) = cur.fetchone()
            cur.execute("SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual")
            (current_schema,) = cur.fetchone()
            cur.execute("SELECT 1 FROM dual")
            cur.fetchone()

    print("Oracle connection OK")
    print(f"  user={current_user} schema={current_schema} sid={sid}")


_dag_kwargs = {
    "dag_id": "test_oracle_connection",
    "start_date": datetime(2024, 1, 1),
    "catchup": False,
    "tags": ["connectivity", "oracle"],
    "doc_md": __doc__,
}
if "schedule" in inspect.signature(DAG.__init__).parameters:
    _dag_kwargs["schedule"] = None
else:
    _dag_kwargs["schedule_interval"] = None

with DAG(**_dag_kwargs) as dag:
    PythonOperator(
        task_id="check_oracle",
        python_callable=test_oracle_connection,
    )
