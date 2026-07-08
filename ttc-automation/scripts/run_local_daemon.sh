#!/bin/bash
# Run TTC local daemon with common local environment defaults.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DAEMON_DIR="$PROJECT_DIR/daemon"

cd "$DAEMON_DIR"

# Create venv if missing
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

# Optional: source local env overrides from .env in project root
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

# Disable proxy for local candidate-collector / source DB calls
export NO_PROXY="127.0.0.1,localhost"

python ttc_daemon.py
