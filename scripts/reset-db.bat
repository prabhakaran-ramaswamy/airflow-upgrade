@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo ==^> Stopping Postgres
docker compose -f postgres/docker-compose.yml --env-file .env down

echo ==^> Deleting shared DB folder: %CD%\pgdata
if exist "pgdata" (
  rmdir /s /q "pgdata"
  if errorlevel 1 (
    echo Failed to delete pgdata. Stop any process using it and retry.
    exit /b 1
  )
)

echo ==^> Recreating Postgres + airflow DB + CSV seed
call "%~dp0\00-prepare-data.bat"
exit /b %ERRORLEVEL%
