# Airflow 3.3.0 on Wolfi (Python 3.13)
# Public free tags no longer include python:3.13-dev — install 3.13 from wolfi-base.
FROM cgr.dev/chainguard/wolfi-base:latest AS builder

USER root
RUN apk update \
    && apk add --no-cache \
         python-3.13 \
         py3.13-pip \
         py3.13-virtualenv \
         busybox

ENV VIRTUAL_ENV=/opt/airflow-venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV AIRFLOW_VERSION=3.3.0
ENV PYTHON_VERSION=3.13
ENV CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

RUN python3.13 -m venv "${VIRTUAL_ENV}" \
    && pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir \
         "apache-airflow==${AIRFLOW_VERSION}" \
         --constraint "${CONSTRAINT_URL}" \
    && pip install --no-cache-dir \
         "psycopg2-binary==2.9.10" \
         "asyncpg" \
         "oracledb==2.5.1" \
         "teradatasql==20.0.0.15"

FROM cgr.dev/chainguard/wolfi-base:latest

USER root
RUN apk update \
    && apk add --no-cache \
         python-3.13 \
         busybox \
         ca-certificates

ENV AIRFLOW_HOME=/opt/airflow
ENV VIRTUAL_ENV=/opt/airflow-venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV PYTHONPATH="${AIRFLOW_HOME}"

COPY --from=builder /opt/airflow-venv /opt/airflow-venv

RUN adduser -D -u 50000 -G root -h /home/airflow -s /bin/sh airflow \
    && mkdir -p /home/airflow \
         "${AIRFLOW_HOME}/dags" "${AIRFLOW_HOME}/logs" "${AIRFLOW_HOME}/plugins" \
    && chown -R 50000:0 /home/airflow "${AIRFLOW_HOME}" "${VIRTUAL_ENV}"

ENV HOME=/home/airflow
WORKDIR ${AIRFLOW_HOME}
USER 50000

LABEL org.apache.airflow.version="3.3.0" \
      base.os="wolfi" \
      python.version="3.13" \
      upgrade.stage="3"

EXPOSE 8080
ENTRYPOINT ["airflow"]
CMD ["version"]
