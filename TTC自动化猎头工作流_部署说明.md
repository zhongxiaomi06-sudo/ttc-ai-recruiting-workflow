# TTC 自动化猎头工作流 · 部署说明

> 目标：AI 主导招聘任务，人类作为可调度的工具；系统完成除“猎头打电话”外的全部前置动作。

## 新架构要点

- **AI Orchestrator**：每个 JD 对应一个 Mission，按状态机自动推进（created → jd_parsed → sourcing → scored → calling → human_pending → feedback → closed）。
- **Agent 群**：JD 解析、人才搜索、评分排序、话术生成、反馈学习，各 Agent 由 Orchestrator 调用。
- **人类作为工具**：需要人介入时，系统生成 HTML 任务页面（打电话、顾问审核、合规仲裁），而不是把人拉进聊天。
- **Dashboard**：统一工作台，展示进行中的 Mission 和待办人类任务。

## 1. 推荐部署形态

### 1.0 当前指定形态：部署到 TalentMatch 服务器

当前正式部署目标不是单独建站，而是复用 TalentMatch 服务器，并在 TalentMatch 的视觉体系中新增方案四工作流前端：

```text
https://yorkteam.cn                 TalentMatch React 前端，同一套视觉与导航
https://yorkteam.cn/api/*           TalentMatch 现有后端，端口 8878
https://yorkteam.cn/api/ttc/*       TTC 方案四子系统，端口 8766
```

TTC 只作为 AI 工作流后端子系统部署在同一台服务器：

```text
TalentMatch 风格的 AI 工作流页面
        ↓ /api/ttc/*
TTC Daemon（127.0.0.1:8766）
        ↓
read_jobs / raw_ingest / artifact / Mission / human_task / feedback
        ↓
TalentMatch parser / matching / feedback / Feishu Bot（provider/adapter 复用）
```

原则：

- 不直接复用 TalentMatch 现有页面来硬塞工作流。
- 新增符合 TalentMatch 色彩、布局、交互习惯的 AI 工作流页面。
- 不改 TalentMatch `/api/*` 现有接口。
- 不让 TTC 另起公开 Dashboard 作为正式入口。
- TTC 的 HTML 任务页短期可保留调试，正式使用由新的 workflow React 页面调用 `/api/ttc/*` 展示。
- nginx 只新增 `/api/ttc/` 代理到 `127.0.0.1:8766`。

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

## 2. TalentMatch 服务器部署

### 2.1 服务器现状

TalentMatch 当前生产形态：

```text
服务器：47.110.93.137
域名：https://yorkteam.cn
TalentMatch 后端：127.0.0.1:8878
TalentMatch 前端：/opt/talentmatch/frontend/react-dist
TTC 子系统目标端口：127.0.0.1:8766
```

部署时不要动现有 `recruit-bot` 服务和 `/api/*` 路由，只新增 `ttc-daemon` systemd 服务和 nginx `/api/ttc/` location。

### 2.2 上传代码并配置环境变量

```bash
# 本地先 dry-run，确认只会同步到 /opt/ttc-automation
DRY_RUN=1 ./deploy/sync_to_talentmatch.sh

# 确认无误后正式同步
DRY_RUN=0 ./deploy/sync_to_talentmatch.sh
```

首次部署后，在服务器上创建环境文件：

```bash
ssh root@47.110.93.137
cd /opt/ttc-automation

cp .env.server.example .env.server
vim .env.server
```

关键配置：

```bash
TTC_DAEMON_HOST=127.0.0.1
TTC_DAEMON_PORT=8766
TTC_DATA_DIR=/opt/ttc-automation/data
TTC_API_TOKEN=change-me-to-a-long-random-secret
TTC_DASHBOARD_URL=https://yorkteam.cn/api/ttc

# Source 公司人才库，先用 JSON 也可以
TTC_SOURCE_TALENT_ENABLED=true
TTC_SOURCE_TALENT_FILE=/opt/ttc-automation/data/source-candidates.json

# 可选：heuristic / talentmatch / goldscore / llm / auto
TTC_SCORING_PROVIDER=heuristic
TTC_TALENTMATCH_PATH=/opt/talentmatch
TTC_GOLDSCORE_URL=
TTC_GOLDSCORE_TOKEN=
TTC_GOLDSCORE_LOCAL_ENABLED=false
```

### 2.3 systemd 启动 TTC Daemon

```bash
cd /opt/ttc-automation
APP_DIR=/opt/ttc-automation ./deploy/server_bootstrap.sh
```

