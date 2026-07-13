---
name: pipeline-service
description: ttc-crm Pipeline 核心服务 API。包含 Pipeline 创建、更新、列表、阶段管理、备注管理、状态更新、面试管理等接口。
---

# Pipeline Service Pipeline 核心服务

Pipeline 核心服务 API，用于管理招聘流程的完整生命周期。

---

## API 列表

### PipelineCreate 创建 Pipeline

创建新的 Pipeline。

**请求**

```
POST /pipeline_service/pipeline/create
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_id | string | 是 | 项目 ID |
| talent_store_id | string | 是 | 人才库 ID |
| talent_name | string | 是 | 人才姓名 |
| talent_title | string | 否 | 人才职位 |
| talent_phone | list&lt;string&gt; | 否 | 人才电话列表 |
| attachment_id | string | 否 | 附件 ID |
| talent_company | string | 否 | 人才公司 |
| talent_school | string | 否 | 人才学校 |
| talent_degree | string | 否 | 人才学历 |
| lark_message_id | string | 否 | 飞书消息 ID |
| bot_name | string | 否 | 机器人名称 |
| recommendation_join_project_action_info | map&lt;string, string&gt; | 否 | 推荐入项 Action 信息 |
| lovtalent_pipeline_id | string | 否 | Lovtalent Pipeline ID（可选） |
| created_at | string | 否 | 创建时间（可选） |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline_id | string | 创建的 Pipeline ID |

---

### CreatePipelineByPersonLeadsID 根据人才ID创建 Pipeline

根据 PersonLeadsID 创建 Pipeline。

**请求**

```
POST /pipeline_service/pipeline/create_by_person_leads_id
```

（请求参数通过其他方式传递）

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline_id | string | 创建的 Pipeline ID |

---

### PipelineCreateByBenchmark 根据 Benchmark 创建 Pipeline

根据 Benchmark 创建 Pipeline。

**请求**

```
POST /pipeline_service/pipeline/create_by_benchmark
```

（请求参数同 PipelineCreate）

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline_id | string | 创建的 Pipeline ID |

---

### PipelineList 获取 Pipeline 列表

获取 Pipeline 列表。

**请求**

```
POST /pipeline_service/pipeline/list
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
| data | list&lt;PipelineData&gt; | Pipeline 数据列表 |
| total | i64 | 总数 |
| user_map | map&lt;string, UserInfo&gt; | 用户信息映射 |
| permissions | map&lt;string, list&lt;string&gt;&gt; | 权限映射（可选） |

---

### SourcingPipelineList Sourcing Pipeline 列表

获取 Sourcing Pipeline 列表。

**请求**

```
POST /pipeline_service/pipeline/sourcing/list
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 岗位 ID |
| status | string | 否 | 状态 |
| limit | i64 | 是 | 每页数量 |
| offset | i64 | 是 | 偏移量 |
| sort_by | string | 否 | 排序字段 |

**响应**

（响应为空结构）

---

### SourcingPipelineCount Sourcing Pipeline 计数

获取 Sourcing Pipeline 各状态数量。

**请求**

```
POST /pipeline_service/pipeline/sourcing/count
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 岗位 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| status_count | map&lt;string, i64&gt; | 各状态数量 |
| total | i64 | 总数 |
| created_in_30_days | i64 | 30天内创建数 |

---

### PipelineInfo 获取 Pipeline 详情

获取单个 Pipeline 的详细信息。

**请求**

```
POST /pipeline_service/pipeline/info
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline | map&lt;string, string&gt; | Pipeline 数据（bson.D 类型） |
| status | string | 状态 |
| latest_step_id | string | 最新阶段 ID |
| current_user_permission | string | 当前用户权限 |
| active_state | string | 活跃状态（Progressing/Ended/Finished） |

---

### PipelineUpdate 更新 Pipeline

更新 Pipeline 状态和 Action 信息。

**请求**

```
POST /pipeline_service/pipeline/update
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| action_id | string | 是 | Action ID |
| status | string | 是 | 状态 |
| action_info | map&lt;string, string&gt; | 否 | Action 信息 |
| update_action_info | bool | 否 | 是否更新 Action 信息 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| msg | string | 消息 |

---

### PipelineAddStep 添加阶段

为 Pipeline 添加新阶段。

**请求**

```
POST /pipeline_service/pipeline/add-step
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| pre_step_id | string | 否 | 前置阶段 ID |
| parent_step_id | string | 否 | 父阶段 ID |
| type | string | 是 | 阶段类型 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| step_id | string | 新阶段 ID |

---

### PipelineDeleteStep 删除阶段

删除 Pipeline 的阶段。

**请求**

```
POST /pipeline_service/pipeline/delete-step
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |

