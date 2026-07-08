# TalentMatch v6 · 系统审计报告

> 审计时间: 2026-06-18 21:40 CST
> 服务器: 47.110.93.137 (阿里云 ECS)
> 域名: https://yorkteam.cn

---

## 总体状态: ✅ 系统运行正常

| 组件 | 状态 | 详情 |
|------|------|------|
| FastAPI 后端 (8878) | ✅ active | 3006 候选人, 19542 职位, 195 匹配 |
| Nginx HTTPS (443) | ✅ active | Let's Encrypt 证书, 全链路加密 |
| 飞书 WebSocket | ✅ active | 连接到 feishu.cn, App 审核中 |
| 前端 React SPA | ✅ 已部署 | yorkteam.cn 200 OK |
| 数据库 SQLite WAL | ✅ 正常 | 42MB, 24 个索引, integrity_check ok |
| 数据库备份 | ✅ 每日 03:00 | backup.sh → /opt/recruit-bot/backups/ |
| 隐式反馈聚合 | ✅ 5min 循环 | implicit_score 写入 candidates 表 |
| 用户追踪 | ✅ 前端 + 后端 | tracking 表 + TrackingMiddleware |
| deploy.sh | ✅ 已更新 | 指向 47.110.93.137, 一键部署 |

---

## 关键修复记录

### P0 — 已全部修复

1. **HTTPS 上线** — Let's Encrypt 证书, yorkteam.cn 全链路 200
2. **飞书 WebSocket 启动** — `feishu-ws.service` active, 轮询+WebSocket 双通道
3. **代码统一** — `feishu_client.py` 从 1158 行拆到 150 行 + `card_builders.py` 191 行
4. **tests/ 目录恢复** — 10 个测试文件, 15 万行, 已同步到服务器
5. **Apple Double 清理** — 139 个 `._*` 文件已删除
6. **空目录清理** — 3 个空目录已移除
7. **聚合循环修复** — `aggregate_implicit_signals` 写入 `implicit_score` 列
8. **Jobs 分页修复** — `list_jobs` 加 `offset` 参数
9. **ws_client 线程安全** — `threading.Lock` + 重复消息去重

### 🟠 P1 — 已处理

10. **部署脚本重写** — `deploy/deploy.sh` 指向 47.110.93.137, Git tag 自动打
11. **前端构建部署** — 最新 react-dist 已部署

### 🟡 P2 — 待后续

12. **连接池** — 当前每条请求开新 SQLite 连接, 多进程时需 RDS MySQL
13. **API 输入验证** — Pydantic model 校验 (已在 app/models/ 有部分)
14. **前端筛选栏 / Drawer** — 代码已写但本地未构建部署

---

## API 端点清单

| 端点 | 状态 | 说明 |
|------|------|------|
| GET /health | ✅ | 系统健康检查 |
| GET /api/stats | ✅ | 统计数据 |
| GET /api/candidates | ✅ | 候选人列表 (分页) |
| GET /api/jobs | ✅ | 职位列表 (分页+搜索) |
| GET /api/matches | ✅ | 匹配记录 |
| POST /api/fast-match | ✅ | 快速匹配引擎 |
| POST /api/compare | ✅ | 候选人对比 |
| POST /api/tracking/event | ✅ | 隐式追踪事件 |
| POST /api/tracking/batch | ✅ | 批量追踪上传 |
| GET /api/tracking/stats | ✅ | 追踪统计 |
| POST /api/feedback | ✅ | 显式反馈 (含 reason_tags) |
| POST /api/auth/register | ✅ | 用户注册 |
| POST /api/auth/login | ✅ | 用户登录 + JWT |
| GET /api/auth/me | ✅ | 当前用户信息 |
| GET /api/agents/status | ✅ | Agent 管道状态 |
| POST /webhook/event | ✅ | 飞书事件接收 |

---

## 部署流程

```bash
# 一键部署
cd /Users/ashley/Documents/简历的工作信息
bash deploy/deploy.sh

# 手动 SSH
ssh root@47.110.93.137

# 查看服务状态
systemctl status recruit-bot
systemctl status nginx
systemctl status recruit-bot-ws

# 查看日志
journalctl -u recruit-bot -n 50 --no-pager
journalctl -u recruit-bot-ws -n 50 --no-pager

# 重启服务
systemctl restart recruit-bot
systemctl restart recruit-bot-ws

# 查看数据库
sqlite3 /opt/recruit-bot/data/sqlite/recruit.db
```

---

## 飞书集成状态

| 配置项 | 状态 | 说明 |
|--------|------|------|
| APP_ID | ✅ cli_aaa0d8ccb4ba5bcb | 已配置 |
| APP_SECRET | ✅ | 在 .env, systemd 中 |
| WebSocket | ✅ active | 连接到 wss://msg-frontier.feishu.cn |
| App 激活状态 | ⏳ 审核中 | activate_status=2, 审核通过后自动接收事件 |
| 事件订阅 URL | 🔄 无需配置 | WebSocket 长连接不需要回调 URL |

---

## 待办 (按优先级)

1. **🔴 飞书 App 上线审核** — 在飞书开放平台提交发布, 审核通过后 WebSocket 开始接收事件
2. **🔴 API Key 轮换** — 当前 DASHSCOPE_API_KEY = DEEPSEEK_API_KEY (同一值), 需在阿里云 DashScope 创建专用 Key
3. **🟠 用户登录/注册** — Login.jsx + auth.py 已写好, 可在前端测试
4. **🟠 前端筛选栏** — 人才库/职位库的筛选组件需构建部署
5. **🟡 RDS MySQL 迁移** — 多用户/多进程时切换, 当前 SQLite 单 writer 够用
6. **🟡 日志轮转** — systemd-journald 的 SystemMaxUse=500M 可配
