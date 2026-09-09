#!/usr/bin/env bash
# Second Chair - dev server
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "→ creating venv"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements-dev.txt
fi

[ -f .env ] || { cp .env.example .env; echo "→ wrote .env (add your keys)"; }

echo "→ http://127.0.0.1:8000"
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