---

### PipelineLogs 获取操作日志

获取 Pipeline 的操作日志。

**请求**

```
GET /pipeline_service/pipeline/log
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | Pipeline ID（query 参数） |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| logs | list&lt;PipelineLog&gt; | 日志列表 |

---

### PipelineAppendNote 添加备注

为 Pipeline 添加备注。

**请求**

```
POST /pipeline_service/pipeline/note_list/append
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| action_id | string | 是 | Action ID |
| status | string | 否 | 状态 |
| content | string | 是 | 备注内容 |
| files | list&lt;string&gt; | 否 | 文件列表 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| note_id | string | 备注 ID |

---

### PipelineUpdateNote 更新备注

更新 Pipeline 的备注。

**请求**

```
POST /pipeline_service/pipeline/note_list/update_one
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| action_id | string | 是 | Action ID |
| note_id | string | 是 | 备注 ID |
| status | string | 否 | 状态 |
| content | string | 是 | 备注内容 |
| files | list&lt;string&gt; | 否 | 文件列表 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |

---

### PipelineDeleteNote 删除备注

删除 Pipeline 的备注。

**请求**

```
POST /pipeline_service/pipeline/note_list/delete_one
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| action_id | string | 是 | Action ID |
| note_id | string | 是 | 备注 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |

---

### PipelineUpdateField 更新字段

更新 Pipeline Action 的特定字段。

**请求**

```
POST /pipeline_service/pipeline/action_info/update_field
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| action_id | string | 是 | Action ID |
| action_info_fields | map&lt;string, string&gt; | 是 | 要更新的字段 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |

---

### CheckPipelineExists 检查 Pipeline 是否存在

检查指定人才和项目是否已存在 Pipeline。

**请求**

```
POST /pipeline_service/pipeline/check_exists
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| person_leads_id | string | 是 | 人才 ID |
| project_id | string | 是 | 项目 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| exists | bool | 是否存在 |

---

### CheckPipelineExistsV2 检查 Pipeline 是否存在 V2

检查指定人才和项目是否已存在 Pipeline（V2 版本，支持更多参数）。

**请求**

```
POST /pipeline_service/pipeline/check_exists_v2
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| person_leads_id | string | 否 | 人才 ID |
| project_id | string | 是 | 项目 ID |
| mobile | string | 否 | 手机号 |
| name | string | 否 | 姓名 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline_id | string | Pipeline ID（如存在） |

---

### GetActionInfo 获取 Action 信息

获取指定 Action 的详细信息。

**请求**

```
POST /pipeline_service/pipeline/action/info
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| action_id | string | 是 | Action ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| action | map&lt;string, string&gt; | Action 数据（interface{} 类型） |

---

### GetCurrentUserPermission 获取当前用户权限

获取当前用户对多个 Pipeline 的权限。

**请求**

```
POST /pipeline_service/pipeline/current_user/permission
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_ids | list&lt;string&gt; | 是 | Pipeline ID 列表 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| permissions | map&lt;string, bool&gt; | 权限映射 |

---

### ActionStatusUpdate 更新 Action 状态

更新 Action 的状态。

**请求**

```
POST /pipeline_service/pipeline/action/status/update
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| action_id | string | 是 | Action ID |
| status | string | 是 | 新状态 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| msg | string | 消息 |

---

### SetFinalInterview 设置终面

设置 Pipeline 的终面阶段。

**请求**

```
POST /pipeline_service/pipeline/final_interview/set
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| interview_step_id | string | 否 | 面试阶段 ID（有数据时需传） |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |

---

### SetBenchmark 设置 Benchmark

将 Pipeline 设置为 Benchmark。

**请求**

```
POST /pipeline_service/pipeline/set_benchmark
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |

**响应**

（响应为空结构）

---

### PipelineUpdateBasicInfo 更新基础信息

更新 Pipeline 的基础信息。

**请求**

