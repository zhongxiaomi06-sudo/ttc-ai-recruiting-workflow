---
name: jobwater
description: 调用 jobwater Agent 服务进行职位数据查询和市场分析。支持结构化职位数据查询（describe_job_table、query_jobs）、子 Agent 分析（ask_market_analyst、ask_opportunity_advisor、ask_with_skill）。用于获取职位表结构、筛选查询职位、市场行情分析、机会评估建议等场景。
---

# Jobwater 职位数据与市场分析 Skill

> 本 skill 提供 jobwater Agent 服务的完整调用指南
> 基础地址：`https://job-water.ttcadvisory.com`

---

## 一、前置条件

### 1.1 基础地址
```
https://job-water.ttcadvisory.com
```

### 1.2 鉴权说明
- `/api/invoke` 与 `/mcp` **需要 `x-api-key`**
- `/v1/*` 需要 `x-api-key`
- `/api/chat/stream` 可不带 `x-api-key`（默认落到 public principal），带上可做会话隔离

### 1.3 API Key
```
X_API_KEY=jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a
```

**使用方式**: 在请求头中添加 `x-api-key`

---

## 二、工具发现

**Endpoint**: `GET /api/invoke/tools`

**curl 示例**:
```bash
curl -s 'https://job-water.ttcadvisory.com/api/invoke/tools' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a'
```

**返回示例**:
```json
{
  "ok": true,
  "tools": [
    {
      "name": "describe_job_table",
      "description": "获取表结构、样本值、记录数",
      "parameters": { ... }
    },
    {
      "name": "query_jobs",
      "description": "按列筛选、全文检索、排序、分组统计、计数",
      "parameters": { ... }
    },
    {
      "name": "ask_market_analyst",
      "description": "市场行情分析",
      "parameters": { ... }
    },
    {
      "name": "ask_opportunity_advisor",
      "description": "机会评估建议",
      "parameters": { ... }
    },
    {
      "name": "ask_with_skill",
      "description": "指定 Skill 进行分析输出（可选调用工具）",
      "parameters": { ... }
    }
  ]
}
```

---

## 三、核心工具调用

### 3.1 通用调用方式

**Endpoint**: `POST /api/invoke`

**请求格式**:
```json
{
  "tool": "<tool_name>",
  "args": { ... }
}
```

**响应格式**:
- 成功：`{ ok: true, tool, result }`
- 失败：`{ ok: false, tool, error }`

---

### 3.2 describe_job_table - 获取表结构

**用途**: 获取职位表的表结构、样本值、记录数

**curl 示例**:
```bash
curl -sX POST 'https://job-water.ttcadvisory.com/api/invoke' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a' \
  -d '{"tool":"describe_job_table","args":{}}'
```

---

### 3.3 query_jobs - 查询职位

**用途**: 按列筛选、全文检索、排序、分组统计、计数

**参数说明**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `column_filters` | string/array | 列筛选条件，JSON 格式 |
| `group_by` | string | 分组字段 |
| `limit` | int | 返回数量（最大 50） |
| `sort_by` | string | 排序字段 |
| `sort_order` | string | 排序方向：asc/desc |

**column_filters 格式**:
```json
[
  {"column": "base地", "op": "contains", "value": "北京"},
  {"column": "客户名称", "op": "eq", "value": "某公司名称"}
]
```

**支持的 op**:
- `contains` - 包含
- `eq` - 等于
- `neq` - 不等于
- `gt` / `gte` - 大于 / 大于等于
- `lt` / `lte` - 小于 / 小于等于
- `startswith` - 以...开头
- `endswith` - 以...结尾

**curl 示例 1 - 列筛选**:
```bash
curl -sX POST 'https://job-water.ttcadvisory.com/api/invoke' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a' \
  -d '{
    "tool": "query_jobs",
    "args": {
      "column_filters": "[{\"column\":\"base地\",\"op\":\"contains\",\"value\":\"北京\"}]",
      "limit": 20
    }
  }'
```

