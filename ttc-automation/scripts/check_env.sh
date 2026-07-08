#!/bin/bash
# Verify Aliyun / Feishu / Source talent / Daemon connectivity.
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

echo "=== Aliyun CLI ==="
if aliyun --profile ttc sts GetCallerIdentity >/dev/null 2>&1; then
  echo "✅ Aliyun profile 'ttc' OK"
else
  echo "❌ Aliyun profile 'ttc' failed. Run: aliyun configure set --profile ttc --mode AK ..."
fi

echo ""
echo "=== Feishu CLI ==="
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 lark-cli auth status --json --verify | grep -E '"bot"|"user"|"verified"' || true

echo ""
echo "=== Source Talent ==="
curl -s --noproxy "*" "http://127.0.0.1:8766/admin/source-talent" | python3 -m json.tool || echo "❌ Daemon not running"

echo ""
echo "=== Daemon Status ==="
curl -s --noproxy "*" "http://127.0.0.1:8766/status" | python3 -m json.tool || echo "❌ Daemon not running"
