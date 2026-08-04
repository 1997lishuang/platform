@echo off
setlocal

echo Checking platform ports...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Test-NetConnection 127.0.0.1 -Port 8000 | Select-Object ComputerName,RemotePort,TcpTestSucceeded"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Test-NetConnection 127.0.0.1 -Port 5173 | Select-Object ComputerName,RemotePort,TcpTestSucceeded"

echo.
echo Listening processes:
netstat -ano | findstr ":8000"
netstat -ano | findstr ":5173"

echo.
echo Logs:
echo   log\backend.log
echo   log\backend.err
echo   log\frontend.log
echo   log\frontend.err

pause
