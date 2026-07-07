# TTC 自动化猎头工作流 · 部署说明

> 目标：AI 主导招聘任务，人类作为可调度的工具；系统完成除“猎头打电话”外的全部前置动作。

## 新架构要点

- **AI Orchestrator**：每个 JD 对应一个 Mission，按状态机自动推进（created → jd_parsed → sourcing → scored → calling → human_pending → feedback → closed）。
- **Agent 群**：JD 解析、人才搜索、评分排序、话术生成、反馈学习，各 Agent 由 Orchestrator 调用。
- **人类作为工具**：需要人介入时，系统生成 HTML 任务页面（打电话、顾问审核、合规仲裁），而不是把人拉进聊天。
- **Dashboard**：统一工作台，展示进行中的 Mission 和待办人类任务。

## 1. 推荐部署形态

推荐把核心服务部署到服务器，而不是全部跑在顾问电脑本地。

```text
顾问浏览器 / 飞书 / ChatGPT / candidate-collector
        ↓ HTTPS
服务器 TTC Daemon
        ↓
SQLite 持久化 / Mission 状态机 / problem_task / human_task / Source 人才库 / 成熟读取工具
        ↓
Dashboard + HTML 任务页
```

本地只保留“采集端”：浏览器油猴脚本、公司官方人才库浏览器插件、必要时的 candidate-collector。服务器负责统一存储、分类、路由、Mission 编排、任务页和后续 API 对接。

## 2. 服务器部署（Docker Compose 推荐）

### 2.1 准备服务器

- Linux 服务器，建议 2C4G 起步。
- 安装 Docker 与 Docker Compose。
- 准备域名，例如 `https://ttc.example.com`，并在 Nginx / Caddy / 云厂商网关上配置 HTTPS。
- Dashboard 和任务页包含候选人信息，公网部署时必须放在 VPN、公司内网、Nginx Basic Auth 或其他访问控制之后。

### 2.2 上传代码并配置环境变量

```bash
cd /opt
git clone <your-repo-or-uploaded-folder> ttc-system
cd /opt/ttc-system

cp .env.server.example .env.server
vim .env.server
```

关键配置：

```bash
TTC_DAEMON_HOST=0.0.0.0
TTC_DAEMON_PORT=8766
TTC_DATA_DIR=/data
TTC_API_TOKEN=change-me-to-a-long-random-secret

# Source 公司人才库，先用 JSON 也可以
TTC_SOURCE_TALENT_ENABLED=true
TTC_SOURCE_TALENT_FILE=/data/source-candidates.json
```

### 2.3 启动

```bash
docker compose up -d --build
docker compose logs -f ttc-daemon
```

服务默认映射到服务器 `8766` 端口。建议通过 Nginx 反代到域名：

```bash
sudo cp deploy/nginx-ttc-daemon.conf /etc/nginx/conf.d/ttc-daemon.conf
sudo nginx -t
sudo systemctl reload nginx
```

把 `deploy/nginx-ttc-daemon.conf` 里的 `server_name ttc.example.com` 改成你的真实域名，并加 HTTPS 证书。

验证：

```bash
curl http://SERVER_IP:8766/health
# 或
curl https://ttc.example.com/health
```

### 2.4 非 Docker 部署（可选）

如果不用 Docker，可以用 systemd：

```bash
cd /opt/ttc-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium

sudo useradd --system --home /opt/ttc-system --shell /usr/sbin/nologin ttc || true
sudo chown -R ttc:ttc /opt/ttc-system
sudo cp deploy/ttc-daemon.service /etc/systemd/system/ttc-daemon.service
sudo systemctl daemon-reload
sudo systemctl enable --now ttc-daemon
sudo systemctl status ttc-daemon
```

## 3. 本地开发模式（可选）

只用于研发调试，不作为团队正式使用方式：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
python3 ttc_daemon.py
```

默认监听 `http://127.0.0.1:8766`。

## 4. 安装油猴脚本并指向服务器

1. 安装浏览器扩展 Tampermonkey（或 Violentmonkey）。
2. 安装 Feishu Toolkit：
   - 打开 `https://github.com/BlueSkyXN/feishu-toolkit/raw/main/feishu-toolkit.user.js`
