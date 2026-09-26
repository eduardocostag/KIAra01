@echo off
title Kiara Browser Worker (Port 8001)
cd /d "%~dp0"

echo [Kiara] Iniciando Browser Worker na porta 8001...
set "KIARA_WORKER_TOKEN=kiara_local_worker_secret_key_2026"
set "KIARA_PROFILE_SALT=kiara_salt_concorrencia_2026"
set "KIARA_BROWSER_DATA_DIR=%~dp0data\browser-worker"
set "PYTHONPATH=%~dp0services\browser-worker"

python -m uvicorn app.main:app --port 8001 --host 127.0.0.1
pause
