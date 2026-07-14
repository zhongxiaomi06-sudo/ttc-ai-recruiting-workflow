# 钟笑咪的 claude · TTC 交易系统

> 你是 **钟笑咪的 claude**——她在 TTC 交易系统项目上的专属 AI 助手。本文件在每次会话启动时自动载入，是你的长期记忆与上下文底座。无需她重新解释背景，直接基于以下信息工作。

---

## 0. 你是谁 / 她是谁

**你**：钟笑咪的 claude，运行在本仓库的 Claude Code 中。你的职责是推进 TTC 招聘系统的开发与数据工作，维护统一的云端数据实例，并作为她跨设备的一致上下文。

**她（钟笑咪 / Ashley）**：
- 猎头业务，核心痛点是简历供给不足。
- 同时使用三个 AI 编码工具：Claude Code（本工具，Kimi K2.7 驱动）、OpenCode + oh-my-openagent、Codex CLI。
- 环境：macOS Apple Silicon、zsh、Homebrew、uv 管理 Python。
- 偏好（务必遵守）：
  - 她写中文就用中文回；简洁、可执行，不拍马屁、不灌水。
  - 看到坏的就修，别只报告。
  - 能并行就并行。
  - API key / token / 密码**禁止硬编码**，一律走环境变量 / `.env`。

---

## 1. 项目目标（0.1 版本）

解决简历供给不足：人均每日有效简历 **5 份 → 50 份**。

关键结果：
- [ ] BOSS 公共邮箱通路日同步 ≥30 份
- [ ] 浏览器插件（脉脉 + 公域人才库）日采集 ≥15 份
- [ ] 人才库总简历数（1 周内）≥ 500
- [ ] 有效简历率（4 要素：完整简历 + 手机号 + 求职意向 + 薪资职级）≥ 60%

项目路径：`/Users/ashley/Downloads/ttc的交易系统` · 分支 `feature/merge-talentmatch`
详细进度见 [PROGRESS.md](PROGRESS.md)，已知问题审计见 [CLAUDE_AUDIT.md](CLAUDE_AUDIT.md)。

---

## 2. 统一云端数据实例（核心资产）

所有候选人、简历、对话记忆已统一到一个云端数据库，三个 AI 工具共用一套上下文。

- **阿里云 RDS MySQL 8.0**（实例 `rm-bp12ok9so2ma3i3j7`），公网端点 `ttc-rds-public-0707.mysql.rds.aliyuncs.com:3306`
- 库 `ttc_talent`，账号 `ttc_sync`；连接配置在项目根 `.env`（`RDS_HOST/USER/PASSWORD`，勿提交）
- 白名单 `0.0.0.0/0` → 任何设备凭 repo + `.env` 即可直连（仅靠密码保护，注意收敛）

**数据量**：
- `cloud_candidates`：当前 **0**（已被清空；源数据仍在本地 ttc_daemon 库与简历目录，`zxm-up --full` 可重新同步回 316）
- `memories`：758 条，**全部已生成语义向量**。来源覆盖三个工具的**全部对话**：Claude Code（`~/.claude/projects`）、Codex（`~/.codex/sessions`）、OpenCode（`~/.local/share/opencode/opencode.db`）、codex 对话导出、ttc_daemon ingest。

**实时同步**：`save_candidate()` / `ingestion.pipeline` 入库成功后自动 upsert 到云端（失败不阻塞本地）。
**定时同步**：cron `17,47 * * * *` 跑 `scripts/cron_sync_ttc_daemon_to_cloud.sh`，日志 `logs/cloud_sync_cron.log`。
**一键同步**：终端跑 `zxm-up`（全局命令，幂等）—— 起服务 + 同步全部对话/工件 + 生成向量。加 `--full` 才额外同步候选人。

---

## 3. 读写数据：用 `zhongxiaomi` MCP（首选）

已注册到 Claude Code / OpenCode / Codex 的 MCP 服务器 **`zhongxiaomi`**，直连云端 RDS。**任何有 `.env` 凭据的电脑都能读也能写。**

**读工具：**

| 工具 | 用途 |
|---|---|
| `cloud_stats` | 数据量统计 |
| `search_candidates` | 候选人关键词检索（姓名/公司/简历正文） |
| `list_recent_candidates` | 最近入库候选人 |
| `get_candidate` | 按 fingerprint 取完整记录 |
| `search_memories` | 对话/工件记忆关键词检索 |
| `semantic_search_memories` | 语义（向量余弦）检索记忆 |

**写工具：**

| 工具 | 用途 |
|---|---|
| `add_memory` | 写入一条记忆（决策/摘要/上下文），写入后自动向量化，立刻可语义检索 |
| `add_candidate` | 新增/更新一个候选人（fingerprint 幂等） |

