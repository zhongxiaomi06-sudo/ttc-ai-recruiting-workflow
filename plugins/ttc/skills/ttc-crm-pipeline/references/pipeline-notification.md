---
name: pipeline-notification
description: ttc-crm Pipeline 通知服务 API。包含通知的创建、更新、删除、查询等接口。
---

# Notification Service 通知服务

通知服务 API，用于管理 Pipeline 相关的通知和提醒。

---

## API 列表

### CreateNotification 创建通知

为 Pipeline 创建通知。

**请求**

```
POST /pipeline_service/pipeline/notification/create
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| action_id | string | 是 | Action ID |
| notification_type | string | 是 | 通知类型 |
| notifications | list&lt;Notification&gt; | 是 | 通知列表 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 创建的通知 ID |

---

### UpdateNotification 更新通知

更新已存在的通知。

**请求**

```
POST /pipeline_service/pipeline/notification/update
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 通知 ID |
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| action_id | string | 是 | Action ID |
| notification_type | string | 是 | 通知类型 |
| notifications | list&lt;Notification&gt; | 是 | 通知列表 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| message | string | 消息 |

---

### DeleteNotification 删除通知

删除通知。

**请求**

```
POST /pipeline_service/pipeline/notification/delete
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 通知 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| message | string | 消息 |

---

### GetNotification 获取通知

获取单个通知详情。

**请求**

```
POST /pipeline_service/pipeline/notification/get
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 通知 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| notification | PipelineNotification | 通知详情 |

---

### ListNotificationsByPipeline 按 Pipeline 查询通知

获取 Pipeline 下的所有通知。

**请求**

```
POST /pipeline_service/pipeline/notification/list_by_pipeline
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| notifications | list&lt;PipelineNotification&gt; | 通知列表 |

---

### ListNotificationsByStep 按阶段查询通知

获取指定阶段下的所有通知。

**请求**

```
POST /pipeline_service/pipeline/notification/list_by_step
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| notifications | list&lt;PipelineNotification&gt; | 通知列表 |

---

### ListNotificationsByAction 按 Action 查询通知

获取指定 Action 下的所有通知。

**请求**

```
POST /pipeline_service/pipeline/notification/list_by_action
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| action_id | string | 是 | Action ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| notifications | list&lt;PipelineNotification&gt; | 通知列表 |

---

## 数据结构参考

### Notification 通知

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 通知 ID |
| type | string | 类型（before/time） |
| duration | double | 时长 |
| timeUnit | string | 时间单位（day/hour） |
| date | i64 | 日期时间戳 |

### PipelineNotification Pipeline 通知

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 通知 ID |
| pipeline_id | string | Pipeline ID |
| step_id | string | 阶段 ID |
| action_id | string | Action ID |
| notification_type | string | 通知类型 |
| notifications | list&lt;Notification&gt; | 通知列表 |
| event_start_time | i64 | 日程开始时间 |
| event_end_time | i64 | 日程结束时间 |
| event_id | string | 日程 ID |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |

---

## 通知类型说明

### NotificationType 通知类型

| 值 | 说明 |
|----|------|
| before | 提前通知 - 在事件发生前提前一段时间发送通知 |
| time | 定时通知 - 在指定时间点发送通知 |

### TimeUnit 时间单位

| 值 | 说明 |
|----|------|
| day | 天 |
| hour | 小时 |

---

## 使用示例

### 创建提前通知

```json
{
  "pipeline_id": "pl_123456",
  "step_id": "step_789",
  "action_id": "action_abc",
  "notification_type": "interview_reminder",
  "notifications": [
    {
      "type": "before",
      "duration": 1,
      "timeUnit": "day"
    },
    {
      "type": "before",
      "duration": 2,
      "timeUnit": "hour"
    }
  ]
}
```

### 创建定时通知

```json
{
  "pipeline_id": "pl_123456",
  "step_id": "step_789",
  "action_id": "action_abc",
  "notification_type": "follow_up",
  "notifications": [
    {
      "type": "time",
      "date": 1704067200000
    }
  ]
}
```

---

## 账单服务 BillingService

### CreateBilling 创建账单

为 Pipeline 创建账单。

**请求**

```
POST /pipeline_service/billing/create
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| billing | Billing | 是 | 账单信息 |

**Billing 结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| total_amount | double | 总金额 |
| amount_reason | string | 金额原因 |
| installment_amount | list&lt;double&gt; | 分期金额列表 |
| share_reason | string | 分成原因 |
| members | map&lt;string, list&lt;ShareMember&gt;&gt; | 分成成员（key: client_manager/job_referrer/pm/pipeline_participants） |

**ShareMember 结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| share_ratio | double | 分成比例 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 账单 ID |

---

### BillingInfo 获取账单信息

获取 Pipeline 的账单信息。

**请求**

```
GET /pipeline_service/billing/info
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID（query 参数） |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| approval_status | string | 审批状态 |
| submitter | string | 提交人 |
| submit_time | i64 | 提交时间 |
| total_amount | double | 总金额 |
| amount_reason | string | 金额原因 |
| installment_amount | list&lt;double&gt; | 分期金额列表 |
| lark_approval_id | string | 飞书审批 ID |
| share_reason | string | 分成原因 |
| members | map&lt;string, list&lt;ShareMember&gt;&gt; | 分成成员 |

---

## 索引服务 IndexService

### BrushIndex 刷新单个索引

刷新指定 Pipeline 的索引。

**请求**

```
GET /pipeline_service/brush-index
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID（query 参数） |

**响应**

（响应为空结构）

---

### BrushAllIndex 刷新所有索引

刷新所有 Pipeline 的索引。

**请求**

```
GET /pipeline_service/brush-all-index
```

（无请求参数）

**响应**

（响应为空结构）

---

### BrushBiData 刷新 BI 数据

刷新指定 Pipeline 的 BI 数据。

**请求**

```
GET /pipeline_service/brush-bi-data
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID（query 参数） |

**响应**

（响应为空结构）

---

### BrushAllBiData 刷新所有 BI 数据

刷新所有 Pipeline 的 BI 数据。

**请求**

```
GET /pipeline_service/brush-all-bi-data
```

（无请求参数）

**响应**

（响应为空结构）

---

### BrushTaskList 刷新任务列表

刷新指定任务列表。

**请求**

```
POST /pipeline_service/brush-task-list
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ids | list&lt;string&gt; | 是 | 任务 ID 列表 |

**响应**

（响应为空结构）
