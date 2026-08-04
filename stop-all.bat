@echo off
setlocal

echo Stopping platform ports 8000 and 5173...

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo Killing backend process %%p
  taskkill /F /PID %%p
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do (
  echo Killing frontend process %%p
  taskkill /F /PID %%p
)

echo Done.
if /I not "%~1"=="nopause" pause
