@echo off
setlocal

cd /d "%~dp0"

if not exist "%~dp0log" mkdir "%~dp0log"
echo Restarting platform...
call "%~dp0stop-all.bat" nopause

type nul > "%~dp0log\backend.log"
type nul > "%~dp0log\backend.err"
type nul > "%~dp0log\frontend.log"
type nul > "%~dp0log\frontend.err"

echo Starting backend on http://127.0.0.1:8000
start "Platform Backend" /min cmd.exe /c call "%~dp0scripts\run_backend.cmd"

echo Starting frontend on http://127.0.0.1:5173
start "Platform Frontend" /min cmd.exe /c call "%~dp0scripts\run_frontend.cmd"

echo.
echo Platform is starting. Check status with status.bat.
echo Logs are in "%~dp0log".
exit /b 0
