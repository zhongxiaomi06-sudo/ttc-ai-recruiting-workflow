# TTC AI 猎头工作流 · 进度与路线图

> 基于方案四（AI 主导 + 人机调度架构）设计文档审阅生成
> 审阅日期：2026-07-08
> 最后更新：2026-07-08（Week 1+2 实施完成）
> 目标读者：AI 开发 Agent（请严格按本文档执行）

---

## 一、当前进度总览

```
████████████████████████  90-95%

已完成：核心架构、摄入链路、状态机、人机调度、HTML 任务页、
       LLM CoT 评分引擎、反馈闭环、合规审核流程、客户简报、端到端测试
待完成：真实 API 对接、多 Mission 并行、仓位管理、代码清理
```

### 1.1 设计文档 Checklist 实际状态

| # | 条目 | 文档自评 | 实际状态 |
|---|------|---------|---------|
| 1 | 自动化读取飞书/ChatGPT/candidate-collector 输入 | ✅ done | ✅ 完成 |
| 2 | 本地 TTC Daemon 可运行 | ✅ done | ✅ 完成 |
| 3 | 输出架构 HTML | ✅ done | ✅ 完成 |
| 4 | **Orchestrator 状态机与 Agent 编排骨架** | ☐ todo | ✅ **已完成** |
| 5 | **HTML 猎头电话任务页与 Dashboard** | ☐ todo | ✅ **已完成** |
| 6 | 对接公司人才库 API 跑通端到端 Mission | ☐ todo | 🟡 代码就绪，缺 API 凭证 |
| 7 | 接入真实 GoldScoreEngine / TalentMatch 评分 | ☐ todo | 🟢 **LLM CoT 评分引擎就绪，待对接真实 API** |

### 1.2 架构五层完成度

| 架构层 | 完成度 | 关键文件 |
|--------|--------|---------|
| 输入源层（飞书/ChatGPT/Collector/PDF/Web） | 95% | [ttc_daemon/link_reader.py](ttc_daemon/link_reader.py) |
| Agent 层（JD/搜索/评分/话术/富化/调度/反馈） | 95% | [ttc_daemon/agents/](ttc_daemon/agents/) |
| 编排层（Orchestrator + 状态机 + 任务队列） | 95% | [ttc_daemon/agents/orchestrator.py](ttc_daemon/agents/orchestrator.py) |
| Human Tool 层（电话/审核/合规/异常处理） | 90% | [ttc_daemon/agents/human_dispatch.py](ttc_daemon/agents/human_dispatch.py) |
| 展示层（Dashboard / 任务页 / 客户简报） | 90% | [ttc_daemon/templates/](ttc_daemon/templates/) |

---

## 二、已完成的模块明细

### 2.1 摄入链路（capture → read_job → classify → normalize → route）

**完全对齐设计文档第 3.3 节。**

| 阶段 | 实现文件 | 状态 |
|------|---------|------|
| capture | [ttc_daemon/main.py](ttc_daemon/main.py) — `/ingest/*` 端点 | ✅ |
| read_job | [ttc_daemon/ingestion/read_job_runner.py](ttc_daemon/ingestion/read_job_runner.py) | ✅ |
| classify | [ttc_daemon/ingestion/artifact_classifier.py](ttc_daemon/ingestion/artifact_classifier.py) | ✅ |
| normalize | [ttc_daemon/ingestion/normalizer.py](ttc_daemon/ingestion/normalizer.py) | ✅ |
| route | [ttc_daemon/ingestion/mission_router.py](ttc_daemon/ingestion/mission_router.py) | ✅ |

### 2.2 Orchestrator 完整状态机

**文件：** [ttc_daemon/agents/orchestrator.py](ttc_daemon/agents/orchestrator.py)

已实现的 **12 个状态**（完整版）：

```
created → jd_parsed → sourcing → scored → human_review → calling → human_pending → feedback → closed
                ↓           ↓          ↓           ↓              ↓
          problem_pending (任意状态均可跳入，人工解决后 resume)
```

新增状态：
- `human_review` — 有 risk_flags / 置信度低的候选人先经顾问审核
- `calling` — 独立出电话任务生成阶段，再进入 `human_pending` 等待完成

核心方法：
- `start_mission()` — 创建 Mission
- `step_mission()` — 按当前状态推进一步（约 260 行完整逻辑）
- `_pause_for_human()` — 暂停并生成异常任务
- `process_pending_missions()` — 轮询推进

