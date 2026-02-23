#!/usr/bin/env bash
set -euo pipefail

if [[ -f "venv/bin/activate" ]]; then
  source venv/bin/activate
fi

exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8060
