@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==^> Ensuring shared Postgres is up (:15432)
docker compose -f postgres/docker-compose.yml --env-file .env up -d
if errorlevel 1 exit /b 1

echo ==^> Stopping Airflow 2.5.2
docker compose -f airflow-2.5.2/docker-compose.yml --env-file .env down

echo ==^> Starting Airflow 2.11.2 (Wolfi / Python 3.12) on :18080
docker compose -f airflow-2.11.2/docker-compose.yml --env-file .env down
docker compose -f airflow-2.11.2/docker-compose.yml --env-file .env up -d --build
if errorlevel 1 exit /b 1

echo ==^> Waiting for webserver / DB migrate...
timeout /t 30 /nobreak >nul

echo Stage 2 ready. UI: http://localhost:18080  (admin/admin)
echo Unpause and Trigger DAG "file_to_destination" to load rows 51-100.
exit /b 0
