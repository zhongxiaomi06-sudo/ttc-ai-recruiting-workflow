# TTC 猎头工作流自动化组件

配合 [方案三_AI猎头工作流_第一层架构.html](../方案三_AI猎头工作流_第一层架构.html) 与 [方案四_AI猎头工作流_AI主导与人机调度架构.html](../方案四_AI猎头工作流_AI主导与人机调度架构.html) 使用，实现：

- 飞书页面一键推送到本地工作流
- ChatGPT share link 自动读取
- 本地 Daemon 统一接收、存储、编排
- AI Orchestrator 自动推进 Mission 状态机
- Source 公司人才库（JSON / MySQL / API）接入
- 猎头最终只需打电话

## 文件结构

```
ttc-automation/
├── README.md                          # 本文件
├── ttc-feishu-bridge.user.js          # 飞书 → Daemon 油猴脚本
├── ttc-chatgpt-reader.user.js         # ChatGPT share link 读取油猴脚本
├── scripts/
│   └── run_local_daemon.sh            # 一键启动本地 Daemon（推荐）
└── daemon/
    ├── requirements.txt
    ├── run.sh                         # 一键启动 Daemon
    ├── ttc_daemon.py                  # FastAPI 本地服务 + HTML 页面
    ├── db.py                          # SQLite 数据模型
    ├── orchestrator.py                # Mission 状态机与后台调度
    ├── agents.py                      # JD 解析 / 搜人 / 评分 / 话术 Agent
    ├── llm_client.py                  # LLM 调用封装
    ├── link_reader.py                 # ChatGPT/网页/PDF 读取器
    ├── source_talent.py               # Source 人才库适配器
    ├── html_render.py                 # Jinja2 HTML 渲染
    └── templates/                     # Dashboard / Mission / 任务页面
```

## 快速部署

### 1. 启动本地 Daemon

```bash
cd ttc-automation
./scripts/run_local_daemon.sh
```

或：

```bash
cd ttc-automation/daemon
./run.sh
```

默认监听 `http://127.0.0.1:8766`。

首次运行会自动创建虚拟环境并安装依赖；Playwright 浏览器需要单独安装：

```bash
playwright install chromium
```

### 2. 打开 Dashboard

```bash
open http://127.0.0.1:8766/dashboard
```

Dashboard 展示进行中的 Mission 和待办 Human Task。

### 3. 安装浏览器油猴脚本