**curl 示例 2 - 分组统计**:
```bash
curl -sX POST 'https://job-water.ttcadvisory.com/api/invoke' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a' \
  -d '{
    "tool": "query_jobs",
    "args": {
      "column_filters": "[{\"column\":\"base地\",\"op\":\"contains\",\"value\":\"北京\"}]",
      "group_by": "客户名称",
      "limit": 20
    }
  }'
```

---

### 3.4 ask_market_analyst - 市场行情分析

**用途**: 调用市场分析师子 Agent 进行市场行情分析

**参数说明**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `task` | string | 分析任务描述 |
| `context` | string | 上下文信息（可选） |

**curl 示例**:
```bash
curl -sX POST 'https://job-water.ttcadvisory.com/api/invoke' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a' \
  -d '{
    "tool": "ask_market_analyst",
    "args": {
      "task": "分析北京 AI 岗位市场行情，关注 HC 与机会质量",
      "context": "如果需要先查表结构，请先调用 describe_job_table"
    }
  }'
```

---

### 3.5 ask_opportunity_advisor - 机会评估建议

**用途**: 调用机会顾问子 Agent 进行机会评估

**参数说明**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `task` | string | 评估任务描述 |
| `context` | string | 上下文信息（可选） |

**curl 示例**:
```bash
curl -sX POST 'https://job-water.ttcadvisory.com/api/invoke' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a' \
  -d '{
    "tool": "ask_opportunity_advisor",
    "args": {
      "task": "评估当前 AI 产品经理岗位的机会质量",
      "context": "候选人有 5 年互联网产品经验"
    }
  }'
```

---

### 3.6 ask_with_skill - 指定 Skill 分析

**用途**: 指定 Skill 进行分析输出，可选调用工具

**参数说明**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `skill` | string | Skill 名称 |
| `task` | string | 任务描述 |
| `context` | string | 上下文信息（可选） |

**curl 示例**:
```bash
curl -sX POST 'https://job-water.ttcadvisory.com/api/invoke' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a' \
  -d '{
    "tool": "ask_with_skill",
    "args": {
      "skill": "market-research",
      "task": "分析近期 AI 岗位趋势",
      "context": "关注大模型相关职位"
    }
  }'
```

---

## 四、工作流程

### 4.1 探索数据
1. 调用 `describe_job_table` 获取表结构
2. 了解有哪些字段、样本值、记录数

### 4.2 查询职位
1. 使用 `query_jobs` 进行筛选
2. 可组合 `column_filters`、`group_by`、`limit` 等参数

### 4.3 深度分析
1. 使用 `ask_market_analyst` 进行市场分析
2. 使用 `ask_opportunity_advisor` 进行机会评估
3. 使用 `ask_with_skill` 指定特定分析能力

---

## 五、错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| `ok: false` | 工具执行失败 | 检查参数格式和值 |
| `error` 字段 | 具体错误信息 | 根据 error 内容调整请求 |

---

## 六、完整示例

```bash
# 1. 获取表结构
curl -sX POST 'https://job-water.ttcadvisory.com/api/invoke' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a' \
  -d '{"tool":"describe_job_table","args":{}}'

# 2. 查询北京的 AI 相关职位
curl -sX POST 'https://job-water.ttcadvisory.com/api/invoke' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a' \
  -d '{
    "tool": "query_jobs",
    "args": {
      "column_filters": "[{\"column\":\"base地\",\"op\":\"contains\",\"value\":\"北京\"}]",
      "limit": 20
    }
  }'

# 3. 按客户分组统计
curl -sX POST 'https://job-water.ttcadvisory.com/api/invoke' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a' \
  -d '{
    "tool": "query_jobs",
    "args": {
      "group_by": "客户名称",
      "limit": 50
    }
  }'

# 4. 市场行情分析
curl -sX POST 'https://job-water.ttcadvisory.com/api/invoke' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: jw_test_7f3e9a2b8c1d4e6f0a5b9c2d3e8f1a' \
  -d '{
    "tool": "ask_market_analyst",
    "args": {
      "task": "分析北京 AI 岗位市场行情"
    }
  }'
```

---

## 七、文件位置

本 skill 文件保存在：
```
/root/.openclaw/workspace/skills/jobwater/SKILL.md
```
