@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==^> Ensuring shared Postgres is up (:15432)
docker compose -f postgres/docker-compose.yml --env-file .env up -d
if errorlevel 1 exit /b 1

echo ==^> Starting Airflow 2.5.2 (Debian) on :18080
docker compose -f airflow-2.5.2/docker-compose.yml --env-file .env down
docker compose -f airflow-2.5.2/docker-compose.yml --env-file .env up -d --build
if errorlevel 1 (
  echo.
  echo Stage 1 init failed. If you already ran stage 2/3, the metadata DB is newer
  echo than Airflow 2.5.2. Wipe and restart from stage 1:
  echo   scripts\reset-db.bat
  echo   scripts\01-stage1-airflow-252.bat
  exit /b 1
)

echo ==^> Waiting for webserver...
timeout /t 20 /nobreak >nul

echo Stage 1 ready. UI: http://localhost:18080  (admin/admin)
echo Unpause and Trigger DAG "file_to_destination" to load rows 1-50.
exit /b 0
