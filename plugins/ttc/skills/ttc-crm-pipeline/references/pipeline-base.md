---
name: pipeline-base
description: ttc-crm Pipeline 基础类型定义。包含枚举定义（阶段类型/状态/活跃状态/通知类型等）、以及 Pipeline 数据/项目数据/任务数据等核心数据结构。被所有 Pipeline 服务共享使用。
---

# Pipeline Base 基础类型

ttc-crm Pipeline 基础类型定义，包含枚举定义和核心数据结构。

## 概览

| 类型 | 说明 |
|------|------|
| 业务枚举 | StepType, PipelineStatus, ActiveState, NotificationType, TimeUnit 等 |
| 数据结构 | PipelineData, ProjectData, TaskInfo, StepStatus, ActionStatus, Notification 等 |

---

## 枚举定义

### Pipeline 阶段类型 (StepType)

| 值 | 常量名 | 含义 |
|----|--------|------|
| Recommendation | RECOMMENDATION | 推荐阶段 |
| Interview | INTERVIEW | 面试阶段 |
| Offer | OFFER | Offer 阶段 |
| Onboarding | ONBOARDING | 入职阶段 |

### Pipeline 状态 (Status)

| 值 | 常量名 | 含义 |
|----|--------|------|
| Recommendable | RECOMMENDABLE | 可推荐 |
| NotRecommendable | NOT_RECOMMENDABLE | 不可推荐 |

### Pipeline 活跃状态 (ActiveState)

| 值 | 常量名 | 含义 |
|----|--------|------|
| Progressing | PROGRESSING | 进行中 |
| Ended | ENDED | 已终止 |
| Finished | FINISHED | 已完成 |

### 通知类型 (NotificationType)

| 值 | 常量名 | 含义 |
|----|--------|------|
| before | BEFORE | 提前通知 |
| time | TIME | 定时通知 |

### 时间单位 (TimeUnit)

| 值 | 常量名 | 含义 |
|----|--------|------|
| day | DAY | 天 |
| hour | HOUR | 小时 |

### Pipeline 终止操作 (TerminateAction)

| 值 | 常量名 | 含义 |
|----|--------|------|
| terminate | TERMINATE | 终止 |
| cancel | CANCEL | 取消终止 |

---

## 数据结构

### Filter 过滤器

| 字段 | 类型 | 说明 |
|------|------|------|
| key | string | 过滤字段 |
| op | string | 操作符 |
| value | string | 过滤值（interface{} 类型） |

### Sort 排序

| 字段 | 类型 | 说明 |
|------|------|------|
| key | string | 排序字段（本期只支持 latest_work_time） |
| sort | string | 正倒序（本期固定倒序） |

### ActionStatus Action 状态

| 字段 | 类型 | 说明 |
|------|------|------|
| key | string | Action 键 |
| status | string | 状态 |
| id | string | Action ID |

### StepStatusExtraInfo 阶段状态额外信息

| 字段 | 类型 | 说明 |
|------|------|------|
| interview_start_time | i64 | 面试开始时间（可选） |
| interview_end_time | i64 | 面试结束时间（可选） |

### StepStatus 阶段状态

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 阶段 ID |
| type | string | 阶段类型（Recommendation/Interview/Offer/Onboarding） |
| parent_step_id | string | 父阶段 ID |
| status | string | 状态 |
| actions | list&lt;ActionStatus&gt; | Action 状态列表 |
| extra_info | StepStatusExtraInfo | 额外信息 |

