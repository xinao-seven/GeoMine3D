@echo off
setlocal

cd /d "%~dp0"

REM GeoMine3D quick start: rebuild the frontend every time, then serve everything
REM from the backend port (0.0.0.0:8000, reachable from the LAN).
REM
REM Usage:
REM   start.bat          - rebuild frontend, then start server on 0.0.0.0:8000
REM   start.bat server   - skip the build and start the server only

set "FRONTEND_DIR=%~dp0GeoMine3D"
set "BUILD=1"
if /i "%~1"=="server" set "BUILD=0"

if "%BUILD%"=="1" (
    echo [GeoMine3D] Building frontend...
    pushd "%FRONTEND_DIR%"
    call npm run build
    if errorlevel 1 (
        echo [GeoMine3D] Frontend build failed. Aborting.
        popd
        exit /b 1
    )
    popd
) else (
    echo [GeoMine3D] Skipping frontend build ^(server mode^).
)

:server
set "PY=python"
if exist "%~dp0backend\.venv\Scripts\python.exe" set "PY=%~dp0backend\.venv\Scripts\python.exe"

rem Detect the LAN IPv4 address for the banner.
rem Do NOT capture it with for /f: the command contains quotes and parentheses,
rem which cmd truncates (the old version silently produced an empty address).
rem The helper writes one line to a temp file, then set /p reads it back.
set "LAN_IP="
call :detect_lan_ip
if not defined LAN_IP set "LAN_IP=127.0.0.1"

echo.
echo ============================================================
echo   GeoMine3D is starting...
echo   Local:    http://127.0.0.1:8000
echo   LAN:      http://%LAN_IP%:8000
echo   API docs: http://%LAN_IP%:8000/docs
echo   Press Ctrl+C to stop.
echo ============================================================
echo.

cd /d "%~dp0backend"
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

endlocal
exit /b 0

rem ------------------------------------------------------------
rem Best effort: python helper -> PowerShell (default route NIC)
rem ------------------------------------------------------------
:detect_lan_ip
set "IPFILE=%TEMP%\geomine_lan_ip_%RANDOM%%RANDOM%.txt"
del "%IPFILE%" >nul 2>&1

if exist "%~dp0tools\lan_ip.py" (
    "%PY%" "%~dp0tools\lan_ip.py" > "%IPFILE%" 2>nul
)
if exist "%IPFILE%" set /p LAN_IP=<"%IPFILE%"
del "%IPFILE%" >nul 2>&1
if defined LAN_IP goto :eof

powershell -NoProfile -Command "$idx = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1).InterfaceIndex; $ip = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $idx -ErrorAction SilentlyContinue).IPAddress; if (-not $ip) { $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL' } | Select-Object -First 1 -ExpandProperty IPAddress) }; if ($ip) { [Console]::Write($ip) }" > "%IPFILE%" 2>nul
if exist "%IPFILE%" set /p LAN_IP=<"%IPFILE%"
del "%IPFILE%" >nul 2>&1
goto :eof
