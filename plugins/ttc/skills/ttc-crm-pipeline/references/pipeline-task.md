---
name: pipeline-task
description: ttc-crm Pipeline 任务服务 API。包含任务列表、任务类型、任务状态更新、任务通知等接口。
---

# Task Service 任务服务

任务服务 API，用于管理招聘流程中的任务。

---

## API 列表

### GetCurrentUserTaskTypes 获取当前用户任务类型

获取当前用户的任务类型及数量统计。

**请求**

```
POST /pipeline_service/task_service/current_user/task/types
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| filter | list&lt;Filter&gt; | 否 | 过滤条件 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_types | list&lt;TaskTypeInfo&gt; | 任务类型信息列表 |

---

### GetCurrentUserTaskList 获取当前用户任务列表

获取当前用户的任务列表。

**请求**

```
POST /pipeline_service/task_service/current_user/task/list
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| limit | i32 | 是 | 每页数量 |
| offset | i32 | 是 | 偏移量 |
| filter | list&lt;Filter&gt; | 否 | 过滤条件 |
| sort | list&lt;Sort&gt; | 否 | 排序条件 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| tasks | list&lt;TaskInfo&gt; | 任务信息列表 |

---

### GetCurrentUserTaskListByJob 按岗位获取任务列表

按岗位分组获取当前用户的任务列表。

**请求**

```
POST /pipeline_service/task_service/current_user/task/list_by_job
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| limit | i32 | 是 | 每页数量 |
| offset | i32 | 是 | 偏移量 |
| task_steps | list&lt;string&gt; | 否 | 任务阶段筛选 |
| task_statuses | list&lt;string&gt; | 否 | 任务状态筛选 |
| created_within_days | i32 | 否 | 筛选创建时间为x天内的任务，0表示不筛选 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| total | i64 | 总数 |
| job_task_groups | list&lt;JobTaskGroup&gt; | 岗位任务组列表 |

---

### GetCurrentUserInProgressTasks 获取进行中任务

获取当前用户进行中的任务统计。

**请求**

```
POST /pipeline_service/task_service/current_user/task/in_progress
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| created_within_days | i32 | 否 | 筛选创建时间为x天内的任务，0表示不筛选 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| total | i64 | 总任务数 |
| task_steps | map&lt;string, i32&gt; | 各阶段任务数量（key: step_name, value: count） |

---

### UpdateTaskStatus 更新任务状态

更新任务的状态。

**请求**

```
POST /pipeline_service/task_service/task/update
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 任务 ID |
| status | string | 是 | 新状态 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| message | string | 消息 |

---

### GetTaskTypes 获取任务类型

获取任务类型列表（非当前用户）。

**请求**

```
POST /pipeline_service/task_service/task/types
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| filter | list&lt;Filter&gt; | 否 | 过滤条件 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_types | list&lt;TaskTypeInfo&gt; | 任务类型信息列表 |

---

### GetTaskList 获取任务列表

获取任务列表（非当前用户）。

**请求**

```
POST /pipeline_service/task_service/task/list
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| limit | i32 | 是 | 每页数量 |
| offset | i32 | 是 | 偏移量 |
| filter | list&lt;Filter&gt; | 否 | 过滤条件 |
| sort | list&lt;Sort&gt; | 否 | 排序条件 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| tasks | list&lt;TaskInfo&gt; | 任务信息列表 |

---

### SendTaskNotifications 发送任务通知

向指定用户发送任务通知。

**请求**

```
POST /pipeline_service/task_service/send_notifications
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_ids | list&lt;string&gt; | 是 | 用户 ID 列表 |

**响应**

（响应为空结构）

---

### BrushTaskData 刷新任务数据

刷新任务数据（用于数据修复）。

**请求**

```
POST /pipeline_service/task_service/brush_task_data
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id_list | list&lt;string&gt; | 否 | 指定 ID 列表，如果为空则处理所有数据 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| canceled_task_count | i32 | 取消的任务数量 |
| updated_task_count | i32 | 更新的任务数量 |
| message | string | 执行结果消息 |

---

## 数据结构参考

### TaskTypeInfo 任务类型信息

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 任务类型 |
| count | i32 | 数量 |

### TaskInfo 任务信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 任务 ID |
| type | string | 任务类型 |
| status_updated_at | i64 | 状态更新时间 |
| extra_info | map&lt;string, string&gt; | 额外信息 |
| work_page_url | string | 工作页面 URL |
| status | string | 状态 |
| owners | list&lt;string&gt; | Owner 列表 |

### TaskExtraInfo 任务额外信息

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline_id | string | Pipeline ID |
| step_id | string | 阶段 ID |
| action_id | string | Action ID |
| job_id | string | 岗位 ID |
| person_leads_id | string | 人才 ID |
| attachment_id | string | 附件 ID |

### TaskSummary 任务摘要

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 任务 ID |
| talent_name | string | 人才姓名 |
| talent_company | string | 人才公司 |
| talent_title | string | 人才职位 |
| status_updated_at | i64 | 状态更新时间 |
| created_at | i64 | 创建时间 |
| pipeline_status | string | Pipeline 状态 |
| url | string | URL |
| button_text | string | 按钮文本 |
| pipeline_id | string | Pipeline ID |
| type | string | 类型 |
| pipeline_source | string | Pipeline 来源 |
| pipeline_source_remark | string | Pipeline 来源备注 |

### JobTaskGroup 岗位任务组

| 字段 | 类型 | 说明 |
|------|------|------|
| job_id | string | 岗位 ID |
| job_name | string | 岗位名称 |
| company_name | string | 公司名称 |
| tasks | list&lt;TaskSummary&gt; | 任务摘要列表 |
| latest_task_created_at | i64 | 最新任务创建时间 |