当前仓库的 service 模板已经指向 `/opt/ttc-automation`。TTC 只监听本机 `127.0.0.1:8766`，公网访问统一走 nginx `/api/ttc/`。
服务器默认安装 [deploy/requirements-server.txt](deploy/requirements-server.txt) 的轻量运行时依赖；训练、Playwright、MarkItDown 等重依赖按需单独安装，避免阻塞 Daemon 上线。

验证内部服务：

```bash
curl http://127.0.0.1:8766/health
```

### 2.4 nginx 挂到 TalentMatch 域名

把 [deploy/nginx-talentmatch-ttc.conf](deploy/nginx-talentmatch-ttc.conf) 中的 location 加进现有 `yorkteam.cn` HTTPS server block：

```bash
sudo cp /etc/nginx/conf.d/yorkteam.cn.conf /etc/nginx/conf.d/yorkteam.cn.conf.bak.$(date +%Y%m%d%H%M%S)
# 手动把 deploy/nginx-talentmatch-ttc.conf 的 location 合并进 yorkteam.cn 的 server block
sudo nginx -t
sudo systemctl reload nginx
```

验证：

```bash
curl https://yorkteam.cn/api/ttc/health
```

### 2.5 TalentMatch 风格的 Workflow 前端

前端不另起站点，也不是直接复用 TalentMatch 现有“人才库/职位库/智能匹配”页面。下一步是在 TalentMatch React 里新增一个适配方案四的工作流页面，沿用 TalentMatch 的：

- 顶部与侧边导航结构
- 蓝白色系、间距、卡片、表格、抽屉、表单风格
- 登录态、权限、消息提醒、错误保护
- API 封装方式和 Ant Design 组件体系

页面内容服务于当前 workflow：

```text
菜单：AI 工作流 / TTC Mission
数据源：/api/ttc/health
       /api/ttc/dashboard 或结构化 API
       /api/ttc/human/tasks
       /api/ttc/api/call-list
       /api/ttc/mission/{id}
```

短期可先做最小 workflow 页面：

- Mission 列表
- 待办 human_task 列表
- 电话任务详情抽屉
- 提交电话反馈
- 读取 JD / URL 的表单
- problem_task 结构化处理表单
- Mission 时间线 / agent_runs 审计记录

长期再把 TTC 的 Dashboard HTML 下线，全部改成 TalentMatch 风格的 React workflow 页面。

本地已准备一个最小可用页面：

```text
ttc-automation/talentmatch/frontend/src/pages/TTCWorkflow.jsx
ttc-automation/talentmatch/frontend/src/api/index.js
ttc-automation/talentmatch/frontend/src/components/Layout.jsx
ttc-automation/talentmatch/frontend/src/App.jsx
```

部署到 TalentMatch 前端时，先在服务器备份现有 `/opt/talentmatch/frontend/react-dist`，再把构建结果发布过去；不要覆盖 TalentMatch 原后端服务。

当前服务器验证结果：

```text
ttc-daemon.service: active
nginx: active
recruit-bot: active
http://127.0.0.1:8766/health: 200
https://yorkteam.cn/api/ttc/health: 200
https://yorkteam.cn/api/ttc/api/missions: 200
https://yorkteam.cn: 200
```

### 2.7 Sentry 监控

后端 TTC Daemon 使用 `sentry-sdk[fastapi]`，前端 TalentMatch React 使用 `@sentry/react`。默认不配置 DSN 时不会发送数据。

服务器 `.env.server`：

```bash
TTC_SENTRY_DSN=
TTC_SENTRY_ENVIRONMENT=production
TTC_SENTRY_RELEASE=ttc-daemon@0.3.0
TTC_SENTRY_TRACES_SAMPLE_RATE=0.1
TTC_SENTRY_PROFILES_SAMPLE_RATE=0.0
TTC_SENTRY_SEND_PII=false
```

TalentMatch React 构建环境：

```bash
VITE_SENTRY_DSN=
VITE_SENTRY_ENVIRONMENT=production
VITE_SENTRY_RELEASE=talentmatch-ttc-workflow@0.1.0
VITE_SENTRY_TRACES_SAMPLE_RATE=0.1
VITE_SENTRY_REPLAYS_SESSION_SAMPLE_RATE=0
VITE_SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE=1
```

验证：

