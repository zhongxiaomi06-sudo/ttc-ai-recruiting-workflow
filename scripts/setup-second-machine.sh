#!/usr/bin/env bash
# setup-second-machine.sh — 第二台电脑一键接入云端协作
#
# 用法：
#   bash setup-second-machine.sh
#
# 它做的事：
#   1. 克隆/更新 ttc-ai-recruiting-workflow 仓库
#   2. 创建 candidate-collector/.venv 并安装依赖
#   3. 注册 zhongxiaomi MCP 到 Claude Code / OpenCode / Codex
#   4. 创建 zxm-up 命令（路径自动适配当前机器）
#   5. 首次同步全部对话/记忆到云端
#
# 前置条件：
#   - 已安装 git、python3、python3-venv
#   - 已安装 Claude Code（或其他 AI 工具）
#   - 有 .env 文件（含 RDS_HOST/RDS_USER/RDS_PASSWORD）

set -euo pipefail

REPO_NAME="ttc-ai-recruiting-workflow"
REPO_URL="https://github.com/zhongxiaomi06-sudo/ttc-ai-recruiting-workflow.git"
REPO_DIR="$HOME/$REPO_NAME"
CC_DIR="$REPO_DIR/candidate-collector"
VENV_PY="$CC_DIR/.venv/bin/python"
LOG_DIR="$REPO_DIR/logs"

say() { printf '\033[1m▸ %s\033[0m\n' "$1"; }
warn() { printf '\033[33m⚠ %s\033[0m\n' "$1"; }

say "第二台电脑一键接入云端协作"
say "仓库：$REPO_URL"
say "本地路径：$REPO_DIR"

# 1) 克隆/更新仓库
if [ -d "$REPO_DIR/.git" ]; then
  say "仓库已存在，拉取最新代码"
  git -C "$REPO_DIR" pull --rebase
else
  say "克隆仓库"
  git clone "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"

# 2) 检查 .env
if [ ! -f "$REPO_DIR/.env" ]; then
  warn ".env 不存在！请把含 RDS_HOST/RDS_USER/RDS_PASSWORD 的 .env 放到 $REPO_DIR/.env"
  warn "然后重新运行本脚本"
  exit 1
fi
say "✓ .env 就绪"

# 3) venv + 依赖
if [ ! -x "$VENV_PY" ]; then
  say "创建虚拟环境"
  python3 -m venv "$CC_DIR/.venv"
fi
say "安装依赖"
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet pymysql "mcp>=1.0" fastembed httpx python-dotenv

# 4) 注册 MCP
say "注册 zhongxiaomi MCP"
REPO_DIR="$REPO_DIR" VENV_PY="$VENV_PY" CC_DIR="$CC_DIR" python3 - <<'PY'
import json, os, pathlib
repo_dir = os.environ["REPO_DIR"]
venv_py = os.environ["VENV_PY"]
cc_dir = os.environ["CC_DIR"]
home = pathlib.Path.home()

# Claude Code
p = home / ".claude.json"
if p.exists():
    try:
        d = json.loads(p.read_text())
        d.setdefault("mcpServers", {})["zhongxiaomi"] = {
            "type": "stdio",
            "command": venv_py,
            "args": ["-m", "cloud_sync.mcp_server"],
            "env": {"PYTHONPATH": cc_dir},
        }
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
        print("  ✓ Claude Code")
    except Exception as e:
        print(f"  Claude Code 注册失败: {e}")

# OpenCode
p = home / ".config/opencode/opencode.json"
if p.exists():
    try:
        d = json.loads(p.read_text())
        d.setdefault("mcp", {})["zhongxiaomi"] = {
            "type": "local",
            "command": [venv_py, "-m", "cloud_sync.mcp_server"],
            "enabled": True,
            "environment": {"PYTHONPATH": cc_dir},
        }
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
        print("  ✓ OpenCode")
    except Exception as e:
        print(f"  OpenCode 注册失败: {e}")

# Codex
p = home / ".codex/config.toml"
if p.exists():
    t = p.read_text()
    if "[mcp_servers.zhongxiaomi]" not in t:
        t = t.rstrip() + (
            "\n\n[mcp_servers.zhongxiaomi]\n"
            f'command = "{venv_py}"\n'
            'args = ["-m", "cloud_sync.mcp_server"]\n'
            "startup_timeout_sec = 30\n\n"
            "[mcp_servers.zhongxiaomi.env]\n"
            f'PYTHONPATH = "{cc_dir}"\n'
        )
        p.write_text(t)
    print("  ✓ Codex")
PY

# 5) 创建 zxm-up
say "创建 zxm-up 命令"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/zxm-up" <<EOF
#!/usr/bin/env bash
set -euo pipefail
REPO="$REPO_DIR"
PY="$VENV_PY"
CC="$CC_DIR"
LOG_DIR="$LOG_DIR"
LOG_FILE="$LOG_DIR/zxm-up.log"

mkdir -p "$LOG_DIR"
cd "$REPO"

DRY_RUN=""
SOURCE="all"
LIMIT=""
FULL=false

while [[ \$# -gt 0 ]]; do
  case "\$1" in
    --dry-run) DRY_RUN="--dry-run"; shift ;;
    --full) FULL=true; shift ;;
    --source) SOURCE="\$2"; shift 2 ;;
    --source=*) SOURCE="\${1#*=}"; shift ;;
    --limit) LIMIT="\$2"; shift 2 ;;
    --limit=*) LIMIT="\${1#*=}"; shift ;;
    -h|--help)
      grep '^# ' "\$0" | sed 's/^# //'
      exit 0
      ;;
    *) echo "未知参数: \$1"; exit 1 ;;
  esac
done

export PYTHONPATH="$CC"

echo "▸ 1/3 同步 AI 对话记忆"
LIMIT_ARG=""
[ -n "$LIMIT" ] && LIMIT_ARG="--limit $LIMIT"
$PY "$REPO/scripts/sync_all_conversations_to_cloud.py" --source "$SOURCE" --ensure-schema $LIMIT_ARG $DRY_RUN | tee -a "$LOG_FILE"

if [[ -z "$DRY_RUN" ]]; then
  echo "▸ 2/3 回填语义向量"
  $PY "$REPO/scripts/backfill_memory_embeddings.py" | tee -a "$LOG_FILE"
fi

if $FULL; then
  echo "▸ 3/3 同步候选人数据"
  $PY "$REPO/scripts/sync_ttc_daemon_candidates_to_cloud.py" $DRY_RUN | tee -a "$LOG_FILE"
fi

echo "✅ 完成"
EOF
chmod +x "$HOME/.local/bin/zxm-up"
say "✓ zxm-up 已创建：$HOME/.local/bin/zxm-up"

# 6) 首次同步
say "首次同步到云端"
"$HOME/.local/bin/zxm-up" || warn "首次同步失败，可稍后手动运行 zxm-up"

# 7) 安装定时同步
say "安装定时同步（每 30 分钟）"
(crontab -l 2>/dev/null | grep -v zxm-up; echo "# zxm-up: sync AI conversations to cloud every 30 min"; echo "*/30 * * * * $HOME/.local/bin/zxm-up >> $LOG_DIR/zxm-up-cron.log 2>&1") | crontab -

say "✅ 第二台电脑接入完成"
say "重启你的 AI 工具后，即可使用 zhongxiaomi MCP 读写云端"
