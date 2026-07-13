---
name: pipeline-project
description: ttc-crm Pipeline 项目服务 API。包含项目列表、项目详情、简历提交、AI 搜索、Benchmark 管理、王牌岗位管理等接口。
---

# Project Service 项目服务

项目服务 API，用于管理招聘项目和相关操作。

---

## API 列表

### ProjectList 项目列表

获取项目列表。

**请求**

```
POST /pipeline_service/project/list
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 否 | 搜索关键词 |
| filter | list&lt;Filter&gt; | 否 | 过滤条件 |
| sort | list&lt;Sort&gt; | 否 | 排序条件 |
| limit | i32 | 是 | 每页数量 |
| offset | i32 | 是 | 偏移量 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| data | list&lt;ProjectData&gt; | 项目数据列表 |
| total | i64 | 总数 |
| user_map | map&lt;string, UserInfo&gt; | 用户信息映射 |

---

### ProjectInfo 项目详情

获取项目详细信息。

**请求**

```
POST /pipeline_service/project/info
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_ids | list&lt;string&gt; | 是 | 项目 ID 列表 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| projects | list&lt;ProjectInfo&gt; | 项目信息列表 |

---

### CreatePipelineByResume 通过简历创建 Pipeline

上传简历并创建 Pipeline。

**请求**

```
POST /pipeline_service/project/resume_submit
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | multipart file | 是 | 简历文件 |
| project_id | string | 是 | 项目 ID |
| dst_list | string | 否 | 目标列表 |
| permission_level | string | 否 | 权限级别 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| job_id | string | 任务 ID |

---

### ProjectResumeStatus 简历状态

获取项目简历处理状态。

**请求**

```
GET /pipeline_service/project/resume_status
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | string | 是 | 项目 ID（query 参数） |
| dst_list | string | 否 | 目标列表（query 参数） |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| status | list&lt;ResumeStatus&gt; | 简历状态列表 |

---

### ProjectResumeStatusByIDs 批量查询简历状态

根据任务 ID 批量查询简历状态。

**请求**

```
POST /pipeline_service/project/resume_status_by_id
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_ids | list&lt;string&gt; | 是 | 任务 ID 列表 |
| dst_list | string | 否 | 目标列表 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| status | list&lt;ResumeStatus&gt; | 简历状态列表 |

---

### ProjectIDsByChatIDs 通过 ChatID 获取项目

根据飞书 ChatID 获取关联的项目 ID。

**请求**

```
POST /pipeline_service/project/project_ids_by_chat_id
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| chat_id | string | 是 | 飞书 Chat ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| project_ids | list&lt;string&gt; | 项目 ID 列表 |

---

### CreateProjectAISearchJob 创建 AI 搜索任务

为项目创建 AI 搜索任务。

**请求**

```
POST /pipeline_service/project/ai_search/create
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | string | 是 | 项目 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| max_wait_time_seconds | i64 | 最大等待时间（秒） |

---

### ProjectAISearchStatus AI 搜索状态

获取项目 AI 搜索状态。

**请求**

```
POST /pipeline_service/project/ai_search/status
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | string | 是 | 项目 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| enable | bool | 是否启用 |
| submit_enabled | bool | 是否可提交 |
| max_wait_time_seconds | i64 | 最大等待时间（秒） |
| remaining_wait_time_seconds | i64 | 剩余等待时间（秒） |
| person_leads_count | i64 | 人才数量 |

---

### StartBenchmark 启动 Benchmark

启动岗位的 Benchmark 匹配。

**请求**

```
POST /pipeline_service/project/benchmark/start
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 岗位 ID |

**响应**

（响应为空结构）

---

### GetBenchmarkLogs 获取 Benchmark 日志

获取岗位的 Benchmark 执行日志。

**请求**

```
POST /pipeline_service/project/benchmark/logs
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 岗位 ID（query 参数） |

**响应**

（响应为空结构）

---

### ClearProjectBenchmarkTriedIDs 清除 Benchmark 已尝试ID

清除项目 Benchmark 已尝试的人才 ID。

**请求**

```
POST /pipeline_service/project/benchmark/clear_tried_ids
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 岗位 ID（query 参数） |

**响应**

（响应为空结构）

---

### GetAceJobPersonLeadsIDs 获取王牌岗位人才ID

获取王牌岗位相关的人才 ID。

**请求**

```
GET /pipeline_service/project/ace_job/person_leads_ids
```

（无请求参数）

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| unique_person_leads_ids | list&lt;string&gt; | 唯一人才 ID 列表 |
| person_leads_to_pipeline | map&lt;string, string&gt; | 人才到 Pipeline 的映射 |
| person_leads_to_job_ids | map&lt;string, list&lt;string&gt;&gt; | 人才到岗位的映射 |

---

### StartAceJobByProjectID 按项目启动王牌岗位

根据项目 ID 启动王牌岗位检查。

**请求**

```
POST /pipeline_service/project/ace_job/start_by_project_id
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_unique_id | string | 是 | 岗位唯一 ID |

**响应**

（响应为空结构）

---

### StartAceJobMatchByJobID 按岗位启动王牌岗位匹配

根据岗位 ID 启动王牌岗位匹配。

**请求**

```
POST /pipeline_service/project/ace_job/start_job_match
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 岗位 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| message | string | 消息 |

---

## 客户服务 ClientService

### ClientList 客户列表

获取客户列表。

**请求**

```
POST /pipeline_service/client/list
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 否 | 搜索关键词 |
| filter | list&lt;Filter&gt; | 否 | 过滤条件 |
| sort | list&lt;Sort&gt; | 否 | 排序条件 |
| limit | i32 | 是 | 每页数量 |
| offset | i32 | 是 | 偏移量 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| total | i64 | 总数 |
| data | list&lt;ClientInfo&gt; | 客户信息列表 |
| user_map | map&lt;string, UserInfo&gt; | 用户信息映射 |

---

## 用户服务 UserService

### UserInfo 用户信息

获取用户信息。

**请求**

```
GET /pipeline_service/user/info
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID（query 参数） |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| user_info | UserInfo | 用户信息 |

---

### UserList 用户列表

获取用户列表。

**请求**

```
GET /pipeline_service/user/list
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 否 | 搜索关键词 |
| limit | i32 | 是 | 每页数量 |
| offset | i32 | 是 | 偏移量 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| user_list | list&lt;UserInfo&gt; | 用户信息列表 |

---

## 文件服务 FileService

### FileInfo 文件信息

获取文件信息。

**请求**

```
GET /pipeline_service/file/info
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_id | string | 是 | 文件 ID（query 参数） |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| file | FileInfo | 文件信息 |

---

### FileUpload 文件上传

上传文件。

**请求**

```
POST /pipeline_service/file/upload
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | binary | 是 | 文件（form 参数） |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| file | FileInfo | 上传的文件信息 |

---

## 同步服务 SyncService

### SyncAceJobMatchBitable 同步王牌岗位匹配到多维表格

将王牌岗位匹配数据同步到多维表格。

**请求**

```
POST /pipeline_service/sync/ace_job_match_bitable
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_ids | list&lt;string&gt; | 是 | Pipeline ID 列表 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否整体成功 |
| success_count | i32 | 成功同步数量 |
| fail_count | i32 | 失败数量 |
| failed_ids | list&lt;string&gt; | 失败的 Pipeline ID 列表 |