### PipelineData Pipeline 数据

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | Pipeline ID |
| talent_id | string | 人才 ID |
| talent_name | string | 人才姓名 |
| talent_company | string | 人才公司 |
| talent_school | string | 人才学校 |
| latest_step | string | 最新阶段（Recommendation/Interview/Offer/Onboarding） |
| status | string | 状态（Recommendable/NotRecommendable 等） |
| submitter | string | 提交人 |
| created_at | i64 | 创建时间（可选） |
| with_permission | bool | 是否有权限 |
| step_status | list&lt;StepStatus&gt; | 阶段状态列表 |
| active_state | string | 活跃状态（Progressing/Ended/Finished） |
| client_id | string | 客户 ID |
| client_name | string | 客户名称 |
| project_id | string | 项目 ID |
| project_name | string | 项目名称 |
| project_updated_at | i64 | 项目更新时间 |
| project_created_at | i64 | 项目创建时间 |
| project_pm_ids | list&lt;string&gt; | 项目 PM ID 列表 |
| updated_at | i64 | 更新时间（可选） |
| permission_level | string | 权限级别 |
| source | string | 来源 |
| source_remark | string | 来源备注 |
| latest_action_id | string | 最新 Action ID |
| latest_step_id | string | 最新阶段 ID |
| job_secrecy | string | 岗位保密（可选） |
| job_has_permission | bool | 岗位是否有权限（可选） |
| talent_attachment_id | string | 人才附件 ID |
| is_manually_terminated | bool | 是否被手动终止 |
| job_name | string | 岗位名称 |
| owner_ids | list&lt;string&gt; | Owner ID 列表 |
| talent_degree | string | 人才学历 |
| talent_title | string | 人才职位 |
| recommend_user | string | 推荐人 |
| recommend_time | string | 推荐时间 |
| recommend_text | string | 推荐语 |
| recommend_status | string | 推荐状态 |
| is_non_headhunter | bool | 是否非猎头（可选） |

### PipelineLog Pipeline 操作日志

| 字段 | 类型 | 说明 |
|------|------|------|
| operator | string | 操作人用户 ID |
| operating_time | i64 | 操作时间（13位时间戳） |
| type | string | 行为类型 |
| step_name | string | 环节名 |
| action_key | string | Action 键 |
| old_data | string | 旧数据（interface{} 类型） |
| new_data | string | 新数据（interface{} 类型） |
| note_id | string | 备注 ID |

### ProjectInfo 项目信息

| 字段 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目 ID |
| project_name | string | 项目名称 |
| client_id | string | 客户 ID |
| client_name | string | 客户名称 |
| description | string | 描述 |
| is_public | bool | 是否公开 |
| with_permission | bool | 是否有权限 |
| pms | list&lt;string&gt; | PM 列表 |
| participants | list&lt;string&gt; | 参与者列表 |
| permission_level | string | 权限级别 |
| client_manager | list&lt;string&gt; | 客户经理列表 |
| job_referrer | list&lt;string&gt; | 岗位推荐人列表 |
| is_non_headhunter | bool | 是否非猎头（可选） |

### ProjectData 项目数据

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 项目 ID |
| name | string | 项目名称 |
| client_id | string | 客户 ID |
| client_name | string | 客户名称 |
| pm | string | PM |
| with_permission | bool | 是否有权限 |
| pipeline_step_count | map&lt;string, i64&gt; | 各阶段 Pipeline 数量 |
| total_pipeline | i64 | 总 Pipeline 数 |
| updated_at | string | 更新时间 |
| created_at | string | 创建时间 |
| permission_level | string | 权限级别 |
| cooperation | string | 合作方式 |
| active_job_count | i64 | 活跃岗位数 |
| job_tags | list&lt;string&gt; | 岗位标签 |
| job_description | string | 岗位描述 |
| headcount | i64 | HC 数 |
| expect_amount | i64 | 预期金额 |
| company_manager | string | 公司经理 |
| job_participants | list&lt;string&gt; | 岗位参与者 |
| is_favorited | bool | 是否收藏（可选） |
| is_lovtalent | bool | 是否 Lovtalent（可选） |
| is_non_headhunter | bool | 是否非猎头（可选） |

### ClientInfo 客户信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 客户 ID |
| name | string | 客户名称 |
| manager | string | 经理 |
| follow_up_time | i64 | 跟进时间 |
| project_count | i64 | 项目数 |
| rate | double | 费率 |

