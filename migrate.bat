@echo off
setlocal

cd /d "%~dp0"

".\.venv\Scripts\alembic.exe" upgrade head

pause