### 2.3 8 个 Agent

| Agent | 文件 | 完成度 |
|-------|------|--------|
| JD 解析 | [ttc_daemon/agents/jd_agent.py](ttc_daemon/agents/jd_agent.py) | ✅ |
| 人才搜索 | [ttc_daemon/agents/sourcing_agent.py](ttc_daemon/agents/sourcing_agent.py) | ✅ |
| 评分排序 | [ttc_daemon/agents/scoring_agent.py](ttc_daemon/agents/scoring_agent.py) | ✅ |
| 话术生成 | [ttc_daemon/agents/outreach_agent.py](ttc_daemon/agents/outreach_agent.py) | ✅ |
| Human 调度 | [ttc_daemon/agents/human_dispatch.py](ttc_daemon/agents/human_dispatch.py) | ✅ |
| Web 富化 | [ttc_daemon/agents/web_enrichment_agent.py](ttc_daemon/agents/web_enrichment_agent.py) | ✅ |
| 反馈学习 | [ttc_daemon/agents/feedback_agent.py](ttc_daemon/agents/feedback_agent.py) | ✅ **新建** |
| 合规检测 | [ttc_daemon/core/scoring.py](ttc_daemon/core/scoring.py) — `detect_compliance_issues()` | ✅ **新建** |

### 2.4 HTML 任务页面

| 模板 | 用途 | 状态 |
|------|------|------|
| [dashboard.html](ttc_daemon/templates/dashboard.html) | Mission 仪表盘 + 待办任务列表（含 human_review/calling 状态） | ✅ |
| [call_task.html](ttc_daemon/templates/call_task.html) | 猎头电话任务 | ✅ |
| [problem_task.html](ttc_daemon/templates/problem_task.html) | 异常处理（7 种异常类型） | ✅ |
| [review_task.html](ttc_daemon/templates/review_task.html) | 顾问审核页（含候选人对比表+风险信号） | ✅ |
| [compliance_task.html](ttc_daemon/templates/compliance_task.html) | 合规仲裁页（含风险项列表+决策表单） | ✅ |
| [generic_task.html](ttc_daemon/templates/generic_task.html) | 通用兜底页 | ✅ |
| [client_brief.html](ttc_daemon/templates/client_brief.html) | **客户简报**（岗位概要+Top 5 对比+推荐策略） | ✅ **新建** |

### 2.5 辅助系统

| 模块 | 文件 | 状态 |
|------|------|------|
| 后台调度器 | [ttc_daemon/scheduler.py](ttc_daemon/scheduler.py) | ✅ |
| 飞书 Bot 通知 | [ttc_daemon/notifications/feishu_bot.py](ttc_daemon/notifications/feishu_bot.py) | ✅ |
| 异常恢复机制 | [ttc_daemon/problem_task_manager.py](ttc_daemon/problem_task_manager.py) | ✅ |
| 多源人才召回 | [ttc_daemon/talent_db_adapter.py](ttc_daemon/talent_db_adapter.py) | ✅ |
| LLM 可插拔层 | [ttc_daemon/llm_utils.py](ttc_daemon/llm_utils.py) | ✅ |
| 审计日志 | `agent_runs` 表 | ✅ |
| 集成测试 | [ttc_daemon/tests/](ttc_daemon/tests/) — 34 个测试，<5s 完成 | ✅ **新建** |

### 2.6 评分引擎

**文件：** [ttc_daemon/core/scoring.py](ttc_daemon/core/scoring.py)

```
score_candidate()
├── LLM CoT 分步评分（6 维 × 3 次取中位数，差异 >10 触发 human_review）
│   ├── tech_depth（技术深度）
│   ├── project_ownership（项目所有权）
│   ├── complexity（复杂度）
│   ├── impact（结果影响）
│   ├── engineering_integrity（工程完整性）
│   └── company_prestige（公司含金量）
├── 兜底加权评分（jd_alignment × 0.6 + gold_score × 0.4）
├── 合规检测（detect_compliance_issues）
└── 话术生成（generate_talking_points + build_call_script）
```

---

## 三、差距分析（更新）

### ✅ 3.1 真实评分引擎 — 已完成

LLM CoT 分步评分已实现，支持：
- 6 维评分 + 证据绑定（每项分数绑定简历原句）
- risk_flags 检测（红灯 8 项 + 黄灯 8 项）
- confidence（high/medium/low）
- level（扎实/中上/中等/较浅/不足）
- verification_questions（5-10 个追问题）
- company_analysis（公司含金量分析）
- 3 次评分取中位数，差异 >10 分触发 human_review

