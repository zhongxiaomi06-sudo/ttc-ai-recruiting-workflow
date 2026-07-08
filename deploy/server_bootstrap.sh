#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ttc-automation}"
ENV_FILE="$APP_DIR/.env.server"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-deploy/requirements-server.txt}"

cd "$APP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  cp .env.server.example "$ENV_FILE"
  echo "Created $ENV_FILE. Edit it before production use."
fi

USE_DOCKER="${USE_DOCKER:-0}"
if [ "$USE_DOCKER" = "1" ] && command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose up -d --build
  docker compose ps
  exit 0
fi

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r "$REQUIREMENTS_FILE"

if [ "${INSTALL_PLAYWRIGHT:-0}" = "1" ]; then
  ./venv/bin/python -m playwright install chromium
fi

if command -v systemctl >/dev/null 2>&1; then
  sudo useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin ttc 2>/dev/null || true
  sudo chown -R ttc:ttc "$APP_DIR"
  sudo cp deploy/ttc-daemon.service /etc/systemd/system/ttc-daemon.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now ttc-daemon
  sudo systemctl status --no-pager ttc-daemon
else
  echo "systemd not found. Start manually with:"
  echo "  cd $APP_DIR && source venv/bin/activate && python ttc_daemon.py"
fi
