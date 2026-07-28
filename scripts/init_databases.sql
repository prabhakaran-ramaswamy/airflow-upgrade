-- Run against shared Postgres (host :15432 / container postgres:5432)
-- Creates the single Airflow DB used for metadata + file-loaded orders

SELECT 'Creating databases if missing...' AS status;

SELECT 'CREATE DATABASE airflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
