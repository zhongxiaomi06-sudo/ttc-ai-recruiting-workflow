#!/bin/bash
# 健康探针 — cron 每分钟跑，发现异常立即重启
# 安装: */1 * * * * /opt/recruit-bot-v5/guard/health_probe.sh >> /var/log/health_probe.log 2>&1

HEALTH_URL="http://127.0.0.1:8878/health"
FRONTEND_URL="https://yorkteam.cn"
MAX_RETRIES=3
LOG_TAG="[health_probe]"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $LOG_TAG $1"; }

# Check backend health
for i in $(seq 1 $MAX_RETRIES); do
    status=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 "$HEALTH_URL" 2>/dev/null)
    if [ "$status" = "200" ]; then
        break
    fi
    log "Backend attempt $i: HTTP $status"
    sleep 2
done

if [ "$status" != "200" ]; then
    log "FATAL: Backend health check failed after $MAX_RETRIES attempts — RESTARTING"
    systemctl restart recruit-bot
    sleep 3
    # Verify restart
    new_status=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 "$HEALTH_URL" 2>/dev/null)
    log "After restart: HTTP $new_status"
    if [ "$new_status" != "200" ]; then
        log "CRITICAL: Restart did not fix backend!"
    fi
fi

# Check frontend
frontend_status=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 -k "$FRONTEND_URL" 2>/dev/null)
if [ "$frontend_status" != "200" ]; then
    log "WARN: Frontend HTTP $frontend_status — reloading nginx"
    systemctl reload nginx
fi