1. 安装 [Tampermonkey](https://www.tampermonkey.net/) 或 Violentmonkey。
2. 安装 [Feishu Toolkit](https://github.com/BlueSkyXN/feishu-toolkit)（解除复制限制、去水印）。
3. 在油猴管理器中点击“添加新脚本”，把 `ttc-feishu-bridge.user.js` 的内容粘贴进去并保存。
4. 同样方式安装 `ttc-chatgpt-reader.user.js`。

脚本面板支持设置 Daemon 地址和 API Token。

### 4. 启动 candidate-collector

```bash
cd candidate-collector
./run.sh
```

candidate-collector 默认监听 `http://127.0.0.1:8765`，Daemon 会通过 `/api/export-jd` 拉取已评分候选人。

## 使用方式

### 飞书页面

打开任意飞书文档 / Wiki / 表格 / 群聊页面，右下角会出现 **TTC** 悬浮面板：

- **发送整页 → TTC**：提取页面可见文本并发送到 Daemon。
- **发送选中 → TTC**：只发送当前选中的文本。
- **设置 Daemon 地址 / API Token**：本地安全认证（可选）。
- **自动识别 JD**：开启后检测到招聘关键词会自动推送。

发送后，Orchestrator 会自动：
1. 分类内容类型
2. 解析 JD
3. 从 candidate-collector / Source 人才库 / 公司人才库召回候选人
4. 评分排序
5. 生成电话任务 HTML 页面

### ChatGPT share link

打开 `https://chatgpt.com/share/...`，右下角会出现 **TTC ChatGPT** 面板：

- 默认自动等待对话加载完成后发送到 Daemon。
- 如果自动失败，可点击“发送对话 → TTC”手动重试。

### 猎头打电话

当 Mission 进入 `human_pending` 状态后，Dashboard 会出现 `phone_call` 任务：

- 打开任务页：候选人档案 + JD 摘要 + 推荐话术 + 验证问题 + 证据来源
- 打完电话后回填结果（有意向/无兴趣/未接通/信息有误）
- 反馈自动回流，Orchestrator 关闭 Mission

### Daemon API

常用端点：

```bash
# 健康检查 + 统计
curl http://127.0.0.1:8766/status

# Source 人才库状态检查
curl http://127.0.0.1:8766/admin/source-talent

# 提交链接读取任务（ChatGPT / 网页）
curl -X GET "http://127.0.0.1:8766/ingest/read-link?url=https://chatgpt.com/share/..."

# 查看当前待打电话清单
curl http://127.0.0.1:8766/api/call-list

# 提交电话任务反馈
curl -X POST "http://127.0.0.1:8766/human/task/{task_id}/complete" \
  -H "Content-Type: application/json" \
  -d '{"outcome":"interested","notes":"候选人愿意聊"}'
```

如果启用了 `TTC_API_TOKEN`，以上 API 调用需带上 `-H "X-TTC-Token: your-token"`。

## 数据存放

所有原始快照和提取内容都保存在本机 `ttc-automation/daemon/data/` 下：

- `data/links/<hash>/`：每个链接的 `raw.html`、`extracted.md`、`meta.json`
- `data/ttc.db`：SQLite 索引与元数据（missions / human_tasks / artifacts / agent_runs / read_jobs）

## 环境变量

在项目根目录创建 `.env`，`run_local_daemon.sh` 会自动加载：

```bash
# API 认证（可选）
TTC_API_TOKEN=your-secret-token

# Source 人才库：JSON 文件
TTC_SOURCE_TALENT_ENABLED=true
TTC_SOURCE_TALENT_FILE=/path/to/source-candidates.json

# Source 人才库：MySQL/RDS
TTC_MYSQL_HOST=121.40.2.48
TTC_MYSQL_PORT=3306
TTC_MYSQL_DATABASE=recruit_bot
TTC_MYSQL_USER=ttc_reader
TTC_MYSQL_PASSWORD=***
TTC_MYSQL_TABLE=candidates
TTC_MYSQL_NAME_COL=name
TTC_MYSQL_TEXT_COL=resume_text

# Source 人才库：API
TTC_SOURCE_TALENT_URL=https://source-talent.example.com
TTC_SOURCE_TALENT_KEY=your-api-key
TTC_SOURCE_TALENT_QUERY_PATH=/api/candidates/search

# 公司人才库 API（可选）
TTC_TALENT_DB_ENABLED=true
TTC_TALENT_DB_URL=https://your-talent-db.example.com/api/search
TTC_TALENT_DB_KEY=your-api-key

# LLM（可选，用于更准的 JD 解析和分类）
TTC_LLM_API_KEY=sk-...
TTC_LLM_BASE_URL=https://api.openai.com/v1   # 或 Kimi/Claude 兼容地址
TTC_LLM_MODEL=gpt-4o-mini
```

未配置 LLM 时，系统使用关键词兜底，仍可跑通主链路。

## 注意事项

- 油猴脚本通过 `GM_xmlhttpRequest` 绕过浏览器跨域限制，直接向本机 Daemon 发送数据。
- ChatGPT share link 能否读取取决于你本机网络能否打开该页面；如果网络层直接拒绝（如当前服务器环境），Playwright 也会失败。
- 只采集你已授权访问的页面；不绕过登录、验证码、付费墙。
- 本地调用 candidate-collector / Source DB 已禁用环境代理，避免本机代理导致 localhost 502。

## 当前已实现

- ✅ 飞书 / ChatGPT / candidate-collector 输入采集
- ✅ 本地 Daemon + SQLite 数据层
- ✅ AI Orchestrator + Mission 状态机
- ✅ read_job → artifact_classifier → normalized_artifact → mission_router 闭环
- ✅ JD 解析 → 人才搜索（candidate-collector + Source 人才库 + 公司人才库） → 评分 → 生成电话任务 自动推进
- ✅ Dashboard + Mission 详情 + Human Task HTML 页面
- ✅ 猎头电话任务页与反馈提交
- ✅ API Token 认证（可选）
- ✅ Source 人才库 JSON / MySQL / API 适配器
- ✅ 本地代理绕过

## 下一步

1. 接入真实 GoldScoreEngine / TalentMatch 评分，替换当前占位算法。
2. 飞书 Bot 主动推送新任务通知。
3. 接入 Recruiting Quant OS 仓位管理。
