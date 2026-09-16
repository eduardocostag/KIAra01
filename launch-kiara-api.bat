@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -m uvicorn services.api.kiara_api.main:create_app --factory --host 127.0.0.1 --port 8000 --env-file services\api\.env.local
) else (
  python -m uvicorn services.api.kiara_api.main:create_app --factory --host 127.0.0.1 --port 8000 --env-file services\api\.env.local
)
