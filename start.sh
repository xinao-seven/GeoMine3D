#!/usr/bin/env bash
# GeoMine3D quick start (Git Bash / Linux / macOS)
# Rebuilds the frontend every time, then serves everything from the backend port
# (0.0.0.0:8000, reachable from the LAN).
#
# Usage:
#   ./start.sh          - rebuild frontend, then start server on 0.0.0.0:8000
#   ./start.sh server   - skip the build and start the server only
set -e
cd "$(dirname "$0")"

BUILD=1
if [ "${1:-}" = "server" ]; then
    BUILD=0
fi

if [ "$BUILD" = "1" ]; then
    echo "[GeoMine3D] Building frontend..."
    (cd GeoMine3D && npm run build)
else
    echo "[GeoMine3D] Skipping frontend build (server mode)"
fi

cd backend
PY=python
if [ -x .venv/Scripts/python.exe ]; then
    PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
fi

# LAN IPv4 for the banner: python helper first, then hostname resolution fallback.
LAN_IP=""
if [ -f ../tools/lan_ip.py ]; then
    LAN_IP=$("$PY" ../tools/lan_ip.py 2>/dev/null || true)
fi
if [ -z "$LAN_IP" ]; then
    LAN_IP="127.0.0.1"
fi

echo
echo "============================================================"
echo "  GeoMine3D is starting..."
echo "  Local:    http://127.0.0.1:8000"
echo "  LAN:      http://${LAN_IP}:8000"
echo "  API docs: http://${LAN_IP}:8000/docs"
echo "  Press Ctrl+C to stop."
echo "============================================================"
echo

"$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
