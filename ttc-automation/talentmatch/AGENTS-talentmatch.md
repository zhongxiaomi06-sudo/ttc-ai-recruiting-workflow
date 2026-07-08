# TalentMatch · AI Agent 操作规范

> 每次 Codex/Claude 在此项目工作时，必须遵守此文件中的所有规则。

---

## 规则 1：多轮次审计（强制）

**触发条件**：用户说"多轮次审计"、"跑X轮测试"、"完整测试"、"全部测一遍"、"审计"。

**执行流程**：

```bash
# 1. 先在服务器上跑 50 轮全功能审计
ssh root@47.110.93.137 "python3 /tmp/full_audit_v2.py 50"

# 2. 如果有失败项，逐个修复直到 100% 通过
# 3. 修复后重新跑 50 轮确认
# 4. 禁止在未跑完审计前声称"已完成"
```

**审计脚本**（服务器上）：`/tmp/full_audit_v2.py`
- 每轮 25 个检查项
- 50 轮 = 1250 项
- 覆盖：health / stats / auth(register+login+me) / search / match / tracking / feedback / analytics / messages / jobs / candidates
- 全部 200/201/409 都视为通过

**通过标准**：1250/1250 = 100%。任何失败必须修复后重跑。

---

## 规则 2：部署安全（强制）

**每次修改代码后必须执行：**

```bash
# Step A: 重启服务 + 验证 health
ssh root@47.110.93.137 "systemctl restart recruit-bot && sleep 2"
ssh root@47.110.93.137 "curl -s http://127.0.0.1:8878/health | python3 -c 'import sys,json;assert json.load(sys.stdin)[\"status\"]==\"ok\"'"

# Step B: 跑白屏防护
cd /Users/ashley/Documents/简历的工作信息/recruit-system
python3 guard/whitescreen_guard.py

# Step C: 确认前端 200
ssh root@47.110.93.137 "curl -s -o /dev/null -w '%{http_code}' https://yorkteam.cn | grep -q 200"
```

**任何一步失败 = 不可交付，先回滚再修。**

---

## 规则 3：数据库安全（强制）

| 禁止操作 | 后果 |
|---------|------|
| 在 valid_cols 加 DB schema 不存在的列 | INSERT 500 → 白屏 |
| 删除已有 DB 列 | 旧数据 INSERT/UPDATE 崩 |
| bare `except: pass` | 真实错误被吞 |

**修改前必须验证 schema：**
```bash
ssh root@47.110.93.137 "sqlite3 /opt/recruit-bot-v5/data/sqlite/recruit.db '.schema 表名'"
```

---

## 规则 4：汇报格式（强制）

**每次汇报工作结果时，必须包含：**

```
## 系统状态
| 指标 | 值 |
|------|-----|
| 服务 | recruit-bot/nginx/ws 状态 |
| 数据 | candidates / jobs / matches / feedback |
| 审计 | X轮 Y项 PASS/FAIL |

## 本次完成
- 1.
- 2.

## 剩余工作
| 优先级 | 项目 | 状态 |
|--------|------|------|

## 风险
- (如有)
```

**禁止凭记忆或假设填写。每个数字必须来自服务器实时查询。**

---

## 规则 5：Git + 记忆同步（强制）

**每次修改完成必须：**
```bash
cd /Users/ashley/Documents/简历的工作信息/recruit-system
git add -A && git commit -m "描述" && git push origin master

cd ~/Documents/我的过去
# 创建对话摘要
git add -A && git commit -m "📝 日期 描述" && git push origin main
```

---

## 服务器信息

| 项目 | 值 |
|------|-----|
| 地址 | 47.110.93.137 |
| 域名 | https://yorkteam.cn |
| 服务路径 | /opt/recruit-bot-v5/ |
| 数据库 | /opt/recruit-bot-v5/data/sqlite/recruit.db |
| 用户数据 | /opt/recruit-bot-v5/data/users/users.json |
| 前端构建 | /opt/recruit-bot-v5/frontend/react-dist/ |
| systemd | recruit-bot / recruit-bot-ws / nginx |

## 审计脚本

| 脚本 | 路径 | 用途 |
|------|------|------|
| 白屏防护 | guard/whitescreen_guard.py | 6项快速检查 |
| 全功能审计 | guard/full_audit.py | 50轮×25项=1250项 |

## 关键技能

| 技能 | 路径 | 触发 |
|------|------|------|
| deploy-safety | ~/.codex/skills/deploy-safety/SKILL.md | 每次部署 |
| audit-reporter | ~/.codex/skills/audit-reporter/SKILL.md | 每次汇报 |
