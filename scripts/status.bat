@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

docker compose -f data-migration/docker-compose.yml run --rm data-ops status
exit /b %ERRORLEVEL%
