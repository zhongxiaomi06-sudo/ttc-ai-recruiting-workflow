# 猎头子系统 v6 · 开源集成方案

> 基于 GitHub 开源仓库研究结果

---

## 一、调研结论

### 优先集成（与现有 v5 技术栈直接兼容）

| 仓库 | Stars | 复用点 | 集成方式 |
|------|-------|--------|---------|
| **agent-recruiter** | ⭐5 | Pydantic 模型 (JobRequirements/CandidateProfile/MatchScore)、多代理管道编排 (5 agents)、技能归一化匹配算法 | pip 安装 + 直接 import 使用 |
| **open-resume** | ⭐8674 | ATS 友好度检测算法、简历结构化解析逻辑 | 参考其解析架构思想，API 风格保持一致 |
| **iflow-bot** | ⭐226 | 飞书多通道消息引擎、文件下载、会话管理、流式输出 | 作为飞书 Bot 的替代/增强层 |

### 参考架构（不直接集成）

| 仓库 | Stars | 可借鉴的设计 |
|------|-------|-------------|
| smart-ats | ⭐6 | Java 体系但架构图可直接复用：RAG 语义搜索 + 异步管道 + 招聘漏斗分析 |
| LangGraph AI Interview Agent | ⭐51 | LangGraph 多代理编排设计，多层 Agent 协作模式 |
| Resume-Job-Description-Matching | ⭐186 | 技能归一化 + 多维度评分 + 排序算法思路 |

### 架构演进

```
v5 (当前)                              v6 (本次迭代)
┌─────────────┐                      ┌──────────────────┐
│ FastAPI      │                      │ FastAPI + Redis   │
│ SQLite       │     agent-recruiter  │ SQLite + ChromaDB │
│ ChromaDB     │ ───→ 模型复用 ───→   │ + Agent Pipeline  │
│ 19 个端点    │                      │ 25+ 个端点        │
│ 53 测试通过  │                      │ 70+ 测试通过      │
└─────────────┘                      └──────────────────┘
```

## 二、agent-recruiter 核心代码复用

### 2.1 Pydantic 模型复用（已有 v5 模型，扩展增强）

将 agent-recruiter 的 `models.py` 中更完善的 JobRequirements 模型整合进来：
- 增加 `responsibilities`（职责列表）
- 增加 `team`（团队字段）
- 增加信号评分维度和面试计划输出

### 2.2 技能归一化匹配（已有实现，参考增强）

agent-recruiter 的 `_normalize_skill()` 和 `compute_match_score()` 
提供了一种更模块化的匹配评分方式，我们在 v5 已有类似实现，将参考其权重分配逻辑。

## 三、v6 子系统架构

### 3.1 核心模块

```
recruit-system-v6/
├── main.py                     # FastAPI 入口 + Webhook（增强版）
├── resume_parser/              # 简历解析（复用 v5，增强）
├── job_parser/                 # JD 解析（复用 v5，增强）
├── matching/                   # 匹配引擎（复用 agent-recruiter 算法）
├── storage/                    # 存储层（复用 v5）
├── pipelines/                  # 管道（增强版 + 异步 Worker）
├── bot/                        # 飞书集成（增强版）
├── agents/                     # 多 Agent 管道（参考 agent-recruiter）
│   ├── jd_agent.py             # JD 解析 Agent
│   ├── resume_agent.py         # 简历筛选 Agent  
│   ├── match_agent.py          # 匹配评分 Agent
│   ├── outreach_agent.py       # 外联起草 Agent
│   └── orchestrator.py         # 总控 Agent
└── tests/                      # 测试（70+ 用例）
```

### 3.2 职位库 + 人才库双向匹配流程

```
飞书 Bot
  │
  ├── 发简历文件 → resume_parser → 入库人才库
  │        
  ├── 发JD文本  → job_parser  → 入库职位库
  │                
  └── /match     → orchestrator
                      ├── jd_agent（解析当前职位）
                      ├── resume_agent（搜索匹配候选人）
                      ├── match_agent（多维评分 + 潜规则加权）
                      └── response agent（生成推荐卡片）
```

## 四、实施计划

### 已完成的 v5 基线（53 测试通过）
- [x] FastAPI 19 端点
- [x] 简历解析 TXT/PDF/DOCX
- [x] SQLite + ChromaDB 存储
- [x] 10个求职搜索+更多
- [x] DashScope/Qwen LLM

### v6 新增（仍在开发中）
- [ ] 从 agent-recruiter 集成匹配算法
- [ ] 双向职位库和人才库匹配
- [ ] 更多端点和测试
- [ ] 飞书事件订阅配置
- [ ] 最终部署文档

## 五、文件变更摘要

v5（现有）→ v6（新增）：
- `main.py`：更多端点
- `agents/orchestrator.py`：新文件
- `agents/jd_agent.py`：新文件
- `agents/match_agent.py`：新文件
- 增强现有模块