3. 安装 TTC-Feishu Bridge：
   - 打开本地文件 `file:///Users/ashley/Downloads/ttc的交易系统/ttc-feishu-bridge.user.js`
   - 或在 Tampermonkey 中“新建脚本”，粘贴内容。
4. （可选）安装 TTC-ChatGPT Reader：
   - 打开 `file:///Users/ashley/Downloads/ttc的交易系统/ttc-chatgpt-reader.user.js`
5. 打开飞书或 ChatGPT 页面右下角 TTC 面板，把 Daemon URL 从 `http://127.0.0.1:8766` 改成服务器地址，例如：

```text
https://ttc.example.com
```

油猴脚本已经允许连接自定义服务器地址；正式使用时请优先使用 HTTPS。服务器配置了 `TTC_API_TOKEN` 时，油猴脚本里也要填写同一个 API Token；请求会通过 `X-TTC-Token` 发送到 Daemon。

## 5. candidate-collector 部署方式

短期建议 candidate-collector 仍跑在顾问本机或内网机器，负责读取浏览器里已授权候选人页面；收藏后把结果推到服务器 TTC Daemon。这样避免把招聘平台登录态搬到服务器。

长期如果要服务器化 candidate-collector，需要改 Chrome 扩展的 API 地址、权限和登录态管理；这一步建议等 Daemon 闭环稳定后再做。

本地启动：

```bash
cd candidate-collector
python3 -m pip install -r requirements.txt
./run.sh
```

默认监听 `http://127.0.0.1:8765`。服务器 Daemon 可以通过 webhook 接收候选人，也可以在内网/VPN 条件下拉取其 `export-jd` 接口。

## 6. 配置公司人才库 API

编辑 `ttc_daemon/config.py` 中的 `TALENT_DB_CONFIG`，或设置环境变量：

```bash
export TTC_TALENT_DB_ENABLED=true
export TTC_TALENT_DB_URL=https://your-talent-db.example.com
export TTC_TALENT_DB_KEY=your-api-key
export TTC_TALENT_DB_QUERY_PATH=/api/candidates/search
```

## 7. 配置 LLM（可选，用于 JD 结构化）

```bash
export TTC_LLM_PROVIDER=openai
export TTC_LLM_API_KEY=sk-...
export TTC_LLM_MODEL=gpt-4o-mini
```

未配置时，Daemon 使用简单关键词兜底。

## 7.1 配置 Source 公司人才库

Source 公司数据作为独立人才库来源接入，不需要重写搜索系统。优先使用成熟导出或 API：

```bash
# 方式一：先用本地 JSON 导出接入
export TTC_SOURCE_TALENT_ENABLED=true
export TTC_SOURCE_TALENT_FILE=/path/to/source-candidates.json

# 方式二：后续接 Source 公司人才库 API
export TTC_SOURCE_TALENT_ENABLED=true
export TTC_SOURCE_TALENT_URL=https://source-talent.example.com
export TTC_SOURCE_TALENT_KEY=your-api-key
export TTC_SOURCE_TALENT_QUERY_PATH=/api/candidates/search
```

JSON 支持两种格式：

```json
[
  {"name": "候选人A", "skills": ["Python", "LLM"], "source_url": "https://..."}
]
```

或：

```json
{"candidates": [{"name": "候选人A", "skills": ["Python", "LLM"]}]}
```

召回顺序为：公司人才库 API → Source 公司人才库 → candidate-collector → 后续全网补全。所有来源都会写入 `source_types`，便于后续证据追踪和去重。

## 7.2 成熟工具复用矩阵

TTC 不从零开发通用抓取、文件解析和浏览器自动化，只开发业务状态机、分类路由、异常恢复和证据标准。

| 场景 | 首选成熟工具 | 在 TTC 中的定位 |
|---|---|---|
| 公司/顾问已有候选人页面 | 公司官方人才库浏览器插件 | 一线入口，继续读取已授权可见页面 |
| 本地候选人收藏 | candidate-collector | 候选人页面、Gmail 附件、本地 PDF 入库 |
| 飞书文档/群消息 | Feishu Toolkit + TTC-Feishu Bridge | 页面提取，不承载业务判断 |
| ChatGPT 分享页 | TTC-ChatGPT Reader + Playwright | 浏览器侧读取动态内容 |
| 普通公开网页 | Crawl4AI 或 Firecrawl | 转成 LLM 友好的 Markdown/JSON |
| PDF/Word/PPT/Excel | MarkItDown，必要时 Apache Tika 兜底 | 文件转 Markdown |
| 已授权多步交互页面 | Playwright 或 Browser Use | 低频兜底，不做高吞吐抓取 |
| 大规模网页队列 | Scrapy 或 Crawlee | 闭环稳定后再引入，负责队列、重试、限速 |

