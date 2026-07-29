# Airflow Upgrade Path Lab
#
# Stage 1: Airflow 2.5.2  (Debian)     UI :18080
# Stage 2: Airflow 2.11.2 (Wolfi 3.12) UI :18080
# Stage 3: Airflow 3.3.0  (Wolfi 3.13) UI :18080
#
# Shared Postgres (same server for metadata + data migration)
#   Host port: 15432 (non-default; container listens on 5432)
#   Data folder (common, deletable): D:\airflow-upgrade\pgdata
#   airflow  -> Airflow metadata + orders loaded by DAG (50 + 50 + 50)
#   Source: data-migration/data/orders.csv (150 rows)

## Prerequisites

- Docker Desktop with Compose v2

## Quick start (full upgrade path)

From `D:\airflow-upgrade` in Command Prompt:

```bat
REM 0) Start Postgres :15432, create DBs, seed 150-row CSV
scripts\00-prepare-data.bat

REM 1) Start Airflow 2.5.2 — then Trigger DAG file_to_destination (loads 50)
scripts\01-stage1-airflow-252.bat

REM 2) Upgrade to 2.11.2 — Trigger DAG file_to_destination again (loads next 50)
scripts\02-stage2-airflow-2112.bat

REM 3) Upgrade to 3.3 — Trigger DAG file_to_destination again (loads final 50)
scripts\03-stage3-airflow-33.bat

REM Check load progress anytime
scripts\status.bat

REM Wipe DB and rerun prepare (deletes pgdata folder)
scripts\reset-db.bat
```

At each stage: open the UI → unpause DAG **`file_to_destination`** → Trigger.  
Each run loads the **next 50** rows from the CSV into `airflow.orders` (same DB as metadata).

## Manual commands

### Shared Postgres

```bat
docker compose -f postgres/docker-compose.yml --env-file .env up -d
REM Host: localhost:15432  user/pass: postgres / Rampoo@1981
REM Data on disk: D:\airflow-upgrade\pgdata  (delete folder or run scripts\reset-db.bat to wipe)
```

### Prepare CSV + orders schema (data-ops)

```bat
docker compose -f data-migration/docker-compose.yml build
docker compose -f data-migration/docker-compose.yml run --rm data-ops init-db
docker compose -f data-migration/docker-compose.yml run --rm data-ops seed --reset
docker compose -f data-migration/docker-compose.yml run --rm data-ops status
```

### Airflow stacks (one at a time; same `airflow` metadata DB)

```bat
REM Stage 1 — Debian
docker compose -f airflow-2.5.2/docker-compose.yml --env-file .env up -d --build
REM UI http://localhost:18080  admin/admin  → trigger file_to_destination

REM Stage 2 — Wolfi Python 3.12
docker compose -f airflow-2.5.2/docker-compose.yml down
docker compose -f airflow-2.11.2/docker-compose.yml --env-file .env up -d --build
REM UI http://localhost:18080  admin/admin  → trigger file_to_destination

REM Stage 3 — Wolfi Python 3.13
docker compose -f airflow-2.11.2/docker-compose.yml down
docker compose -f airflow-3.3/docker-compose.yml --env-file .env up -d --build
REM UI http://localhost:18080  admin/admin  → trigger file_to_destination
```

## Load phases (DAG `file_to_destination`)

| Run | When                         | Records |
|----:|------------------------------|--------:|
|   1 | On Airflow 2.5.2             |      50 |
|   2 | After upgrade to 2.11.2      |      50 |
|   3 | After upgrade to 3.3         |      50 |
|     | **Total**                    | **150** |

Source file: `data-migration/data/orders.csv` (mounted at `/data/orders.csv` in Airflow)  
Destination: `airflow.orders` (+ `migration_state`) — same database as Airflow metadata  
DAG code: `shared/dags/file_to_destination.py` (mounted into every Airflow stage)

## Connectivity test DAGs

Mounted from `shared/dags/` (plain Python drivers, no Airflow hooks):

| DAG id | Env vars |
|--------|----------|
| `test_postgres_connection` | `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| `test_oracle_connection` | `ORA_HOST`, `ORA_PORT`, `ORA_SID`, `ORA_USER`, `ORA_PASSWORD`, `ORA_SCHEMA` |
| `test_teradata_connection` | `TERADATA_HOST`, `TERADATA_PORT`, `TERADATA_USER`, `TERADATA_PASSWORD`, `TERADATA_DATABASE` |

Edit values in `.env`, recreate containers, then Trigger each DAG from the UI.

## Project layout

```
airflow-upgrade/
  .env
  pgdata/                  # shared Postgres data (delete to reset)
  postgres/                # shared Postgres (host :15432)
  data-migration/          # seed CSV Docker image
  shared/dags/             # file_to_destination DAG (all stages)
  airflow-2.5.2/           # Debian image  apache/airflow:2.5.2-python3.10
  airflow-2.11.2/          # Wolfi py3.12  (Chainguard + Airflow 2.11.2)
  airflow-3.3/             # Wolfi py3.13  (Chainguard + Airflow 3.3.0)
  scripts/                 # .bat upgrade helpers
```

## Notes

- Metadata DB `airflow` is shared and migrated in place (`airflow db migrate`) at each stage.
- Data load is done by the Airflow DAG (CSV file -> `airflow.orders`), not the data-ops migrate command.
- All services join Docker network `airflow-upgrade-net` and use hostname `postgres`.
- Wolfi stages build from `cgr.dev/chainguard/wolfi-base` and install Python 3.12/3.13 via `apk` (free Chainguard no longer publishes public `python:3.12-dev` / `3.13-dev` tags). First build can take several minutes while Airflow installs under constraints.
"# airflow-upgrade" 
