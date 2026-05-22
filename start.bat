@echo off
title Potato Disease Detection System
cd /d "%~dp0"

echo Starting server...
start /B python -m uvicorn main:app --host 0.0.0.0 --reload >nul 2>&1

timeout /t 4 /nobreak >nul

for /f "delims=" %%a in ('powershell -noprofile -command "(Get-NetAdapter -Name 'Wi-Fi' | Get-NetIPAddress -AddressFamily IPv4).IPAddress"') do set IP=%%a
start http://localhost:8000
echo.
echo PC:     http://localhost:8000
echo Phone:  http://%IP%:8000  (same WiFi)
echo Close this window to stop.

:loop
timeout /t 1 /nobreak >nul
goto loop