### ✅ 3.2 反馈学习 Agent — 已完成

[ttc_daemon/agents/feedback_agent.py](ttc_daemon/agents/feedback_agent.py) 实现：
- 评分权重校准（基于关键词分析拒绝原因，调整维度权重）
- 复盘报告生成（命中率、响应率、推荐精度）
- Mission feedback 状态自动触发
- `get_calibrated_weights()` 跨 Mission 汇总

### ✅ 3.3 human_review 审核流程 — 已完成

`scored` 状态处理逻辑：
- 有 red flag / needs_human_review / confidence=low → `human_review`（创建 review_task）
- 无风险 → 直接 `calling`
- 审核通过 → `calling`；驳回 → `closed`；需要补充 → `problem_pending`

### ✅ 3.4 端到端集成测试 — 已完成

34 个测试（2 个 LLM 依赖跳过），覆盖：
- 摄入链路（classify → normalize → route）
- 状态机全流程（created → closed）
- 异常恢复（problem_task → resume）
- 评分引擎（兜底评分、合规检测、话术生成）
- 运行时间 <5 秒

### ✅ 3.5 客户简报 — 已完成

- [client_brief.html](ttc_daemon/templates/client_brief.html) — 岗位概要 + Top 5 对比表 + 推荐策略 + 下一步建议
- [outreach_agent.py](ttc_daemon/agents/outreach_agent.py) — `generate_client_brief()` + `create_client_brief_task()`

### ✅ 3.6 calling 状态 — 已完成

状态机已更新为：
```
scored → human_review（有风险）→ calling（生成电话任务）→ human_pending（等待完成）→ feedback
```

### ✅ 3.7 合规仲裁流程 — 已完成

`detect_compliance_issues()` 在评分阶段检测：
- 红灯信号（学历造假、竞业限制等）
- 来源不可信
- 数据冲突
- 竞业限制关键词

检测到问题后自动创建 `compliance` 类型 human_task。

---

## 四、待完成（后续迭代）

### 🟡 P1 — 需要真实凭证

| 项目 | 说明 |
|------|------|
| 对接公司人才库 API | 代码就绪，需 API 凭证 |
| Source 公司 MySQL 数据验证 | 配置就绪，需连接信息 |
| LLM API Key 配置 | 配置 `TTC_LLM_API_KEY` 环境变量启用 LLM CoT 评分 |

### 🟢 P2 — 增强项

| 项目 | 优先级 |
|------|--------|
| 3.8 多 Mission 并行 + 优先级队列 | 中 |
| 3.9 Recruiting Quant OS 仓位管理对接 | 中 |
| 3.10 代码清理（归档 ttc-automation/） | 低 |
| Dashboard 增强（展示评分详情、证据链） | 低 |

---

## 五、关键文件索引

### 核心文件

| 优先级 | 文件 | 说明 |
|--------|------|------|
| ⭐⭐⭐ | [ttc_daemon/agents/orchestrator.py](ttc_daemon/agents/orchestrator.py) | 状态机核心（12 状态，260 行） |
| ⭐⭐⭐ | [ttc_daemon/db.py](ttc_daemon/db.py) | 数据库模型 + 迁移 |
| ⭐⭐⭐ | [ttc_daemon/core/scoring.py](ttc_daemon/core/scoring.py) | LLM CoT 评分引擎 |
| ⭐⭐⭐ | [ttc_daemon/main.py](ttc_daemon/main.py) | API 端点 + 后台调度 |
| ⭐⭐ | [ttc_daemon/agents/human_dispatch.py](ttc_daemon/agents/human_dispatch.py) | 人机调度核心 |
| ⭐⭐ | [ttc_daemon/agents/feedback_agent.py](ttc_daemon/agents/feedback_agent.py) | 反馈学习 |
| ⭐⭐ | [ttc_daemon/agents/outreach_agent.py](ttc_daemon/agents/outreach_agent.py) | 话术 + 客户简报 |
| ⭐⭐ | [ttc_daemon/tests/](ttc_daemon/tests/) | 集成测试（34 tests） |
| ⭐ | [ttc_daemon/llm_utils.py](ttc_daemon/llm_utils.py) | LLM 通用调用 |
| ⭐ | [CONTEXT.md](CONTEXT.md) | 项目背景 |

---

*最后更新：2026-07-08 · Week 1+2 实施完成*
