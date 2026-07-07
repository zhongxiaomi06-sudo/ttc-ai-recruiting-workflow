# TTC 交易系统 · 开发上下文
> 迁移时间：2026-06-29 | 从 ~/Documents/我的过去/ 对话记录整理

---

## 一、背景与已有系统

### TalentMatch v7（基座，已上线）
- **线上地址**：yorkteam.cn，服务器 47.110.93.137
- **部署路径**：`/opt/recruit-bot-v5/`
- **本地路径**：`/Users/ashley/Documents/简历的工作信息/talentmatch/`
- **状态**：生产就绪，271 个测试全过，v7.0 审计 1250/1250 PASS

### 已有核心能力
| 模块 | 路径 | 说明 |
|------|------|------|
| 简历解析 | `resume_parser/` | PDF/DOCX → 结构化字段 |
| 8维度匹配引擎 | `matching/unified_engine.py` | 含 company_tier 权重 0.12 |
| 权重配置 | `matching/config/scoring_weights.json` | 支持热更新 |
| 反馈学习 | `matching/feedback_learner.py` | Bradley-Terry，每小时跑 |
| 飞书 Bot | `app/feishu/webhook.py` + `handlers.py` | 已修复，32 个测试通过 |
| React 前端 | `frontend/` | Candidates/Jobs/Match/Stats 四个模块 |
| FastAPI 后端 | `main.py` → `app/__init__.py` | 58 个端点，port 8878 |
| SQLite 存储 | `storage/sqlite_common.py` | WAL + 连接池 |
| 基线打分 | `matching/baseline_scorer.py` | 197行，ATS评分器 |

### 数据库现状（截至 2026-06-22）
- 候选人：63 个
- 岗位：8244 个
- 匹配记录：1971 个
- 反馈：653 条

---

## 二、本次 TTC 需求说明

### 需求2（优先做）：工程简历含金量评分 GoldScoreEngine
**来源**：Wendy 郭雯（顾问），6月26日提出
**核心痛点**：顾问看着好的简历，推给技术创始人后被说"太菜/做得浅/不深"
**目标**：对工程技术类候选人打通用含金量分，不针对特定JD

#### 评分维度（8个）
| 维度 | 权重 |
|------|------|
| 技术深度 | 25% |
| 项目所有权 | 15% |
| 复杂度与规模 | 15% |
| 结果与影响 | 15% |
| 工程完整性 | 10% |
| 经历含金量 | 10% |
| 成长与连续性 | 5% |
| 证据可信度 | 5% |

#### 关键规则
- 不能只凭公司名给高分（"字节"≠高分）
- 每个评分结论必须绑定简历原句（evidence binding）
- 同一份简历跑3次取中位数（防随机波动，temperature=0）
- 差异>10分触发人工复核 flag
- 输出5-10个追问题给顾问

#### 输出对象
```python
GoldScore(
    overall_score: int,      # 0-100
    confidence: str,         # high/medium/low
    level: str,              # 扎实/中上/中等/较浅/不足
    dimensions: Dict,        # 每维度：分+证据+未知项
    red_flags: List,
    yellow_flags: List,
    company_analysis: List,
    verification_questions: List,  # 追问题
    recommendation: str
)
```

#### 集成位置
- 新增：`talentmatch/matching/gold_score_engine.py`
- 新增：`talentmatch/matching/config/gold_score_rubric.json`
- 新增：`talentmatch/matching/config/company_knowledge.json`
- 修改：`candidate_profiles` 表新增 `gold_score` JSON 列
- `GoldScore.overall_score` → 写入现有 `CandidateVector.implicit_score`

---

### 需求1：招聘量化决策系统（Recruiting Quant OS）
**来源**：York 姚堃（老板），基于"量化基金"类比设计
**核心类比**：顾问时间=资金，职位=标的，推荐=建仓，反馈=市场信号

#### 新增模块（在 TalentMatch 基础上扩展）
```
新增：
├── matching/job_score_engine.py      # 职位评分
├── matching/position_allocator.py    # 仓位状态机
├── app/api/gold_score.py             # 含金量API
├── app/api/allocation.py             # 仓位管理API
└── app/feishu/job_listener.py        # 飞书群职位监听
```

