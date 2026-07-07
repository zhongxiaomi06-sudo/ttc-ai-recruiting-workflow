#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ttc-system}"
ENV_FILE="$APP_DIR/.env.server"

cd "$APP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  cp .env.server.example "$ENV_FILE"
  echo "Created $ENV_FILE. Edit it before production use."
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose up -d --build
  docker compose ps
  exit 0
fi

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
./venv/bin/python -m playwright install chromium

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
