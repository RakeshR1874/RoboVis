#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:${API_PORT}}"

if command -v pkill >/dev/null 2>&1; then
  pkill -f "uvicorn.*services.api.app.main:app" >/dev/null 2>&1 || true
  pkill -f "vite.*--host.*127.0.0.1.*${WEB_PORT}" >/dev/null 2>&1 || true
fi

ss -lnt | grep -E ":${API_PORT}|:${WEB_PORT}" || true

set +u
source /opt/ros/jazzy/setup.bash
set -u
source "$ROOT_DIR/.venv/bin/activate"
cd "$ROOT_DIR"
PYTHONPATH=. python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port "$API_PORT" > /tmp/auv-api.log 2>&1 &
API_PID=$!
echo "API PID=$API_PID | http://127.0.0.1:${API_PORT}"
cd "$ROOT_DIR/apps/web"
VITE_API_BASE_URL="$API_BASE_URL" npm run dev -- --host 127.0.0.1 --port "$WEB_PORT" > /tmp/auv-web.log 2>&1 &
WEB_PID=$!
echo "WEB PID=$WEB_PID | http://127.0.0.1:${WEB_PORT}"
wait