```
POST /pipeline_service/pipeline/basic_info/update
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| talent_name | string | 否 | 人才姓名 |
| talent_title | string | 否 | 人才职位 |
| talent_phone | string | 否 | 人才电话 |
| attachment_id | string | 否 | 附件 ID |
| talent_company | string | 否 | 人才公司 |
| talent_school | string | 否 | 人才学校 |
| talent_degree | string | 否 | 人才学历 |
| permission_level | string | 否 | 权限级别 |

**响应**

（响应为空结构）

---

### GetPipelineListByJobs 按岗位获取 Pipeline 列表

根据岗位 ID 列表获取 Pipeline。

**请求**

```
POST /pipeline_service/pipeline/list_by_jobs
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_ids | list&lt;string&gt; | 是 | 岗位 ID 列表 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| pipelines | list&lt;ProjectData&gt; | Pipeline 列表 |

---

### GetPipelineIDsByPersonLeadsID 根据人才ID获取 Pipeline

根据人才 ID 获取关联的所有 Pipeline。

**请求**

```
POST /pipeline_service/pipeline/get_pipeline_ids_by_person_leads_id
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| person_leads_id | string | 是 | 人才 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| pipelines | list&lt;PipelineRelatedData&gt; | Pipeline 关联数据列表 |

---

### PipelineTerminate 终止 Pipeline

终止或取消终止 Pipeline。

**请求**

```
POST /pipeline_service/pipeline/terminate
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| action | string | 是 | 操作（terminate 或 cancel） |

**响应**

（响应为空结构）

---

### InterviewOptionalTimeEdit 编辑面试可选时间

编辑面试的可选时间段。

**请求**

```
POST /pipeline_service/pipeline/interview/optional_time/edit
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |
| optional_time | list&lt;TimeSlot&gt; | 是 | 可选时间段列表 |
| role | string | 是 | 角色 |

**响应**

（响应为空结构）

---

### InterviewOptionalTimeGet 获取面试可选时间

获取面试的可选时间段。

**请求**

```
POST /pipeline_service/pipeline/interview/optional_time/get
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| step_id | string | 是 | 阶段 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| interview_round | i32 | 第几轮面试 |
| status | string | 面试状态 |
| optional_time | list&lt;TimeSlot&gt; | 可选时间段 |
| role | string | 角色 |

---

### LastestInterview 获取最新面试

获取 Pipeline 的最新面试信息。

**请求**

```
POST /pipeline_service/pipeline/lastest_interview
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| remark | string | 否 | 备注 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| step_id | string | 阶段 ID |
| interview_time_action_id | string | 面试时间 Action ID |
| interview_round | i32 | 第几轮面试 |

---

### SourcingMatchScore Sourcing 匹配分数

获取 Sourcing Pipeline 的匹配分数。

**请求**

```
POST /pipeline_service/pipeline/sourcing/match_score
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_id | string | 是 | 岗位 ID |
| pipeline_ids | list&lt;string&gt; | 否 | Pipeline ID 列表（可选） |
| created_in_days | i64 | 否 | 创建天数内 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| data | list&lt;MatchScoreInfo&gt; | 匹配分数信息列表 |

---

### PipelineUpdateJobIntent 更新求职意向

更新 Pipeline 的求职意向。

**请求**

```
POST /pipeline_service/pipeline/update_job_intent
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |
| job_intent | string | 是 | 求职意向 |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |

---

### TalentIdToPersonLeadsId 人才ID转换

将 Talent ID 转换为 PersonLeads ID。

**请求**

```
POST /pipeline_service/pipeline/talent_id_to_person_leads_id
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| talent_id | string | 是 | Talent ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| person_leads_id | string | PersonLeads ID |

---

### TalentProjectIdToPipelineId 项目ID转换

将 Talent ID 和 Project ID 转换为 Pipeline ID。

**请求**

```
POST /pipeline_service/pipeline/talent_project_id_to_pipeline_id
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| talent_id | string | 是 | Talent ID |
| project_id | string | 是 | 项目 ID |

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline_id | string | Pipeline ID |

---

### RecommendationReportPushed 推荐报告已推送

标记推荐报告已推送。

**请求**

```
POST /pipeline_service/pipeline/recommendation_report/pushed
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_id | string | 是 | Pipeline ID |

**响应**

（响应为空结构）

---

### MigrateRecommendationActions 迁移推荐 Actions

批量迁移推荐 Actions。

**请求**

```
POST /pipeline_service/pipeline/migrate_recommendation_actions
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pipeline_ids | list&lt;string&gt; | 是 | Pipeline ID 列表 |

**响应**

（响应为空结构）

---

### ParseEvaluateResult 解析评估结果

解析 AI 匹配评估结果。

**请求**

```
POST /pipeline_service/ai_match/parse_evaluate_result
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| evaluate_results | list&lt;EvaluateResult&gt; | 是 | 评估结果列表 |

**响应**

（响应为空结构）
