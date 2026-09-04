@echo off
cd /d "C:\Users\EduardoGonçalves\Desktop\KIAra01"
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -m app
) else (
  python -m app
)
