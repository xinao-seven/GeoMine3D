@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM GeoMine3D quick start: build frontend (if needed) and serve everything from the backend port.
REM Usage:
REM   start.bat          - build frontend only if dist is missing, then start server on 0.0.0.0:8000
REM   start.bat build    - force rebuild frontend, then start server
REM   start.bat server   - skip build, start server only

set "FRONTEND_DIR=%~dp0GeoMine3D"
set "DIST_DIR=%FRONTEND_DIR%\dist"
set "BUILD=0"

if /i "%~1"=="build" set "BUILD=1"
if /i "%~1"=="server" goto :server
if not exist "%DIST_DIR%\index.html" set "BUILD=1"

if "%BUILD%"=="1" (
    echo [GeoMine3D] Building frontend...
    pushd "%FRONTEND_DIR%"
    call npm run build
    if errorlevel 1 (
        echo [GeoMine3D] Frontend build failed.
        popd
        exit /b 1
    )
    popd
) else (
    echo [GeoMine3D] Using existing frontend build in dist\
)

:server
set "PY=python"
if exist "%~dp0backend\.venv\Scripts\python.exe" set "PY=%~dp0backend\.venv\Scripts\python.exe"

for /f "delims=" %%i in ('"%PY%" -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()"') do set "LAN_IP=%%i"

echo.
echo ============================================================
echo   GeoMine3D is starting...
echo   Local:   http://127.0.0.1:8000
echo   LAN:     http://%LAN_IP%:8000
echo   API docs: http://%LAN_IP%:8000/docs
echo   Press Ctrl+C to stop.
echo ============================================================
echo.

cd /d "%~dp0backend"
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
endlocal
