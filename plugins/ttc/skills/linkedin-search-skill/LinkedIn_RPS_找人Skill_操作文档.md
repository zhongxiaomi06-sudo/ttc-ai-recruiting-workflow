# LinkedIn RPS 找人 Skill 操作文档（可给同事机器人复用）

## 1) 适用场景
用于在**已登录 LinkedIn Recruiter（RPS）企业账号**里，执行：
- 招聘文案解析
- 搜索策略生成
- 候选人浏览与门禁判断
- 候选人排序与推荐
- 多轮反馈优化

---

## 2) 前置条件
- Browser Use Cloud 账号 + API Key
- 可用 Profile（已登录 LinkedIn Recruiter）
- 机器人可调用 Browser Use Cloud API v2

推荐环境变量：
- `BROWSER_USE_API_KEY`
- `BROWSER_USE_PROFILE_ID`

---

## 3) Skill 核心流程（必须按阶段）

### 阶段 0：解析综合文案（结构化）
从完整招聘文档抽取：
- `project_status`
- `company_context`
- `job_detail`
- `must_have`
- `nice_to_have`
- `red_flags`
- `candidate_profile`
- `search_keywords`（company/skill/exclude）

> 若已提供 `search_strategies`，可跳过阶段 0 和 0.5。

### 阶段 0.5：生成 search_strategies
基于解析结果生成可在 LinkedIn RPS 复现的策略：
- 关键词组合
- 排除词
- 筛选条件（地区/职级/经验/行业等）

### 阶段 1：执行搜索（**原子化强制**）
每次 `run_task` 只能执行**一个 strategy_id**，并返回该策略的一批候选人。

**必须明确 filter 字段**，不可模糊表述。

### 阶段 2：逐个候选人判断
按 company + job + must-have 判断：
- `passed_gate`
- `reject_must_have_mismatch`
- `reject_not_suitable`

### 阶段 2.5：超过 5 人时排序
合适候选人 >5 时，结合完整上下文排序，只保留前 5 名。

### 阶段 3：输出
- 每位处理过候选人的结构化记录
- 本轮最终推荐（<=5 人）总结文本
- 优先输出 `profile_url`；缺失需给 `url_missing_reason` + 后续补采动作

### 阶段 4：多轮优化
收到顾问反馈后，优化关键词与筛选条件，进入新一轮。

---

## 4) 阶段 1 原子化模板（建议）
```text
strategy_id: {strategy_id}
keywords: {keywords}
location: {location}
current_company_include: {current_company_include}
current_company_exclude: {current_company_exclude}
title_include: {title_include}
title_exclude: {title_exclude}
years_of_experience_min: {years_of_experience_min}
years_of_experience_max: {years_of_experience_max}
industry: {industry}
skills_must: {skills_must}
skills_optional: {skills_optional}
exclude_keywords: {exclude_keywords}
result_page_limit: {result_page_limit}

约束:
- 单次 run_task 仅执行当前 strategy_id
- 不得执行其他 strategy_id
- 返回当前 strategy 下的一批候选人信息
```

---

## 5) 候选人结构化输出建议
```json
{
  "candidate_name": "",
  "profile_url": "",
  "current_company": "",
  "current_title": "",
  "experience_summary": "",
  "education_summary": "",
  "gate_decision": "passed_gate | reject_must_have_mismatch | reject_not_suitable",
  "must_have_mismatch": "",
  "must_have_evidence": "",
  "follow_up_suggestion": "",
  "url_missing_reason": "",
  "profile_identifier": "",
  "url_follow_up_action": "",
  "rank_in_round": ""
}
```

---

## 6) Browser Use Cloud API 最小调用链
1. `POST /api/v2/sessions`（绑定 profile）
2. `POST /api/v2/tasks`（执行单轮或单策略任务）
3. `GET /api/v2/tasks/{task_id}`（轮询结果）
4. `PATCH /api/v2/sessions/{session_id}` action=`stop`（节约成本）

---

## 7) 给同事机器人落地建议
- 把此文档作为系统/技能参考文档导入
- 固定执行顺序：0 → 0.5 → 1 → 2 → 2.5 → 3 → 4
- 对阶段 1 强制加"单 strategy 原子化"校验
- 输出环节强制校验：每轮最多推荐 5 人

---

## 8) 当前你这边可复用资产
- Browser Use Cloud 技能包：`browser-use-cloud.skill`
- 该文档：`LinkedIn_RPS_找人Skill_操作文档.md`

如需，我可以下一步再给你打一个单独的 `.skill` 包（名字：`linkedin-search-skill`），给同事直接导入。
