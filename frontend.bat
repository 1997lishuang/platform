@echo off
setlocal

cd /d "%~dp0frontend"

if not exist "%~dp0log" mkdir "%~dp0log"
echo Frontend log: %~dp0log\frontend.log
echo Frontend error log: %~dp0log\frontend.err
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort > "%~dp0log\frontend.log" 2> "%~dp0log\frontend.err"

pause
