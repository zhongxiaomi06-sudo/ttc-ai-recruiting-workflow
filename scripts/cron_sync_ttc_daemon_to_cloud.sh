#!/usr/bin/env bash
# Periodic sync of ttc_daemon data/ingest artifacts to the cloud RDS memories table.
# Installed as a cron job. Cloud failures never affect local systems; output is
# appended to a log for inspection.
set -euo pipefail

REPO="/Users/ashley/Downloads/ttc的交易系统"
PYBIN="$REPO/candidate-collector/.venv/bin/python"
LOG_DIR="$REPO/logs"
LOG_FILE="$LOG_DIR/cloud_sync_cron.log"

mkdir -p "$LOG_DIR"
cd "$REPO"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') sync ttc_daemon -> cloud ==="
  "$PYBIN" scripts/sync_ttc_daemon_to_cloud.py
  echo "--- exit: $? ---"
} >>"$LOG_FILE" 2>&1 || {
  echo "!!! $(date '+%Y-%m-%d %H:%M:%S') sync failed (see above) !!!" >>"$LOG_FILE"
  exit 0   # never fail the cron job loudly
}
