#!/usr/bin/env bash
# GeoMine3D quick start (Git Bash / Linux / macOS)
# Usage:
#   ./start.sh          - build frontend only if dist is missing, then start server on 0.0.0.0:8000
#   ./start.sh build    - force rebuild frontend, then start server
#   ./start.sh server   - skip build, start server only
set -e
cd "$(dirname "$0")"

BUILD=0
case "${1:-}" in
    build) BUILD=1 ;;
    server) BUILD=0 ;;
    *) [ -f GeoMine3D/dist/index.html ] || BUILD=1 ;;
esac

if [ "$BUILD" = "1" ]; then
    echo "[GeoMine3D] Building frontend..."
    (cd GeoMine3D && npm run build)
else
    echo "[GeoMine3D] Using existing frontend build in GeoMine3D/dist"
fi

LAN_IP=$(python -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()" 2>/dev/null || echo "<your-lan-ip>")

echo
echo "============================================================"
echo "  GeoMine3D is starting..."
echo "  Local:    http://127.0.0.1:8000"
echo "  LAN:      http://${LAN_IP}:8000"
echo "  API docs: http://${LAN_IP}:8000/docs"
echo "  Press Ctrl+C to stop."
echo "============================================================"
echo

cd backend
PY=python
[ -x .venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe
[ -x .venv/bin/python ] && PY=.venv/bin/python
"$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
