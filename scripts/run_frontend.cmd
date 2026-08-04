@echo off
setlocal
cd /d "%~dp0..\frontend"

if not exist "%~dp0..\log" mkdir "%~dp0..\log"
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort > "%~dp0..\log\frontend.log" 2> "%~dp0..\log\frontend.err"
