# TTC 招聘量化决策系统 & 简历含金量评估
## 完整技术规划文档 v2.0
> 2026-06-29 | 面向：研发实习生 + 技术负责人

---

## 0. 核心结论（先读这里）

**不需要新建系统。**

TalentMatch v7 已在线（yorkteam.cn），271 个测试通过，有完整的简历解析、匹配引擎、飞书 Bot、React 前端。

Wendy 的需求（简历含金量评分）= **在现有系统里加一个 `GoldScoreEngine` 模块**，强化已有的 `company_tier` 维度，补充"技术深度/项目所有权/证据可信度"判断，并给顾问出追问题。

TTC 量化决策系统（需求1）= **在 TalentMatch 基础上扩展职位侧能力**（职位监听、职位评分、仓位状态机），复用现有候选人侧的全部能力。

```
现有 TalentMatch v7（候选人侧）
├── 简历解析（resume_parser/）
├── 8维度匹配引擎（unified_engine.py）
│   └── company_tier 0.12权重 ← Wendy需求在这里扩展
├── 飞书 Bot（app/feishu/）
├── Bradley-Terry 反馈学习（feedback_learner.py）
└── React 前端 + FastAPI 后端

新增模块（本次规划）
├── GoldScoreEngine（简历含金量）← 需求2，4周
└── Recruiting Quant OS（职位侧）← 需求1，分Phase
```

---

## 目录

