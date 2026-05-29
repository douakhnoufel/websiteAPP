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
  echo [INFO] SSL key not found. Trying to generate local certificates...
  python "%~dp0gen_certs.py"
)

if not exist "%CERT_FILE%" (
  echo [INFO] SSL certificate not found. Trying to generate local certificates...
  python "%~dp0gen_certs.py"
)

if not exist "%KEY_FILE%" (
  echo [ERROR] Missing SSL key: "%KEY_FILE%"
  echo [ERROR] Certificate generation did not succeed.
  pause
  exit /b 1
)

if not exist "%CERT_FILE%" (
  echo [ERROR] Missing SSL certificate: "%CERT_FILE%"
  echo [ERROR] Certificate generation did not succeed.
  pause
  exit /b 1
)

set "PHONE_IP="
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "$routes = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric; $routeIds = @($routes | ForEach-Object InterfaceIndex); $blocked = 'Loopback|VirtualBox|VMware|vEthernet|Docker|WSL|Bluetooth|Tailscale|ZeroTier'; $ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' -and $_.InterfaceAlias -notmatch $blocked }; if ($routeIds.Count -gt 0) { $ips = $ips | Where-Object { $routeIds -contains $_.InterfaceIndex } }; $ip = $ips | Sort-Object InterfaceMetric | Select-Object -First 1 -ExpandProperty IPAddress; if ($ip) { $ip }"`) do set "PHONE_IP=%%a"

echo [INFO] Checking HTTPS certificate for local and phone access...
if defined PHONE_IP (
  python "%~dp0gen_certs.py" "%PHONE_IP%"
) else (
  python "%~dp0gen_certs.py"
)

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
  echo [INFO] Port %PORT% is already in use by process ID %PORT_IN_USE%.
  echo [INFO] Opening the already running app:
  echo   %LOCAL_URL%
  start "" "%LOCAL_URL%"
  echo.
  echo If you want to restart it, stop the existing Python process first and run this file again.
  pause
  exit /b 0
)

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process '%LOCAL_URL%'"

python -m uvicorn main:app --host %HOST% --port %PORT% --ssl-keyfile "%KEY_FILE%" --ssl-certfile "%CERT_FILE%"

echo.
echo PotatoScan server stopped.
pause
