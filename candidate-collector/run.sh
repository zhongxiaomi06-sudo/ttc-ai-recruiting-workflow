#!/bin/sh
set -eu
cd "$(dirname "$0")"
PY="${TTC_PYTHON:-python3.12}"
exec "$PY" -m uvicorn app:app --host 127.0.0.1 --port 8765