#### 职位评分公式
```
职位投入分 =
  需求清晰度  × 0.20
  + 客户反馈速度 × 0.20
  + 人才供给度  × 0.15
  + 历史转化率  × 0.20
  + 收益预期   × 0.15
  + 数据完整度  × 0.10
```

#### 仓位状态机
```
DISCOVERED → TRIAL（小仓，推1-3人）
  → ACTIVE（标准，3-5人）→ SCALE_UP（重仓）
  → SCALE_DOWN → STOP
DISCOVERED → WATCHING（评分<40，不投入）
```

#### 新增数据库表
```sql
-- candidate_profiles 追加
ALTER TABLE candidates ADD COLUMN gold_score JSON;

-- jobs 追加
ALTER TABLE jobs ADD COLUMN job_score JSON;
ALTER TABLE jobs ADD COLUMN allocation_level INTEGER DEFAULT 0;
ALTER TABLE jobs ADD COLUMN allocation_state TEXT DEFAULT 'WATCHING';
ALTER TABLE jobs ADD COLUMN state_history JSON;

-- 新表
CREATE TABLE signal_events (...);   -- 信号事件流
CREATE TABLE human_tasks (...);     -- 人工任务派发
```

---

## 三、开发顺序

### Phase 0（W1，本周）：数据准备
1. Wendy 提供 20-50 份脱敏工程简历
2. Wendy 对每份打 好/中/差 或 1-5分，并记录理由
3. 整理历史"客户说菜/不深"的案例
4. → 这批数据是 GoldScoreEngine 的验收基准集

### Phase 1（W2-W4）：GoldScoreEngine MVP
- `gold_score_engine.py`：CoT 分步评分（6步）
- `company_knowledge.json`：初始覆盖50家公司
- 追问题生成
- API：`POST/GET /api/v1/candidates/{id}/gold-score`
- 集成到 candidate 详情页

### Phase 2（W5-W6）：验收与上线
- 与 Wendy 盲测20份基准集
- 目标：Spearman ρ ≥ 0.70，一致性波动 ≤ 8分
- BT 反馈回流接入
- 上线 yorkteam.cn

### Phase 3（M2-M3）：职位侧扩展
- 飞书群监听 → 自动解析职位
- `job_score_engine.py` + `position_allocator.py`

### Phase 4（M4+）：仓位决策 + 闪电战试点
- 3-5个标准化职位全流程自动化试点

---

## 四、验收标准

| 指标 | 目标 |
|------|------|
| 含金量评分一致性（同简历5次极差） | ≤ 8分 |
| 与顾问评分相关性（Spearman ρ） | ≥ 0.70 |
| 客户说"不深"时 AI 分 < 65 | ≥ 80% |
| 每份简历追问题数 | 5-10个 |
| 红旗识别准确率 | ≥ 75% |
| 现有测试不破坏 | 271 passed, 0 failed |

---

## 五、不做的事
- 多账号自动发小红书（平台滥用风险）
- 绕过 Boss/脉脉反爬限制的批量抓取
- 候选人自动触达（全程人工）
- 任何自动决策不加人工复核入口

---

## 六、LLM 选型
- 含金量评分：Claude Sonnet 4.6（长上下文，推理强）
- JD解析：GPT-4o-mini 或 Qwen-Turbo（结构化任务，便宜）
- 成本估算：~11元/天（50份简历+20个职位）

---

## 七、本目录文件说明

| 文件 | 说明 |
|------|------|
| `需求1` | York 原始需求文本（招聘量化决策系统） |
| `需求2` | Wendy 原始需求文本（简历含金量评分） |
| `TTC招聘量化决策系统_研发规划.md` | 需求1技术规划 |
| `TTC_技术规划_完整版.md` | 两个需求合并版完整规划 v2.0 |
| `方案一_招聘量化决策系统.html` | 需求1可视化方案（给 York/研发实习生看） |
| `方案二_简历含金量评估系统.html` | 需求2可视化方案（给 Wendy 碰需求用） |
| `简历数据/` | Wendy 提供的候选人简历 PDF（30+ 份） |
| `CONTEXT.md` | 本文件：完整开发上下文 |

---

## 八、关键联系人
- **York 姚堃**：老板，需求1发起人，最终决策者
- **Wendy 郭雯**：顾问，需求2发起人，验收人，提供基准简历
- **Ashley（钟笑咪）**：研发，TalentMatch 系统开发者

---

*最后更新：2026-06-29*