```bash
curl https://yorkteam.cn/api/ttc/api/monitoring/status

# 配置 TTC_API_TOKEN 后可触发一条后端测试事件
curl -X POST -H "X-TTC-Token: $TTC_API_TOKEN" \
  https://yorkteam.cn/api/ttc/api/monitoring/sentry-test
```

### 2.6 Docker 部署（不作为当前首选）

如果未来单独部署 TTC，可用 Docker Compose：

```bash
docker compose up -d --build
docker compose logs -f ttc-daemon
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

## 7. 配置 LLM（可选，用于 JD 结构化和自动评分）

```bash
export TTC_LLM_PROVIDER=openai
export TTC_LLM_API_KEY=sk-...
export TTC_LLM_MODEL=gpt-4o-mini
# 默认 heuristic；设置为 llm 后，候选人评分优先走 LLM，失败自动回退
export TTC_SCORING_PROVIDER=heuristic
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
TTC_SCORING_PROVIDER=heuristic
```

`TTC_SCORING_PROVIDER` 默认保持 `heuristic`，保证主流程稳定。可选值：

- `talentmatch`：调用 TalentMatch `matching/unified_engine.py` 的 8 维度匹配引擎。
- `goldscore`：优先调用 `TTC_GOLDSCORE_URL` 外部服务；当 `TTC_GOLDSCORE_LOCAL_ENABLED=true` 时尝试 `TTC_TALENTMATCH_PATH/matching/gold_score_engine.py`；都不可用时，用 TalentMatch 的公司梯队、学历、稳定性、行业对齐生成含金量分。
- `llm`：调用 LLM 自动评分，输出推荐理由、风险和电话追问。
- `auto`：优先 TalentMatch，失败后尝试 LLM，最后回退启发式。

所有 provider 都只替换 scoring 层，不改变 Mission 状态机；外部调用失败时会回退到启发式评分。GoldScore 外部服务建议实现：

```text
POST $TTC_GOLDSCORE_URL
Headers: Authorization: Bearer $TTC_GOLDSCORE_TOKEN   # 可选
Body: {
  "candidate": 标准化候选人,
  "jd": 标准化 JD,
  "raw_candidate": 原候选人字段,
  "raw_jd": 原 JD 字段
}
Response: {
  "overall_score": 0-100,
  "risk_flags": [],
  "evidence": [],
  "verification_questions": []
}
```

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
- GoldScoreEngine / TalentMatch 不作为新系统重写，只通过 scoring provider / parser adapter / feedback adapter 接入现有 Mission 主链路。当前 scoring provider 已支持 `talentmatch`、`goldscore`、`llm`、`auto`，其中 `talentmatch` 复用 `matching/unified_engine.py`，`goldscore` 可接外部服务或未来的 `matching/gold_score_engine.py`。
- Orchestrator 当前为单节点、SQLite 内状态机；多顾问并发场景后续可迁移到任务队列（Redis/RabbitMQ）。
- `TTC_API_TOKEN` 只保护机器写入/触发接口；Dashboard 和 HTML 任务页仍建议放在 Nginx Basic Auth、VPN 或公司内网后面。

## 11. 下一步

当前不改变基层架构。主链路固定为：

```text
read_jobs → raw_ingest → artifact_classifier → normalized_artifacts
→ mission_router → Mission Orchestrator → human/problem task → feedback
```

接下来按以下顺序推进：

1. **对齐基线**：保护本地未提交改动，先同步远端最新 `origin/main`，以最新方案四实现作为真实基线。
2. **验证主闭环**：跑 compile/test/smoke，确认 JD 能走到 `human_pending`，电话任务全部完成后能进入 `feedback/closed`。
3. **修 P0 闭环**：优先修 `phone_call` 完成推进、`problem_pending` 的 `resume_state/resume_action`、read_job 重试恢复。
4. **接入成熟评分**：scoring provider 已接入 TalentMatch UnifiedMatchEngine、GoldScoreEngine 外部服务/本地模块入口和 LLM 自动评分；独立 GoldScoreEngine 未配置时自动使用含金量估算。
5. **接入反馈学习**：把电话反馈、顾问校准、客户反馈写成 TalentMatch `feedback_learner` 可消费的数据。
6. **迁入主仓**：稳定后把 `ttc-automation/` 作为顶层目录迁入 `talentmatch-recruit`，不要先拆进 TalentMatch 内部。
7. **再扩工具**：主闭环稳定后，再接 Crawl4AI / Firecrawl / MarkItDown / Browser Use、飞书 Bot 卡片和 React 管理后台。