### UserInfo 用户信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 用户 ID |
| name | string | 用户名称 |
| avatar | string | 头像 |
| lark_union_id | string | 飞书 UnionID |

### TaskTypeInfo 任务类型信息

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 任务类型 |
| count | i32 | 数量 |

### TaskExtraInfo 任务额外信息

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline_id | string | Pipeline ID |
| step_id | string | 阶段 ID |
| action_id | string | Action ID |
| job_id | string | 岗位 ID |
| person_leads_id | string | 人才 ID |
| attachment_id | string | 附件 ID |

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

### ResumeStatus 简历状态

| 字段 | 类型 | 说明 |
|------|------|------|
| job_id | string | 任务 ID |
| resume_name | string | 简历名称 |
| status | string | 状态 |
| message | string | 消息 |
| pipeline_id | string | Pipeline ID |
| status_update_at | i64 | 状态更新时间 |
| project_id | string | 项目 ID |
| dst_list | string | 目标列表 |
| error_code | i64 | 错误码 |
| person_leads_id | string | 人才 ID |
| permission_level | string | 权限级别 |

### FileInfo 文件信息

| 字段 | 类型 | 说明 |
|------|------|------|
| file_id | string | 文件 ID |
| file_url | string | 文件 URL |
| file_name | string | 文件名 |
| preview_url | string | 预览 URL |

---

## 通知相关结构

### Notification 通知

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 通知 ID |
| type | string | 类型（before/time） |
| duration | double | 时长 |
| timeUnit | string | 时间单位（day/hour） |
| date | i64 | 日期 |

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

## 账单相关结构

### ShareMember 分成成员

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| share_ratio | double | 分成比例 |

### Billing 账单

| 字段 | 类型 | 说明 |
|------|------|------|
| total_amount | double | 总金额 |
| amount_reason | string | 金额原因 |
| installment_amount | list&lt;double&gt; | 分期金额 |
| share_reason | string | 分成原因 |
| members | map&lt;string, list&lt;ShareMember&gt;&gt; | 分成成员（key: client_manager/job_referrer/pm/pipeline_participants） |

---

## 面试相关结构

### TimeSlot 时间段

| 字段 | 类型 | 说明 |
|------|------|------|
| start_time | i64 | 开始时间（13位时间戳） |
| end_time | i64 | 结束时间（13位时间戳） |

---

## AI 匹配相关结构

### MustStatistics 必须条件统计

| 字段 | 类型 | 说明 |
|------|------|------|
| total | i32 | 总数 |
| match | i32 | 匹配数 |
| not_sure | i32 | 不确定数 |
| not_match | i32 | 不匹配数 |

### EvaluateResult 评估结果

| 字段 | 类型 | 说明 |
|------|------|------|
| overall_match | bool | 整体是否匹配 |
| job_unique_id | string | 岗位唯一 ID |
| person_leads_id | string | 人才 ID |
| overall_match_rate | double | 整体匹配率 |
| must_match_rate | double | 必须条件匹配率 |
| must_statistics | MustStatistics | 必须条件统计 |

### MatchScoreInfo 匹配分数信息

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline_id | string | Pipeline ID |
| match_score | i64 | 匹配分数 |
| match_reason | string | 匹配原因 |

### PipelineRelatedData Pipeline 关联数据

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline_id | string | Pipeline ID |
| person_leads_id | string | 人才 ID |
| job_id | string | 岗位 ID |
| company_id | string | 公司 ID |
| submitter | string | 提交人 |
| permission_level | string | 权限级别 |
| submit_time | i64 | 提交时间（可选） |

---

## 使用说明

此文件定义了 ttc-crm Pipeline 服务的基础类型，被以下服务共享：

- **pipeline-service**: Pipeline 核心服务
- **pipeline-project**: 项目服务
- **pipeline-task**: 任务服务
- **pipeline-notification**: 通知服务

在调用 API 时，请参考此文档中的枚举值和数据结构定义。
