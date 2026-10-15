#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -f .env || { echo 'Run python scripts/init_env.py first.'; exit 1; }
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
api_pid=$!
web_pid=''
cleanup() {
  kill "$api_pid" 2>/dev/null || true
  if [ -n "$web_pid" ]; then kill "$web_pid" 2>/dev/null || true; fi
  wait || true
}
trap cleanup EXIT INT TERM
for attempt in {1..30}; do
  if ! kill -0 "$api_pid" 2>/dev/null; then echo 'API startup failed.'; exit 1; fi
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/me || true)
  if [ "$code" = 401 ]; then break; fi
  if [ "$attempt" = 30 ]; then echo 'API did not become ready.'; exit 1; fi
  sleep 1
done
(cd frontend && exec node node_modules/next/dist/bin/next start --hostname 127.0.0.1) &
web_pid=$!
for attempt in {1..30}; do
  if ! kill -0 "$web_pid" 2>/dev/null || ! kill -0 "$api_pid" 2>/dev/null; then echo 'A server stopped during startup.'; exit 1; fi
  web_code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/ || true)
  api_code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/api/me || true)
  if [ "$web_code" = 200 ] && [ "$api_code" = 401 ]; then break; fi
  if [ "$attempt" = 30 ]; then echo 'Web/API did not become ready.'; exit 1; fi
  sleep 1
done
echo 'MangaTrans running on local port 3000. Keep API port 8000 private.'
wait -n "$api_pid" "$web_pid"
