#!/usr/bin/env bash
# One-command start for macOS / Linux.
#   ./start.sh          -> install (first run), seed the demo, run both servers
#   ./start.sh --fresh  -> wipe the database and re-seed first
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY=${PYTHON:-python3}
FRESH=""
[[ "${1:-}" == "--fresh" ]] && FRESH="--reset"

echo "── MOSAIC ─────────────────────────────────────────────"

# --- backend ---------------------------------------------------------------
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "Creating the Python virtual environment…"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

if [ ! -f data/mosaic.db ] || [ -n "$FRESH" ]; then
  echo "Seeding the demo…"
  python -m app.seed ${FRESH:---reset}
fi

echo "Starting the API on http://localhost:8000 …"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

# --- frontend --------------------------------------------------------------
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  echo "Installing frontend packages…"
  npm install --no-audit --no-fund
fi

echo
echo "MOSAIC is starting. Open http://localhost:3000"
echo "API docs: http://localhost:8000/docs"
echo
npm run dev
