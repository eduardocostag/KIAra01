@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe run_api.py
) else (
  python run_api.py
)