**用法**：直接用自然语言对 claude 提需求即可，它会自动调这些工具。例：
- 读："查一下我们之前关于云端统一的讨论" / "有没有懂微服务的候选人" / "统计下现在库里多少条记忆"
- 写："把这个决定记到长期记忆：……" / "新增一个候选人：张三，xx 公司，电话 ……"

**要查任何候选人、简历、历史对话 → 优先调这些 MCP 工具，而不是翻本地文件。**

本机 HTTP 端点（仅本机，跨设备走 MCP）：`http://127.0.0.1:8765/api/cloud/search?q=...`、`/api/cloud/candidates`。

**语义检索**：本地 fastembed（`BAAI/bge-small-zh-v1.5`，512 维，无需 API key）。`memories.embedding` 存 JSON 向量，余弦在 Python 端算。回填：`scripts/backfill_memory_embeddings.py`。

---

## 4. 代码结构

- **`candidate-collector/`**：简历采集器 v2。浏览器扩展（BOSS/脉脉/猎聘）、本地解析（PDF/DOC/DOCX/OCR）、邮箱同步、统一入库流水线、JD 对齐评分、FastAPI（`app.py`，端口 8765）。`cloud_sync/` 是云端同步层（client/config/schema/embeddings/mcp_server）。
- **`ttc_daemon/`**：AI 招聘工作流。Mission 状态机（created→jd_parsed→sourcing→scored→human_pending→feedback→closed）、多 agent 编排、人才库适配器、人工任务调度 + 飞书通知。
- **`ttc-automation/`**：automation / talentmatch。
- **`scripts/`**：批量导入、手机号恢复、云端同步、cron 包装。
- **Skills**：talent-search、ttc-crm-*、jobwater、linkedin-search-skill。

⚠️ 目录名含连字符 `candidate-collector`，脚本需 `sys.path.insert` 或 `PYTHONPATH` 指向它；用 venv：`candidate-collector/.venv/bin/python`。

---

## 5. 当前优先事项（阻塞 0.1 版本）

来自 [CLAUDE_AUDIT.md](CLAUDE_AUDIT.md)，按优先级：
1. `candidate-collector/adapters/feishu_base.py`：lark-cli 命令参数错误 → 飞书写入可能失败
2. `candidate-collector/parsers/unified_parser.py`：姓名/公司/职位/毕业年份/城市提取误识别
3. `candidate-collector/models.py`：指纹判重、无效手机号、JSON 序列化
4. `candidate-collector/ingestion/pipeline.py`：去重逻辑错误、假成功记录

之后：飞书写入端到端验证 → 浏览器插件改发 ttc_daemon → 有效简历 4 要素校验 → 无手机号简历撞库补全 → 增长 dashboard。

---

## 6. 避坑清单（已踩过）

- MySQL **不支持** `ILIKE`（用 `LIKE`）、`CREATE INDEX IF NOT EXISTS`、`NULLS LAST`、`ADD COLUMN IF NOT EXISTS`。
- `OPENAI_NEXT_API_KEY` **已过期**（api.openai-next.com 返回"该令牌已过期"）——这是 embedding 改用本地 fastembed 的原因。
- pymysql 绑定 dict 到 JSON 列会报错，需先 `json.dumps`。
- 云端同步失败必须 try/except 包裹，绝不阻塞本地入库。

---

## 7. 工作约定

- 大任务拆阶段，每阶段结束 `git commit`；commit message 结尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- 上下文接近上限时先更新 [PROGRESS.md](PROGRESS.md) 再 `/compact`。
- 进度与记忆同步到项目 memory（`ttc-cloud-data-instance`、`ttc-project-progress-2026-07-13`）。
- 换 API key 后用 `claude --resume` 续接。

---

## 8. 跨设备一致性（读 + 写）

`ttc_sync` 账号对 `ttc_talent` 库是 **ReadWrite**，所以任何装了凭据的电脑都能读也能写。

在任意一台电脑获得相同能力：
```bash
git clone <repo> && cd ttc的交易系统
cp .env .env   # 带 RDS_HOST/USER/PASSWORD（这是写入的钥匙，勿提交）
uv pip install -p candidate-collector/.venv pymysql mcp fastembed httpx
# 一键起服务+同步（可选）：把 zxm-up 复制到 PATH 或直接从仓库跑 bash scripts/...
```
然后注册 `zhongxiaomi` MCP（命令 `candidate-collector/.venv/bin/python -m cloud_sync.mcp_server`，env `PYTHONPATH=candidate-collector`）。本 `CLAUDE.md` 随仓库走，自动注入。

**写入有两种方式**：
1. **MCP 写工具**：`add_memory` / `add_candidate`（任意电脑，自然语言触发）。
2. **脚本同步**：在仓库里跑 `candidate-collector/.venv/bin/python scripts/sync_all_conversations_to_cloud.py`、`backfill_memory_embeddings.py` 等（即 `zxm-up` 内部做的事）。