## 7.3 Source 数据导入脚本

如果 Source 公司提供的是 Excel/CSV，可用脚本批量转成 JSON：

```bash
# CSV
python3 scripts/import_source_talent.py /path/to/source-candidates.csv -o data/source-candidates.json

# Excel（需 pip install pandas openpyxl）
python3 scripts/import_source_talent.py /path/to/source-candidates.xlsx -o data/source-candidates.json
```

脚本会按统一字段映射（name/phone/email/current_company/current_title/location/skills/summary），并自动处理逗号/分号分隔的技能。

## 7.4 管理接口

- 查看 Source 人才库状态：
  ```bash
  curl $TTC_URL/admin/source-talent
  ```
- 验证/刷新 Source 人才库（不需要重启 Daemon）：
  ```bash
  curl -X POST -H "X-TTC-Token: $TTC_API_TOKEN" $TTC_URL/admin/reload-source-talent
  ```
- 读取失败后人工解决，重置 read_job 重试：
  ```bash
  curl -X POST -H "X-TTC-Token: $TTC_API_TOKEN" $TTC_URL/admin/read-job/<job_id>/retry
  ```

## 7.5 LLM 配置（可选但强烈建议）

配置 LLM 后，artifact 分类和 JD 解析会从关键词兜底升级为 LLM 判断，准确率显著提升。

```bash
TTC_LLM_PROVIDER=openai
TTC_LLM_API_KEY=sk-...
TTC_LLM_BASE_URL=          # 可选，OpenAI 兼容接口时填写
TTC_LLM_MODEL=gpt-4o-mini
```

未配置时，系统自动使用关键词兜底，仍可运行。

## 7.6 飞书 Bot 通知（可选）

在人类任务生成时自动推送到飞书群：

```bash
TTC_FEISHU_BOT_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/...
TTC_DASHBOARD_URL=https://ttc.example.com
```

配置后，新的打电话任务、异常任务会自动发卡片到飞书群，点击卡片即可打开 HTML 任务页。

## 8. 运行完整工作流

服务启动后，自动生成 OpenAPI 文档：

- Swagger UI：`$TTC_URL/docs`
- OpenAPI JSON：`$TTC_URL/openapi.json`
- 可视化测试控制台：`$TTC_URL/console`
- 完整 API 文档：[API接口文档.md](API接口文档.md)

### 8.1 快速真实测试

浏览器打开：

```text
http://127.0.0.1:8766/console
```

在控制台里：

1. 粘贴一个 ChatGPT share link 或真实 JD 文本，提交。
2. 等待 10~60 秒。
3. 打开 `http://127.0.0.1:8766/dashboard` 查看 Mission 和待办任务。
4. 打开 `/human/task/<task_id>` 查看 AI 生成的电话任务。

### 8.2 启动 Mission（AI 自动推进）

```bash
export TTC_URL=https://ttc.example.com
export TTC_API_TOKEN=change-me-to-a-long-random-secret

# 从未路由的高置信 JD artifact 启动 Mission
curl -X POST -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{}' $TTC_URL/mission/start

# 或显式指定已经分类为 JD 的 artifact
curl -X POST -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{"normalized_artifact_id":"art_xxx"}' \
  $TTC_URL/mission/start

# 查看 Mission 状态
curl $TTC_URL/mission/<mission_id>

# 手动推进一步（调试用）
curl -X POST -H "X-TTC-Token: $TTC_API_TOKEN" $TTC_URL/mission/<mission_id>/step
```

启动后，Orchestrator 会自动：

1. 解析 JD
2. 查询公司人才库 + Source 公司人才库 + candidate-collector
3. 评分排序
4. 为高分候选人生成电话任务
5. 创建 HTML 任务页面，等待猎头处理

