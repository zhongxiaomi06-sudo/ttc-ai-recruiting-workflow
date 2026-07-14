#!/usr/bin/env bash
# setup_remote_mcp.sh — 在【另一台电脑】上一键安装并注册 zhongxiaomi MCP
#
# 前置（手动做两步）：
#   1. git clone <repo> 本仓库
#   2. 把 .env 放进去（含 RDS_HOST/RDS_USER/RDS_PASSWORD，勿走明文聊天传输）
#
# 然后在本仓库根目录跑：
#   bash scripts/setup_remote_mcp.sh
#
# 它做的事（幂等）：
#   - 建/复用 candidate-collector/.venv，装 pymysql mcp fastembed httpx
#   - 校验 .env 的 RDS 凭据
#   - 把 zhongxiaomi MCP 注册进已安装的 AI 工具（Claude Code / Codex / OpenCode）
#   - 做一次 stdio 握手测试
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CC="$REPO/candidate-collector"
PY="$CC/.venv/bin/python"

say() { printf '\033[1m▸ %s\033[0m\n' "$1"; }
warn() { printf '\033[33m⚠ %s\033[0m\n' "$1"; }

say "仓库路径：$REPO"

# 1) venv + 依赖
if [ ! -x "$PY" ]; then
  say "创建虚拟环境 candidate-collector/.venv"
  if command -v uv >/dev/null 2>&1; then
    uv venv "$CC/.venv"
  else
    python3 -m venv "$CC/.venv"
  fi
fi
say "安装依赖 pymysql / mcp / fastembed / httpx"
if command -v uv >/dev/null 2>&1; then
  uv pip install --python "$PY" pymysql "mcp>=1.0" fastembed httpx python-dotenv >/dev/null
else
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet pymysql "mcp>=1.0" fastembed httpx python-dotenv
fi

# 2) 校验 .env
say "校验 .env 凭据"
if [ ! -f "$REPO/.env" ]; then
  warn ".env 不存在！请把含 RDS_HOST/RDS_USER/RDS_PASSWORD 的 .env 放到 $REPO/.env 后重跑。"
  exit 1
fi
if ! grep -qE "^RDS_HOST=.+" "$REPO/.env" || ! grep -qE "^RDS_PASSWORD=.+" "$REPO/.env"; then
  warn ".env 缺少 RDS_HOST 或 RDS_PASSWORD，请补齐后重跑。"
  exit 1
fi
say "✓ .env 凭据就绪"

# 3) 注册 MCP 到已安装的 AI 工具
say "注册 zhongxiaomi MCP"
REPO="$REPO" PY="$PY" CC="$CC" python3 - <<'PY'
import json, os, pathlib
repo, py, cc = os.environ["REPO"], os.environ["PY"], os.environ["CC"]
home = pathlib.Path.home()
reg = []

# Claude Code
p = home / ".claude.json"
if p.exists():
    try:
        d = json.loads(p.read_text())
        d.setdefault("mcpServers", {})["zhongxiaomi"] = {
            "type": "stdio", "command": py,
            "args": ["-m", "cloud_sync.mcp_server"],
            "env": {"PYTHONPATH": cc},
        }
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
        reg.append("Claude Code")
    except Exception as e:
        print(f"  Claude Code 注册失败: {e}")

# OpenCode
p = home / ".config/opencode/opencode.json"
if p.exists():
    try:
        d = json.loads(p.read_text())
        d.setdefault("mcp", {})["zhongxiaomi"] = {
            "type": "local", "command": [py, "-m", "cloud_sync.mcp_server"],
            "enabled": True, "environment": {"PYTHONPATH": cc},
        }
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
        reg.append("OpenCode")
    except Exception as e:
        print(f"  OpenCode 注册失败: {e}")

# Codex
p = home / ".codex/config.toml"
if p.exists():
    t = p.read_text()
    if "[mcp_servers.zhongxiaomi]" not in t:
        t = t.rstrip() + (
            "\n\n[mcp_servers.zhongxiaomi]\n"
            f'command = "{py}"\n'
            'args = ["-m", "cloud_sync.mcp_server"]\n'
            "startup_timeout_sec = 30\n\n"
            "[mcp_servers.zhongxiaomi.env]\n"
            f'PYTHONPATH = "{cc}"\n'
        )
        p.write_text(t)
    reg.append("Codex")

print("  已注册到：" + ("、".join(reg) if reg else "（未检测到已安装的 AI 工具配置）"))
PY

# 4) 握手测试
say "握手测试（列出工具）"
PYTHONPATH="$CC" "$PY" - <<'PY' 2>/dev/null
import json, subprocess, os, sys
cc = os.environ.get("CC", ".")
env = dict(os.environ, PYTHONPATH=cc)
p = subprocess.Popen([f"{cc}/.venv/bin/python", "-m", "cloud_sync.mcp_server"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL, env=env, text=True)
p.stdin.write(json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize",
    "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"setup","version":"0"}}})+"\n")
p.stdin.flush()
try:
    name = json.loads(p.stdout.readline())["result"]["serverInfo"]["name"]
    p.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})+"\n"); p.stdin.flush()
    p.stdin.write(json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/list"})+"\n"); p.stdin.flush()
    tools = [t["name"] for t in json.loads(p.stdout.readline())["result"]["tools"]]
    print(f"  ✓ MCP '{name}' 正常，工具：{', '.join(tools)}")
except Exception as e:
    print(f"  ⚠ 握手失败：{e}（可重跑或检查 .env）")
    sys.exit(0)
finally:
    p.terminate()
PY

printf '\n\033[32m✓ 完成。重启你的 AI 工具后，直接用自然语言读写云端（zhongxiaomi MCP）。\033[0m\n'