1. [需求2：GoldScoreEngine（简历含金量）](#1-需求2-goldscoreengine简历含金量)
2. [需求1：Recruiting Quant OS（职位侧扩展）](#2-需求1-recruiting-quant-os职位侧扩展)
3. [技术选型](#3-技术选型)
4. [数据模型变更](#4-数据模型变更)
5. [API 接口](#5-api-接口)
6. [测试与验收](#6-测试与验收)
7. [风险与边界](#7-风险与边界)
8. [里程碑计划](#8-里程碑计划)

---

## 1. 需求2：GoldScoreEngine（简历含金量）

### 1.1 问题定义

**Wendy 原话**：
> "简历看着花里胡哨的，看着也有Agent，有创业公司，但是被创始人喷太菜。很多时候推人不准就是我把我觉得好的给客户了，不过客户是懂行的，真能看懂简历，所以他会说：做得浅，菜，不深。"

顾问看到的 vs 客户（技术创始人）看到的：

| 顾问视角 | 客户真实判断 |
|---|---|
| "做过 AI Agent" | "LangChain 调包侠" |
| "在字节工作" | "边缘部门，OA系统，没含金量" |
| "创业过" | "ToVC项目，产品没上线" |
| "写了5年Python" | "全是CRUD，无系统设计" |
| "主导过微服务改造" | "只改了配置，没碰核心链路" |

**系统目标**：不针对特定JD，评估候选人本身的通用技术含金量，并给顾问出追问题。

### 1.2 集成位置

```
talentmatch/matching/
├── unified_engine.py          # 现有 8维度匹配引擎
├── gold_score_engine.py       # 新增：含金量评分引擎
├── feedback_learner.py        # 现有：Bradley-Terry 反馈学习
└── config/
    ├── scoring_weights.json   # 现有：匹配权重
    └── gold_score_rubric.json # 新增：含金量评分Rubric（可配置）
```

**与现有引擎的关系**：
- `GoldScoreEngine` 独立运行，输入简历，输出 `GoldScore` 对象
- `GoldScore.overall_score` 写入 `CandidateVector.implicit_score`，替换现有的 `company_tier` 维度打分
- `GoldScore.company_analysis` 可直接补充 `CandidateVector.company_tier` 字段
- 现有 `candidate_profiles` 表新增 `gold_score` JSONB 列，不破坏现有 schema

### 1.3 评分维度（Rubric v1）

| 维度 | 权重 | 判断内容 | 判断策略 |
|---|---:|---|---|
| 技术深度 | 25% | 原理理解/边界意识/权衡分析，还是调包侠 | LLM CoT |
| 项目所有权 | 15% | 参与/主导/独立负责 | LLM + 关键词规则 |
| 复杂度与规模 | 15% | DAU/并发/延迟/数据量/团队范围 | 实体抽取 + LLM |
| 结果与影响 | 15% | 是否有可验证量化指标 | 实体抽取 |
| 工程完整性 | 10% | 测试/监控/部署/安全/维护 | 关键词 + LLM |
| 经历含金量 | 10% | 公司级别+部门权重（有证据才打分） | 知识库 + LLM |
| 成长与连续性 | 5% | 职责是否升级、能力是否积累 | LLM |
| 证据可信度 | 5% | 描述是否具体/一致/可验证 | LLM |

**关键规则**：
- 不能仅凭公司名给高分（"字节"≠高分）
- 未知部门标 `evidence: unknown`，不得猜测
- "表达漂亮但证据浅"和"深但表达差"必须区分
- 每个评分结论必须绑定简历原句（evidence binding）

### 1.4 输出格式

```python
@dataclass
class GoldScore:
    overall_score: int            # 0-100
    confidence: str               # high / medium / low
    level: str                    # 扎实 / 中上 / 中等 / 较浅 / 不足
    dimensions: Dict[str, DimDetail]
    red_flags: List[Flag]         # 一票否决级别
    yellow_flags: List[str]       # 需验证的疑点
    company_analysis: List[CompanyAssessment]
    verification_questions: List[VerificationQ]  # 追问题
    recommendation: str
    rubric_version: str

@dataclass
class DimDetail:
    score: int                    # 0-100
    evidence: List[str]           # 绑定的简历原句
    comment: str
    unknown_items: List[str]      # 无法判断的项目

@dataclass
class VerificationQ:
    question: str
    validates: str                # 验证什么
    dimension: str                # 对应哪个维度
```

**分级含义**：

| 分数 | 等级 | 操作建议 |
|---|---|---|
| 80-100 | 扎实 | 可重点推荐，无需特别验证 |
| 65-79 | 中上 | 推荐但需用追问题验证 |
| 45-64 | 中等 | 视客户要求，普通职位可推 |
| 25-44 | 较浅 | 不推给技术标准高的客户 |
| 0-24 | 不足 | 不建议推荐 |

### 1.5 LLM 评分策略（防随机波动）

> ⚠️ HackerRank 开源 ATS 已被实测：同一份简历100次运行得分 27-99，波动极大。不能一次性让 LLM 打总分。

**Chain-of-Thought 分步评分**：

```
Step1: 提取所有项目的关键技术声明（结构化JSON）
Step2: 对每个声明，判断"有证据"还是"缺证据"，绑定原句
Step3: 对有证据的声明，判断深度（原理/边界/权衡）
Step4: 对每个维度，综合所有证据给0-100分
Step5: 检查一致性（时间冲突、指标异常、描述模板化）
Step6: 生成追问题
```

**一致性保障**：
- `temperature=0`，固定系统 Prompt
- 同一份简历跑3次，取中位数
- 差异 > 10分触发人工复核 flag

**推荐模型**：Claude Sonnet 4.6（长上下文，推理能力强）

### 1.6 公司含金量知识库

现有 `unified_engine.py` 已有 `company_tier` 字段（T0/T1/T2/T3），但只做 JD 匹配，不做部门含金量判断。

新增 `matching/config/company_knowledge.json`：

```json
{
  "字节跳动": {
    "tier": "T2",
    "core_depts": ["推荐算法", "TikTok", "抖音", "飞书核心", "广告"],
    "edge_depts": ["内部OA", "HR系统", "非核心工具", "法务系统"],
    "dept_inference": "根据项目描述的业务关键词判断部门类型"
  },
  "阿里巴巴": {
    "tier": "T2",
    "core_depts": ["淘宝/天猫核心", "阿里云核心", "支付宝核心", "搜索推荐"],
    "edge_depts": ["内部工具", "小业务线", "孵化项目"]
  }
}
```

未知公司：LLM 基于融资信息/规模/业务判断，标注 `source: llm_inferred`，`confidence: low`。

### 1.7 追问题生成策略

根据低分维度和红黄旗，自动生成 5-10 个定向追问题：

| 策略 | 示例问题 | 验证目标 |
|---|---|---|
| 技术深度探测 | "你提到做过XX系统，当时为什么选这个方案而不是YY？遇到什么 trade-off？" | 区分"做过"和"深入理解" |
| 项目参与度 | "在XX项目中你具体负责哪些模块？架构是你设计的还是参与的？" | 区分"主导"和"参与" |
| 量化成果追问 | "你提到性能提升30%，这个30%怎么测出来的？基线是什么？样本量多大？" | 区分真实数据和编造数据 |
| 失败经验 | "在做XX过程中犯过什么技术错误？怎么发现和修复的？" | 深度浅的人说不出来 |
| 公司部门含金量 | "在XX公司，你们团队规模多大？业务在整个公司是什么定位？" | 判断是否边缘部门 |

### 1.8 集成到现有匹配流程

```
简历上传
   ↓
resume_parser（现有）→ CandidateVector
   ↓
GoldScoreEngine（新增）→ GoldScore
   ↓
GoldScore 写入 candidate_profiles.gold_score（JSONB）
GoldScore.overall_score → CandidateVector.implicit_score（现有字段）
   ↓
UnifiedMatchEngine（现有）→ MatchResult
   ↓
前端展示：匹配分 + 含金量分 + 追问题
```

**Bradley-Terry 反馈回流**（现有功能）：
- 顾问修改含金量分数 → 记录为 feedback
- `feedback_learner.py`（每小时）→ 调整 `scoring_weights.json` 中 `company_tier` 的权重
- 客户反馈"菜/不深" → 写入 feedback 标记 loser → 进入 BT 学习

---

## 2. 需求1：Recruiting Quant OS（职位侧扩展）

### 2.1 现有系统已有什么

TalentMatch v7 已经解决了候选人侧的全部问题：

| 能力 | 现有状态 |
|---|---|
| 简历解析 | ✅ `resume_parser/` |
| 候选人语义检索 | ✅ Sentence Transformers + 向量召回 |
| 多维匹配打分 | ✅ 8维度 + 可配置权重 |
| 飞书 Bot 通知 | ✅ `app/feishu/` |
| 反馈学习 | ✅ Bradley-Terry 每小时 |
| React 前端 | ✅ Candidates/Jobs/Match/Stats |

**缺少的是职位侧能力**：

| 能力 | 现有状态 | 需要新增 |
|---|---|---|
| 职位自动监听 | ❌ 手动录入 | 飞书群消息 → 自动解析职位 |
| 职位评分 | ❌ 无 | 客户质量/需求清晰度/供给 → 综合分 |
| 仓位状态机 | ❌ 无 | DISCOVERED→TRIAL→ACTIVE→SCALE_UP/DOWN→STOP |
| 反馈追踪 | ❌ 无 | 推荐后追踪面试/Offer进展 |
| 动态仓位决策 | ❌ 无 | 根据反馈自动加仓/减仓/止损 |

### 2.2 仓位状态机

```
DISCOVERED（发现职位）
    │
    ├─[评分≥40]→ TRIAL（小仓试投：推1-3人，等24h）
    │                │
    │                ├─[反馈正向]→ ACTIVE（标准投入：推3-5人）
    │                │                │
    │                │                ├─[面试+正向]→ SCALE_UP（重仓）
    │                │                │
    │                │                └─[72h无反馈/需求变化]→ SCALE_DOWN
    │                │                                              │
    │                └─[48h无反馈]→ SCALE_DOWN                    └─[持续无进展]→ STOP
    │
    └─[评分<40]→ WATCHING（观察，不投入）
```

所有状态迁移记录：触发信号 + 规则版本 + 操作者（human/system）+ 时间戳。人工可覆盖。

### 2.3 职位评分公式

```
职位投入分 =
  需求清晰度  × 0.20   （JD完整度、薪资合理性、要求明确）
  + 客户反馈速度 × 0.20   （历史响应时间、面试率、Offer率）
  + 人才供给度  × 0.15   （内部库存、外部可搜索性、历史同类成功）
  + 历史转化率  × 0.20   （同公司/同类职位成交记录）
  + 收益预期   × 0.15   （公司吸引力、招聘紧急度、预算确定性）
  + 数据完整度  × 0.10   （信息完整程度）
```

权重配置化，放 `matching/config/job_scoring_weights.json`。

### 2.4 职位侧新增模块

```
talentmatch/
├── matching/
│   ├── gold_score_engine.py        # 需求2
│   ├── job_score_engine.py         # 新增：职位评分
│   └── position_allocator.py       # 新增：仓位状态机
├── app/
│   ├── api/
│   │   ├── jobs.py                 # 现有
│   │   ├── gold_score.py           # 新增：含金量API
│   │   └── allocation.py           # 新增：仓位管理API
│   └── feishu/
│       ├── webhook.py              # 现有：飞书消息接收
│       └── job_listener.py         # 新增：职位监听解析
```

### 2.5 飞书群监听（Phase 1 关键）

现有 `app/feishu/webhook.py` 已接收飞书消息。需要在此基础上新增：

1. 识别消息是否包含职位信息（LLM 判断）
2. 提取职位结构化信息（JD解析）
3. 去重（向量相似度判断是否是已有职位的更新）
4. 生成 `JOB_NEW` 事件 → 写入职位库 → 触发评分 → 通知相关顾问

### 2.6 人机分工

| 角色 | AI 负责 | 人类负责 |
|---|---|---|
| 职位识别 | 自动监听飞书群、解析JD、去重 | 补充非标需求、确认紧急度 |
| 候选人匹配 | 搜索、排序、推荐理由（现有能力） | 判断AI结果可用性、打标 |
| 仓位决策 | 自动加减仓建议 | 最终确认或覆盖 |
| 反馈收集 | 自动追踪、提醒超时 | 录入非结构化反馈 |
| 候选人沟通 | ❌ 不介入 | 100% 人工 |
| 高阶非标岗位 | ❌ 不介入 | 100% 人工 |

---

## 3. 技术选型

### 3.1 现有技术栈（不变）

| 层 | 技术 | 状态 |
|---|---|---|
| 后端 | Python FastAPI | ✅ 已在线 |
| 数据库 | SQLite + WAL + 连接池 | ✅ 已在线 |
| 向量检索 | Sentence Transformers (MiniLM-L12) | ✅ 已在线 |
| 反馈学习 | Bradley-Terry | ✅ 已在线 |
| 飞书集成 | Lark Open API + Bot | ✅ 已在线 |
| 前端 | React + Vite | ✅ 已在线 |
| 测试 | pytest 271 passed | ✅ 已在线 |

### 3.2 新增技术（最小化新依赖）

| 用途 | 选型 | 理由 |
|---|---|---|
| 简历含金量评分 | Claude Sonnet 4.6 | 长上下文，推理强，已有API |
| 文档解析（兜底） | unstructured / pdfplumber | 补充现有 resume_parser 能力 |
| 职位监听 JD 解析 | GPT-4o-mini 或 Qwen-Turbo | 结构化任务，价格便宜 |
| 向量库扩容（未来） | pgvector（PG插件） | 现有SQLite足够，200K+数据再升级 |

**不引入**：Temporal、Prefect、Kafka（现有 FastAPI 后台任务 + scheduler_monitor 已够用，过度工程化）

### 3.3 LLM 成本估算

| 任务 | Token | 估算费用 |
|---|---|---|
| 含金量评分（CoT，5步） | ~4000 tokens/份 | ~0.20元/份 |
| JD解析 | ~1000 tokens | ~0.03元/份 |
| 追问题生成 | ~800 tokens | ~0.04元/份 |

每天处理50份简历 + 20个职位 ≈ 11元/天，可接受。

---

## 4. 数据模型变更

### 4.1 新增字段（对现有表的最小侵入）

```sql
-- candidate_profiles 表新增
ALTER TABLE candidates ADD COLUMN gold_score JSON;
-- gold_score 结构：见 GoldScore dataclass
-- 现有 implicit_score 字段复用存储 gold_score.overall_score

-- jobs 表新增
ALTER TABLE jobs ADD COLUMN job_score JSON;
ALTER TABLE jobs ADD COLUMN allocation_level INTEGER DEFAULT 0;
ALTER TABLE jobs ADD COLUMN allocation_state TEXT DEFAULT 'WATCHING';
ALTER TABLE jobs ADD COLUMN state_history JSON;
```

### 4.2 新增表

```sql
-- 信号事件流
CREATE TABLE signal_events (
    id TEXT PRIMARY KEY,
    event_type TEXT,     -- JOB_NEW / JOB_UPDATED / FEEDBACK / CHASING
    source TEXT,         -- feishu_group / crm / manual
    job_id TEXT,
    payload JSON,
    processed INTEGER DEFAULT 0,
    created_at TEXT
);

-- 人工任务
CREATE TABLE human_tasks (
    id TEXT PRIMARY KEY,
    task_type TEXT,
    assignee TEXT,
    description TEXT,
    deadline TEXT,
    completion_criteria TEXT,
    status TEXT DEFAULT 'pending',
    result JSON,
    created_at TEXT
);
```

现有 `UNIFIED_SCHEMA`（`storage/sqlite_common.py`）基础上追加，不破坏现有测试。

---

## 5. API 接口

### 含金量评分

```
POST /api/v1/candidates/{id}/gold-score
    触发对已有候选人的含金量评分（异步）
    Response: { "task_id": "uuid", "status": "processing" }

GET  /api/v1/candidates/{id}/gold-score
    获取含金量评分结果
    Response: GoldScore JSON

POST /api/v1/candidates/{id}/gold-score/feedback
    顾问反馈（分数修正 + 客户评价）
    Body: { "reviewer": "wendy", "actual_level": "不深", "score_override": 45 }
```

### 职位仓位管理

```
GET  /api/v1/jobs/{id}/allocation
    获取当前仓位状态
POST /api/v1/jobs/{id}/allocation/override
    人工覆盖仓位决策
    Body: { "new_level": 2, "reason": "客户反馈很快" }
GET  /api/v1/jobs/{id}/signals
    查看该职位的信号事件历史
```

---

## 6. 测试与验收

### 6.1 M0 准备工作（第一周，必须先做）

1. Wendy 提供 **20-50 份脱敏工程简历**（去姓名/手机/邮箱）
2. Wendy 对每份简历打分：好/中/差 或 1-5分，并记录理由
3. 整理历史上客户说"菜/不深"的具体案例（简历+反馈）
4. 这批数据 = GoldScoreEngine 的验收基准集

### 6.2 含金量评分器验收标准

| 指标 | 目标 | 测试方式 |
|---|---|---|
| 一致性：同简历重复评分波动 | ≤ 8分 | 同一份跑5次，取极差 |
| 与顾问评分相关性（Spearman ρ） | ≥ 0.70 | 20份基准集盲测 |
| 客户说"不深"时 AI 分 < 65 | ≥ 80% | 历史案例回测 |
| 每份简历追问题数量 | 5-10个 | 统计 |
| 红旗识别准确率（顾问确认） | ≥ 75% | 人工确认 |

**验收不以"模型觉得合理"为准**，以顾问评分一致性和客户反馈相关性为准。

### 6.3 集成测试

```python
# 新增测试文件
talentmatch/tests/
├── test_gold_score_engine.py      # 含金量评分单元测试
├── test_gold_score_consistency.py # 一致性测试（跑5次）
├── test_job_score_engine.py       # 职位评分测试
└── test_position_allocator.py     # 状态机测试
```

目标：在现有 271 passed 基础上，新增 40-60 个测试，保持 0 failed。

### 6.4 离线回放（Phase 2，上仓位状态机前）

- 用历史职位数据跑离线状态机
- 对比 AI 仓位决策 vs 顾问实际投入时间
- **不自动触达真实候选人**，直到离线验证通过

---

## 7. 风险与边界

### 7.1 不做的事

| 功能 | 原因 |
|---|---|
| 小红书多账号自动发布 + 封号轮换 | 平台滥用风险、账号安全、IP封禁风险 |
| 绕过 Boss/脉脉反爬限制的批量抓取 | 违反平台协议，法律风险 |
| 候选人自动触达（发消息/打电话） | 合规红线，全程人工 |

### 7.2 AI 评分局限性

- **含金量判断不作为唯一淘汰依据**，必须允许顾问复核覆盖
- 公司/部门含金量必须有简历原文证据，禁止模型猜测未知部门
- 一致性波动通过 CoT + 多次取中位数控制，但仍需人工复核 flag

### 7.3 数据安全

- 候选人数据脱敏存储（不存真实姓名/手机，只存内部ID）
- 分级授权：顾问只能看自己负责的候选人
- 现有安全基线：P0=0, P1=0, P2=0，新增代码必须通过同等审计

### 7.4 系统上限

含金量评分质量 = 线上数据质量：
- 简历描述越模糊 → 评分可信度越低（自动标注 `confidence: low`）
- 冰山下候选人（不在系统里）→ 系统无法处理，仍需人工
- 非标高阶职位 → 不进入量化流程

---

## 8. 里程碑计划

### 简历含金量（需求2，集成到 TalentMatch）

| 周 | 工作内容 | 交付物 | 负责 |
|---|---|---|---|
| W1 | 收集基准简历，Wendy打分，定义Rubric v1 | 基准数据集（脱敏）+ rubric JSON | Wendy + 研发 |
| W2 | 实现 GoldScoreEngine + CoT Prompt（分步5阶段） | 本地可运行的评分函数 | 研发 |
| W3 | 一致性测试（跑5次取中位数）+ 公司知识库（50家） | 评分API（内测版）+ 测试通过 | 研发 |
| W4 | 追问题生成 + 集成到 candidate 详情页 + 飞书Bot推送 | 顾问可用的内测版 | 研发 |
| W5 | 与 Wendy 盲测（20份基准集）+ 根据分歧修改Rubric | Spearman ρ ≥ 0.70 | Wendy + 研发 |
| W6 | 修复 + 上线 + 顾问反馈闭环（BT 学习接入） | v1 正式上线 yorkteam.cn | 研发 |

### 招聘量化系统（需求1，职位侧扩展）

| Phase | 时间 | 目标 | 关键交付 |
|---|---|---|---|
| Phase 1 | M2-M3 | 职位监听 | 飞书群 → 自动解析职位 → 写入DB → 通知顾问 |
| Phase 2 | M4-M5 | 职位评分 + 仓位状态机 | job_score_engine + position_allocator |
| Phase 3 | M6-M8 | 闪电战Sourcing | 职位评分 → 自动触发候选人搜索 → 顾问确认 |
| Phase 4 | M9-M11 | 反馈追踪 + 加减仓决策 | 信号事件 → 自动仓位变更 → 顾问审批 |
| Phase 5 | M12+ | 3-5个标准职位全流程试点 | 离线回放验证后 → 真实运行 |

---

## 附录 A：现有系统关键文件速查

```
talentmatch/
├── matching/unified_engine.py      # 8维度匹配引擎（主入口）
├── matching/config/scoring_weights.json  # 权重配置（可热更新）
├── matching/feedback_learner.py    # Bradley-Terry 反馈学习
├── resume_parser/                  # 简历解析
├── app/__init__.py                 # FastAPI 应用 + 后台任务
├── app/feishu/webhook.py           # 飞书 Webhook 接收
├── storage/sqlite_common.py        # 统一 Schema
├── storage/connection_pool.py      # SQLite 连接池
└── tests/                          # 271 个测试
```

## 附录 B：开源参考项目

- [OmkarPathak/ResumeParser](https://github.com/OmkarPathak/ResumeParser) — 本地LLM简历解析（隐私友好）
- [wespiper/pyresume](https://github.com/wespiper/pyresume) — 结构化提取，有置信度
- [vectornguyen76/resume-ranking](https://github.com/vectornguyen76/resume-ranking) — FastAPI + LLM候选人排序参考
- HackerRank hiring-agent — **反面教材**：non-determinism 严重，同简历得分27-99
- [opencats/OpenCATS](https://github.com/opencats/OpenCATS) — 猎头专用开源ATS，架构参考

---

*文档版本 v2.0 | 2026-06-29*  
*基于：需求1、需求2、TalentMatch v7 工程档案、子系统问题清单*  
*下一步：把 W1 样本收集计划发给 Wendy（20-50份脱敏简历 + 人工打分）*