注意：系统不再把所有 `web_page` 默认当 JD。只有 `artifact_type=jd` 且置信度达到阈值时，`mission_router` 才会创建 Mission。

### 8.2 打开工作台

浏览器访问：

```
$TTC_URL/dashboard
```

### 8.3 人类完成任务

猎头打开 `$TTC_URL/human/task/<task_id>`，查看候选人档案、话术、证据，打完电话后提交反馈。

异常任务也在同一路径处理。读取失败、内容为空、登录受限、分类不确定、JD 字段缺失会进入 `problem_pending`，页面会按任务类型展示结构化字段。人工提交后，系统根据 `resume_action` 恢复 read_job、artifact 或 Mission。

### 8.4 自动触发

- 在飞书页面点击右下角 **TTC** 按钮 → 发送当前页到 Daemon。
- 打开 ChatGPT share link → 自动提取并发送（或点击右下角 **→TTC**）。
- candidate-collector 收藏简历后，可手动 POST 到 `/ingest/resume`，或等待 Daemon 定时拉取。

### 8.5 查看电话清单

```bash
curl $TTC_URL/api/call-list | python3 -m json.tool
```

## 9. 文件清单

| 文件 | 作用 |
|---|---|
| `方案四_AI猎头工作流_AI主导与人机调度架构.html` | **最终团队阅读版架构** |
| `ttc-feishu-bridge.user.js` | 飞书页面 → Daemon |
| `ttc-chatgpt-reader.user.js` | ChatGPT 分享页 → Daemon |
| `ttc_daemon.py` | Daemon 启动入口 |
| `ttc_daemon/main.py` | FastAPI 服务 + Mission/人类任务端点 + 后台调度器 |
| `ttc_daemon/agents/` | Orchestrator + JD/搜人/评分/话术/Human Dispatch Agent |
| `ttc_daemon/templates/` | Dashboard / 打电话任务页 / 审核页 |
| `ttc_daemon/db.py` | SQLite schema：ingest、read_jobs、normalized_artifacts、候选、电话清单、Mission、human_task、agent_runs |
| `ttc_daemon/talent_db_adapter.py` | 公司人才库 + Source 公司人才库适配器 |
| `requirements.txt` | Python 依赖 |
| `feishu-toolkit/` | 已集成 TTC Bridge 的 Feishu Toolkit Fork |
| `Dockerfile` / `docker-compose.yml` | 服务器容器化部署 |
| `.env.server.example` | 服务器环境变量模板 |
| `deploy/server_bootstrap.sh` | 服务器一键启动脚本（Docker 优先，systemd 兜底） |
| `deploy/ttc-daemon.service` | systemd 部署模板 |
| `deploy/nginx-ttc-daemon.conf` | Nginx 反代模板 |

## 10. 已知限制

- **ChatGPT share link 在当前环境无法访问**（网络层超时/拒绝）。已搭建自动化读取器（静态 fetch + Playwright 兜底），在可访问 ChatGPT 的网络中即可工作。
- 公司人才库 API 需要用户提供文档后才能正式对接；Source 公司数据可先用本地 JSON 导出接入。
- GoldScoreEngine / TalentMatch 评分逻辑当前为占位，后续接入现有模块。
- Orchestrator 当前为单节点、SQLite 内状态机；多顾问并发场景后续可迁移到任务队列（Redis/RabbitMQ）。
- `TTC_API_TOKEN` 只保护机器写入/触发接口；Dashboard 和 HTML 任务页仍建议放在 Nginx Basic Auth、VPN 或公司内网后面。

## 11. 下一步

1. 用户提供公司人才库 API 或 Source 公司人才库 JSON/API，完善 `ttc_daemon/talent_db_adapter.py` 的字段映射。
2. 按成熟工具矩阵接入 Crawl4AI / Firecrawl / MarkItDown / Browser Use，实现全网补全和文件解析。
3. 接入 GoldScoreEngine / TalentMatch 真实评分。
4. 在可访问 ChatGPT 的机器上验证对话读取。
5. 猎头打电话后通过 `/human/task/<id>/complete` 回填结果，形成学习闭环。
6. 持续完善 problem task 的结构化字段和 resume_action，保证异常解决后能恢复原流程。
7. 接入飞书 Bot 通知：新任务生成时自动推送给猎头。
