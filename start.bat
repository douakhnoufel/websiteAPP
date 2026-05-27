@echo off
setlocal
title PotatoScan Secure Launcher
cd /d "%~dp0"

set "HOST=0.0.0.0"
set "PORT=8000"
set "LOCAL_URL=https://localhost:%PORT%"
set "KEY_FILE=%~dp0key.pem"
set "CERT_FILE=%~dp0cert.pem"

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found in PATH.
  echo Install Python 3.11+ or activate your virtual environment, then try again.
  pause
  exit /b 1
)

if not exist "%KEY_FILE%" (
  echo [ERROR] Missing SSL key: "%KEY_FILE%"
  pause
  exit /b 1
)

if not exist "%CERT_FILE%" (
  echo [ERROR] Missing SSL certificate: "%CERT_FILE%"
  pause
  exit /b 1
)

set "PHONE_IP="
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "$ip = Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } ^| Sort-Object InterfaceMetric ^| Select-Object -First 1 -ExpandProperty IPAddress; if ($ip) { $ip }"`) do set "PHONE_IP=%%a"

echo.
echo ============================================
echo   PotatoScan Secure Launcher
echo ============================================
echo Starting FastAPI with HTTPS on port %PORT%...
echo.
echo PC:    %LOCAL_URL%
if defined PHONE_IP (
  echo Phone: https://%PHONE_IP%:%PORT%  ^(same network^)
) else (
  echo Phone: Could not detect LAN IP automatically.
)
echo.
echo The browser will open automatically in a few seconds.
echo Press Ctrl+C in this window to stop the server.
echo.

set "PORT_IN_USE="
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($c) { $c.OwningProcess }"`) do set "PORT_IN_USE=%%p"

if defined PORT_IN_USE (
  echo [ERROR] Port %PORT% is already in use by process ID %PORT_IN_USE%.
  echo Close the other server first, or open the existing app here:
  echo   %LOCAL_URL%
  echo.
  pause
  exit /b 1
)

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process '%LOCAL_URL%'"

python -m uvicorn main:app --host %HOST% --port %PORT% --ssl-keyfile "%KEY_FILE%" --ssl-certfile "%CERT_FILE%"

echo.
echo PotatoScan server stopped.
pause
