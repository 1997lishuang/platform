@echo off
setlocal

cd /d "%~dp0"

if not exist "%CD%\log" mkdir "%CD%\log"
set PYTHONPATH=%CD%\src
echo Backend log: %CD%\log\backend.log
echo Backend error log: %CD%\log\backend.err
if exist ".\.venv\Scripts\python.exe" (
  ".\.venv\Scripts\python.exe" -m uvicorn boq_pricing.api.main:app --host 127.0.0.1 --port 8000 > "%CD%\log\backend.log" 2> "%CD%\log\backend.err"
) else if exist "D:\windsurfDoc\baseUnit\.venv\Scripts\python.exe" (
  "D:\windsurfDoc\baseUnit\.venv\Scripts\python.exe" -m uvicorn boq_pricing.api.main:app --host 127.0.0.1 --port 8000 > "%CD%\log\backend.log" 2> "%CD%\log\backend.err"
) else (
  python -m uvicorn boq_pricing.api.main:app --host 127.0.0.1 --port 8000 > "%CD%\log\backend.log" 2> "%CD%\log\backend.err"
)

pause
