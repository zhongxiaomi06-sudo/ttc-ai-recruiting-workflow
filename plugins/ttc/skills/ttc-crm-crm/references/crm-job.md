---
name: crm-job
description: ttc-crm CRM 职位管理服务。包含职位创建/更新/搜索、王牌职位、AI评估、批量导入、C端职位、职位代理等功能。
---

# CRM Job 职位管理服务

ttc-crm CRM 职位管理服务，提供职位相关的完整 API。

## 概览

| 功能模块 | 说明 |
|----------|------|
| 职位管理 | 创建、更新、搜索、批量获取职位 |
| 王牌职位 | 申请王牌职位、匹配、评估标准生成 |
| 向量搜索 | 基于向量的职位查询和匹配 |
| C端职位 | forC 预览、分享海报生成 |
| 职位代理 | AI会话、评测、消息管理 |
| 批量导入 | 从飞书多维表格批量导入职位 |

---

## 职位管理接口

### 创建职位

创建新的职位信息。

**接口路径：** `POST /crm/v1/job`

**请求体 (CreateJobRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job | Job | 是 | 职位信息 |

**Job 必填字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 职位名称 |
| cities | list&lt;string&gt; | 城市列表 |
| head_count | i64 | 招聘人数 |
| analytics | string | 职位描述（人选画像） |
| provider | User | 提供者 |
| managers | list&lt;User&gt; | 管理者 |
| company_unique_id | string | 公司ID |
| status | JobStatus | 职位状态 |

**响应数据 (CreateJobData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| job | Job | 创建的职位信息 |

**请求示例：**

```bash
curl -X POST 'https://api.ttcadvisory.com/api/crm/v1/job' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "job": {
      "name": "高级Java工程师",
      "cities": ["北京", "上海"],
      "head_count": 3,
      "analytics": "5年以上Java开发经验，熟悉Spring框架",
      "company_unique_id": "CIZEBHS",
      "status": 1,
      "provider": {"unique_id": "ou_xxxxxxxxxxxxxxxx"},
      "managers": [{"unique_id": "ou_xxxxxxxxxxxxxxxx"}]
    }
  }'
```

> **ID 格式说明：**
> - `company_unique_id`: 客户ID，格式如 `CIZEBHS`（7位大写字母）
> - `provider.unique_id` / `managers[].unique_id`: 飞书用户ID，格式如 `ou_xxxxxxxxxxxxxxxx`

---

### 获取职位详情

根据唯一ID获取职位详细信息。

**接口路径：** `GET /crm/v1/job/:unique_id`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 职位唯一ID |

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| is_c | bool | 否 | 是否是C端请求 |

**响应数据 (GetJobDetailData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| job | Job | 职位详细信息 |

---

### 更新职位信息

更新指定职位的信息。

**接口路径：** `POST /crm/v1/job/:unique_id`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 职位唯一ID |

**请求体 (UpdateJobRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job | Job | 是 | 职位信息（必须包含 unique_id） |

---

### 搜索职位

根据条件搜索职位列表。

**接口路径：** `POST /crm/v1/job/search`

**请求体 (SearchJobRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_unique_id | string | 否 | 公司ID |
| name | string | 否 | 职位名称 |
| cursor | i64 | 否 | 分页游标 |
| size | i64 | 否 | 每页大小 |
| status | JobStatus | 否 | 职位状态 |
| manager_id | string | 否 | 管理者ID |
| participant_id | string | 否 | 参与者ID |
| keyword | string | 否 | 关键字（支持jobId、jobName、companyId、companyName） |
| group_chat_id | string | 否 | 群聊ID |
| cooperation | string | 否 | 合作状态 |
| favorited_by | string | 否 | 收藏人ID |
| industry_tags | list&lt;Tag&gt; | 否 | 行业标签列表 |
| cities | list&lt;string&gt; | 否 | 城市列表 |
| is_lovtalent | bool | 否 | 是否是lovtalent职位 |
| is_non_headhunter | bool | 否 | 是否为非猎头职位 |
| priority | i32 | 否 | 职位优先级（1=王牌职位） |

**响应数据 (SearchJobData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| jobs | list&lt;Job&gt; | 职位列表 |
| has_more | bool | 是否有更多数据 |
| cursor | i64 | 下一页游标 |

**请求示例：**

```bash
# 搜索指定客户的进展中职位
curl -X POST 'https://api.ttcadvisory.com/api/crm/v1/job/search' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "company_unique_id": "CIZEBHS",
    "status": 1,
    "size": 20
  }'

# 搜索王牌职位
curl -X POST 'https://api.ttcadvisory.com/api/crm/v1/job/search' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "priority": 1,
    "status": 1,
    "size": 20
  }'
```

---

### 查询职位（多条件）

根据多维度条件查询职位。

**接口路径：** `POST /crm/v1/job/query`

**请求体 (QueryJobRequest)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| company_names | list&lt;string&gt; | 公司名称列表 |
| company_tags | list&lt;string&gt; | 公司标签列表 |
| job_names | list&lt;string&gt; | 职位名称列表 |
| job_tags | list&lt;string&gt; | 职位标签列表 |
| work_locations | list&lt;string&gt; | 工作地点列表 |
| job_descriptions | list&lt;string&gt; | 职位描述列表 |
| job_requirements | list&lt;string&gt; | JD列表 |

---

### 批量获取职位详情

批量获取多个职位的详细信息。

**接口路径：** `POST /crm/v1/job/batch`

**请求体 (BatchGetJobDetailRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_ids | list&lt;string&gt; | 是 | 职位ID列表 |
| user_unique_id | string | 否 | 用户唯一ID |
| skip_permission | bool | 否 | 是否跳过权限（true可查保密项目） |

**响应数据 (BatchGetJobDetailData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| jobs | list&lt;Job&gt; | 职位列表 |

---

### 轻量级更新职位字段

轻量级更新职位的特定字段。

**接口路径：** `POST /crm/v1/job/patch`

**请求体 (PatchJobRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 职位ID |
| participant_id | string | 否 | 参与者ID |
| analytics | string | 否 | 职位描述 |
| operator | string | 否 | 操作人 |
| source | string | 否 | 操作来源 |
| format_analytics | string | 否 | 王牌岗位格式的人选画像 |

---

### 更新职位状态

更新职位的状态。

**接口路径：** `POST /crm/v1/job/status`

**请求体 (UpdateJobStatusRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_unique_id | string | 是 | 职位唯一ID |
| status | JobStatus | 是 | 新状态 |

---

### 收藏/取消收藏职位

收藏或取消收藏职位。

**接口路径：** `POST /crm/v1/job/favorite`

**请求体 (FavoriteJobRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_unique_ids | list&lt;string&gt; | 是 | 职位ID列表 |
| is_favorite | bool | 是 | true=收藏，false=取消 |

---

### 获取客户职位列表

获取指定客户的所有职位。

**接口路径：** `GET /crm/v1/job/list/:company_unique_id`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_unique_id | string | 是 | 客户ID |

---

### 获取职位画像

获取职位的画像信息。

**接口路径：** `GET /crm/v1/job/profile/:unique_id`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 职位唯一ID |

**响应数据 (GetJobProfileData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| unique_id | string | 职位唯一ID |
| analytics | string | 职位画像 |
| analytics_version_time | i64 | 画像版本时间 |

---

## 王牌职位接口

### 申请成为王牌职位

申请将职位设为王牌职位。

**接口路径：** `POST /crm/v1/job/ace/apply`

**请求体 (ApplyAceJobRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_unique_id | string | 是 | 职位唯一ID |
| operator | string | 是 | 操作人 |

---

### 开始王牌职位匹配

触发王牌职位的人才匹配。

**接口路径：** `POST /crm/v1/job/ace/start_match`

**请求体 (AceJobStartMatchRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_unique_ids | list&lt;string&gt; | 是 | 职位ID列表 |

---

### 更新职位评估标准

更新职位的AI评估标准。

**接口路径：** `POST /crm/v1/job/evaluate_criteria`

**请求体 (UpdateJobEvaluateCriteriaRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_unique_id | string | 是 | 职位唯一ID |
| evaluate_criteria | string | 是 | 评估标准 |
| is_skip_match | bool | 否 | 是否跳过匹配（true=只生成评估标准） |

---

### 批量生成职位评估标准

批量为多个职位生成AI评估标准。

**接口路径：** `POST /crm/v1/job/evaluate_criteria/batch/generate`

**请求体 (BatchGenerateJobEvaluateCriteriaRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_unique_ids | list&lt;string&gt; | 是 | 职位ID列表 |
| is_skip_match | bool | 否 | 是否跳过匹配 |

---

## C端职位接口

### forC 预览生成

生成 C 端职位预览（支持公开/脱敏）。

**接口路径：** `POST /crm/v1/job/forc/preview`

**请求体 (ForcPreviewRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_name | string | 是 | 职位名称 |
| company_name | string | 否 | 公司名称 |
| job_description | string | 否 | 职位描述（JD） |
| job_analytics | string | 否 | 岗位分析（画像/要求） |
| need_blur | bool | 是 | 是否脱敏（true=脱敏, false=公开） |

**响应数据 (ForcPreviewData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| need_blur | bool | 是否脱敏 |
| name_for_c | string | C端职位名称 |
| company_name_for_c | string | C端公司名称 |
| description_for_c | string | C端职位描述 |
| tags_for_c | list&lt;string&gt; | C端标签 |
| qualification_for_c | string | C端职位要求 |

---

### 创建职位分享海报

创建职位分享海报（小程序码）。

**接口路径：** `POST /crm/v1/job/:job_id/poster`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 职位ID |

**响应数据 (CreateJobSharePostData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| wx_mini_program_info | WxMiniProgramInfo | 微信小程序信息 |

---

## 职位代理接口

### 获取会话列表

获取职位相关的 AI 会话列表。

**接口路径：** `GET /crm/v1/job_agent/session_list`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 职位ID |

---

### 获取会话详情

获取 AI 会话中的所有消息。

**接口路径：** `GET /crm/v1/job_agent/session_detail`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话ID |

---

### 会话聊天

与职位 AI 代理进行聊天。

**接口路径：** `POST /crm/v1/job_agent/session_chat`

**请求体 (JobAgentSessionChatRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 职位ID |
| message | string | 是 | 用户消息 |
| session_id | string | 否 | 会话ID（可选，续聊时填写） |
| agent_type | string | 否 | 代理类型 |

---

### 会话聊天（SSE）

与职位 AI 代理进行流式聊天。

**接口路径：** `POST /crm/v1/job_agent/session_chat_sse`

参数同上，返回 Server-Sent Events 流。

---

### 职位评测

进行职位匹配评测。

**接口路径：** `POST /crm/v1/job_agent/evaluation`

**请求体 (JobEvaluationRequest)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| rocket_messages | string | 火箭消息 |
| agent_name | string | 代理名称 |

**响应数据 (JobEvaluationData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| matchSummary | string | 匹配摘要 |
| jobs | list&lt;JobEvaluation&gt; | 匹配职位列表 |
| trace_id | string | 追踪ID |
| tool_calls | list&lt;JobEvaluationToolCall&gt; | 工具调用记录 |
| jobs_by_db | list&lt;JobEvaluation&gt; | 数据库职位列表 |

---

## 批量导入接口

### 创建批量导入表格

创建用于批量导入岗位的飞书多维表格。

**接口路径：** `POST /crm/v1/feishu/batch_job_import_table`

**请求体 (CreateBatchJobImportTableRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_unique_id | string | 是 | 客户ID |

**响应数据 (CreateBatchJobImportTableData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| app_token | string | 多维表格应用ID |
| table_id | string | 表格ID |
| view_id | string | 视图ID |
| app_name | string | 表格名称 |
| table_url | string | 表格访问链接 |

---

### 从表格批量导入岗位

从飞书多维表格批量导入岗位。

**接口路径：** `POST /crm/v1/batch_import_jobs`

**请求体 (BatchImportJobsFromTableRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| table_url | string | 是 | 多维表格URL |

**响应数据 (BatchImportJobsFromTableData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| total_count | i32 | 总记录数 |
| success_count | i32 | 成功数量 |
| failed_count | i32 | 失败数量 |
| skipped_count | i32 | 跳过数量 |
| filtered_count | i32 | 筛选过滤数量 |
| results | list&lt;BatchImportJobResult&gt; | 详细结果列表 |
| summary | string | 结果摘要 |

---

## 使用说明

### 创建职位流程

1. 确保客户已存在（通过 `GetCompanyDetail` 验证）
2. 调用 `CreateJob` 创建职位，填写必填字段
3. 职位创建后可设置为王牌职位或生成 C 端展示信息

### 王牌职位流程

1. 调用 `ApplyAceJob` 申请成为王牌职位
2. 调用 `UpdateJobEvaluateCriteria` 设置评估标准
3. 调用 `AceJobStartMatch` 开始人才匹配

### 职位状态说明

| 状态 | 值 | 说明 |
|------|-----|------|
| 进展中 | 1 | 职位正在招聘中 |
| 暂停 | 5 | 职位暂时停止招聘 |
| 成功 | 10 | 职位招聘成功 |
| 取消 | 20 | 职位已取消 |
