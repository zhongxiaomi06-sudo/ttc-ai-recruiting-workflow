#!/usr/bin/env bash
set -euo pipefail

SERVER="${SERVER:-root@47.110.93.137}"
APP_DIR="${APP_DIR:-/opt/ttc-automation}"
DRY_RUN="${DRY_RUN:-1}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RSYNC_FLAGS=(-az --delete)
if [ "$DRY_RUN" = "1" ]; then
  RSYNC_FLAGS+=(--dry-run)
fi

COMMON_EXCLUDES=(
  --exclude ".git/"
  --exclude ".env"
  --exclude ".env.server"
  --exclude "venv/"
  --exclude "__pycache__/"
  --exclude "*.pyc"
  --exclude "node_modules/"
  --exclude "dist/"
  --exclude "ttc_daemon/data/"
  --exclude "*.db"
  --exclude "*.sqlite"
  --exclude "*.sqlite3"
)

ssh "$SERVER" "mkdir -p '$APP_DIR'"

rsync "${RSYNC_FLAGS[@]}" "${COMMON_EXCLUDES[@]}" \
  "$ROOT_DIR/.env.example" \
  "$ROOT_DIR/.env.server.example" \
  "$ROOT_DIR/requirements.txt" \
  "$ROOT_DIR/ttc_daemon.py" \
  "$ROOT_DIR/README.md" \
  "$ROOT_DIR/API接口文档.md" \
  "$ROOT_DIR/TTC自动化猎头工作流_部署说明.md" \
  "$ROOT_DIR/方案四_AI猎头工作流_AI主导与人机调度架构.html" \
  "$ROOT_DIR/deploy" \
  "$ROOT_DIR/scripts" \
  "$ROOT_DIR/ttc_daemon" \
  "$SERVER:$APP_DIR/"

ssh "$SERVER" "mkdir -p '$APP_DIR/ttc-automation/talentmatch'"
rsync "${RSYNC_FLAGS[@]}" "${COMMON_EXCLUDES[@]}" \
  "$ROOT_DIR/ttc-automation/README.md" \
  "$SERVER:$APP_DIR/ttc-automation/"
rsync "${RSYNC_FLAGS[@]}" "${COMMON_EXCLUDES[@]}" \
  "$ROOT_DIR/ttc-automation/talentmatch/matching" \
  "$SERVER:$APP_DIR/ttc-automation/talentmatch/"
rsync "${RSYNC_FLAGS[@]}" "${COMMON_EXCLUDES[@]}" \
  "$ROOT_DIR/ttc-automation/talentmatch/frontend" \
  "$SERVER:$APP_DIR/ttc-automation/talentmatch/"

if [ "$DRY_RUN" = "1" ]; then
  echo "Dry run complete. Re-run with DRY_RUN=0 to sync to $SERVER:$APP_DIR"
else
  echo "Synced to $SERVER:$APP_DIR"
fi
