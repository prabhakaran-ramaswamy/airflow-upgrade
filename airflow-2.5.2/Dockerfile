# Airflow 2.5.2 — official Debian-based image
FROM apache/airflow:2.5.2-python3.10

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends vim-tiny curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow
RUN pip install --no-cache-dir \
      "psycopg2-binary==2.9.9" \
      "oracledb==2.5.1" \
      "teradatasql==20.0.0.15"

LABEL org.apache.airflow.version="2.5.2" \
      base.os="debian" \
      upgrade.stage="1"
