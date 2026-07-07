#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python3 -m uvicorn app:app --host 127.0.0.1 --port 8765
