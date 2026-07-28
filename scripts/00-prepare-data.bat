@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==^> Starting shared Postgres on host port 15432
docker compose -f postgres/docker-compose.yml --env-file .env up -d
if errorlevel 1 exit /b 1

echo ==^> Waiting for Postgres to become healthy...
set /a _tries=0
:wait_pg
set /a _tries+=1
docker exec airflow-upgrade-postgres pg_isready -U postgres >nul 2>&1
if not errorlevel 1 goto pg_ready
if %_tries% GEQ 60 (
  echo Postgres did not become ready in time.
  docker logs airflow-upgrade-postgres --tail 40
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_pg
:pg_ready
echo Postgres is ready.

echo ==^> Building data-ops image
docker compose -f data-migration/docker-compose.yml build
if errorlevel 1 exit /b 1

echo ==^> Creating shared airflow database on Postgres
docker compose -f data-migration/docker-compose.yml run --rm data-ops init-db
if errorlevel 1 exit /b 1

echo ==^> Seeding 150 records to data/orders.csv
docker compose -f data-migration/docker-compose.yml run --rm data-ops seed --reset
if errorlevel 1 exit /b 1

echo ==^> Status
docker compose -f data-migration/docker-compose.yml run --rm data-ops status
if errorlevel 1 exit /b 1

echo Prepare-data complete. Postgres: localhost:15432  Data: %CD%\pgdata
exit /b 0
