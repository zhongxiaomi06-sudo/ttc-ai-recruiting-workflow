---
name: ttc-crm-pipeline
description: 调用 ttc-crm Pipeline 后端服务。包含 Pipeline 管理、项目管理、任务管理、通知管理、账单管理等模块，用于完整的招聘流程管理业务闭环。
---

# Pipeline 招聘流程服务

ttc-crm Pipeline 后端服务，提供完整的招聘流程管理 API。

---

## 接口调用说明

### 环境配置

| 环境 | 域名 | Base URL |
|------|------|----------|
| **线上环境 (prod)** | `api.ttcadvisory.com` | `https://api.ttcadvisory.com/api` |
| **测试环境 (int)** | `api-int.ttcadvisory.com` | `https://api-int.ttcadvisory.com/api` |

### 认证方式

- **认证类型：** JWT Token (Bearer)
- **获取方式：** 向管理员申请

### 请求 URL 拼接

完整请求 URL = `Base URL` + `接口路径`

**示例：**
```
接口路径：/pipeline_service/pipeline/list

线上环境：https://api.ttcadvisory.com/api/pipeline_service/pipeline/list
测试环境：https://api-int.ttcadvisory.com/api/pipeline_service/pipeline/list
```

### 请求头配置

所有接口都需要在请求头中携带 JWT Token：

```http
Authorization: Bearer <your_jwt_token>
Content-Type: application/json
```

> **注意：** JWT Token 需要向管理员申请获取，不同环境的 Token 可能不同。

### 请求示例

以获取 Pipeline 列表为例（测试环境）：

```bash
curl -X POST 'https://api-int.ttcadvisory.com/api/pipeline_service/pipeline/list' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -d '{
    "keyword": "",
    "filter": [],
    "sort": [{"key": "latest_work_time", "sort": "desc"}],
    "limit": 20,
    "offset": 0
  }'
```

以获取 Pipeline 详情为例（线上环境）：

```bash
curl -X POST 'https://api.ttcadvisory.com/api/pipeline_service/pipeline/info' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -d '{
    "pipeline_id": "pl_123456789"
  }'
```

### 常用接口完整 URL（以线上环境为例）

| 接口 | 方法 | 完整 URL |
|------|------|----------|
| 创建 Pipeline | POST | `https://api.ttcadvisory.com/api/pipeline_service/pipeline/create` |
| 获取 Pipeline 列表 | POST | `https://api.ttcadvisory.com/api/pipeline_service/pipeline/list` |
| 获取 Pipeline 详情 | POST | `https://api.ttcadvisory.com/api/pipeline_service/pipeline/info` |
| 更新 Pipeline | POST | `https://api.ttcadvisory.com/api/pipeline_service/pipeline/update` |
| 获取项目列表 | POST | `https://api.ttcadvisory.com/api/pipeline_service/project/list` |
| 获取任务列表 | POST | `https://api.ttcadvisory.com/api/pipeline_service/task_service/current_user/task/list` |

---

## 模块概览

| 模块 | 说明 | 详细文档 |
|------|------|----------|
| **Pipeline** | 招聘流程管理：创建/更新 Pipeline、阶段管理、备注、状态更新 | [pipeline-service](./references/pipeline-service.md) |
| **Project** | 项目管理：项目列表、简历提交、AI搜索、Benchmark | [pipeline-project](./references/pipeline-project.md) |
| **Task** | 任务管理：任务列表、任务类型、任务状态更新 | [pipeline-task](./references/pipeline-task.md) |
| **Notification** | 通知管理：创建/更新/删除通知、查询通知列表 | [pipeline-notification](./references/pipeline-notification.md) |
| **Base** | 基础类型：枚举、数据结构定义 | [pipeline-base](./references/pipeline-base.md) |

---

## 服务架构

```
Pipeline
├── IndexService (索引服务)
│   ├── BrushIndex                # 刷新单个索引
│   ├── BrushAllIndex             # 刷新所有索引
│   ├── InsertMongo               # 插入 MongoDB
│   ├── FindFromMongo             # 从 MongoDB 查询
│   ├── BrushBiData               # 刷新 BI 数据
│   ├── BrushAllBiData            # 刷新所有 BI 数据
│   ├── Test                      # 测试接口
│   └── BrushTaskList             # 刷新任务列表
│
├── BillingService (账单服务)
│   ├── CreateBilling             # 创建账单
│   └── BillingInfo               # 获取账单信息
│
├── TaskService (任务服务)
│   ├── GetCurrentUserTaskTypes   # 获取当前用户任务类型
│   ├── GetCurrentUserTaskList    # 获取当前用户任务列表
│   ├── GetCurrentUserTaskListByJob  # 按岗位获取任务列表
│   ├── GetCurrentUserInProgressTasks  # 获取进行中任务
│   ├── UpdateTaskStatus          # 更新任务状态
│   ├── GetTaskTypes              # 获取任务类型
│   ├── GetTaskList               # 获取任务列表
│   ├── SendTaskNotifications     # 发送任务通知
│   └── BrushTaskData             # 刷新任务数据
│
├── PipelineService (Pipeline 核心服务)
│   ├── PipelineCreate            # 创建 Pipeline
│   ├── CreatePipelineByPersonLeadsID  # 根据人才ID创建
│   ├── PipelineCreateByBenchmark # 根据 Benchmark 创建
│   ├── PipelineList              # Pipeline 列表
│   ├── SourcingPipelineList      # Sourcing Pipeline 列表
│   ├── SourcingPipelineCount     # Sourcing Pipeline 计数
│   ├── PipelineInfo              # Pipeline 详情
│   ├── PipelineUpdate            # 更新 Pipeline
│   ├── PipelineAddStep           # 添加阶段
│   ├── PipelineDeleteStep        # 删除阶段
│   ├── PipelineLogs              # 操作日志
│   ├── PipelineAppendNote        # 添加备注
│   ├── PipelineUpdateNote        # 更新备注
│   ├── PipelineDeleteNote        # 删除备注
│   ├── PipelineUpdateField       # 更新字段
│   ├── TalentIdToPersonLeadsId   # 人才ID转换
│   ├── TalentProjectIdToPipelineId  # 项目ID转换
│   ├── CheckPipelineExists       # 检查 Pipeline 是否存在
│   ├── CheckPipelineExistsV2     # 检查 Pipeline 是否存在V2
│   ├── GetActionInfo             # 获取 Action 信息
│   ├── GetCurrentUserPermission  # 获取当前用户权限
│   ├── RecommendationReportPushed  # 推荐报告已推送
│   ├── ActionStatusUpdate        # Action 状态更新
│   ├── SetFinalInterview         # 设置终面
│   ├── SetBenchmark              # 设置 Benchmark
│   ├── MigrateRecommendationActions  # 迁移推荐 Actions
│   ├── PipelineUpdateBasicInfo   # 更新基础信息
│   ├── GetPipelineListByJobs     # 按岗位获取 Pipeline
│   ├── GetPipelineIDsByPersonLeadsID  # 根据人才ID获取 Pipeline
│   ├── ParseEvaluateResult       # 解析评估结果
│   ├── PipelineTerminate         # 终止 Pipeline
│   ├── InterviewOptionalTimeEdit # 编辑面试可选时间
│   ├── InterviewOptionalTimeGet  # 获取面试可选时间
│   ├── LastestInterview          # 获取最新面试
│   ├── SourcingMatchScore        # Sourcing 匹配分数
│   └── PipelineUpdateJobIntent   # 更新求职意向
│
├── NotificationService (通知服务)
│   ├── CreateNotification        # 创建通知
│   ├── UpdateNotification        # 更新通知
│   ├── DeleteNotification        # 删除通知
│   ├── GetNotification           # 获取通知
│   ├── ListNotificationsByPipeline  # 按 Pipeline 查询通知
│   ├── ListNotificationsByStep   # 按阶段查询通知
│   └── ListNotificationsByAction # 按 Action 查询通知
│
├── ProjectService (项目服务)
│   ├── ProjectList               # 项目列表
│   ├── ProjectInfo               # 项目详情
│   ├── CreatePipelineByResume    # 通过简历创建 Pipeline
│   ├── ProjectResumeStatus       # 简历状态
│   ├── ProjectResumeStatusByIDs  # 批量查询简历状态
│   ├── ProjectIDsByChatIDs       # 通过 ChatID 获取项目
│   ├── CreateProjectAISearchJob  # 创建 AI 搜索任务
│   ├── ProjectAISearchStatus     # AI 搜索状态
│   ├── StartBenchmark            # 启动 Benchmark
│   ├── GetBenchmarkLogs          # 获取 Benchmark 日志
│   ├── ClearProjectBenchmarkTriedIDs  # 清除 Benchmark 已尝试ID
│   ├── GetAceJobPersonLeadsIDs   # 获取王牌岗位人才ID
│   ├── StartAceJobByProjectID    # 按项目启动王牌岗位
│   └── StartAceJobMatchByJobID   # 按岗位启动王牌岗位匹配
│
├── SyncService (同步服务)
│   └── SyncAceJobMatchBitable    # 同步王牌岗位匹配到多维表格
│
├── ClientService (客户服务)
│   └── ClientList                # 客户列表
│
├── UserService (用户服务)
│   ├── UserInfo                  # 用户信息
│   └── UserList                  # 用户列表
│
└── FileService (文件服务)
    ├── FileInfo                  # 文件信息
    └── FileUpload                # 文件上传
```

---

## 快速参考

### PipelineService Pipeline 核心服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建 Pipeline | POST | `/pipeline_service/pipeline/create` |
| 根据人才ID创建 | POST | `/pipeline_service/pipeline/create_by_person_leads_id` |
| 根据 Benchmark 创建 | POST | `/pipeline_service/pipeline/create_by_benchmark` |
| 获取列表 | POST | `/pipeline_service/pipeline/list` |
| Sourcing 列表 | POST | `/pipeline_service/pipeline/sourcing/list` |
| Sourcing 计数 | POST | `/pipeline_service/pipeline/sourcing/count` |
| 获取详情 | POST | `/pipeline_service/pipeline/info` |
| 更新 Pipeline | POST | `/pipeline_service/pipeline/update` |
| 添加阶段 | POST | `/pipeline_service/pipeline/add-step` |
| 删除阶段 | POST | `/pipeline_service/pipeline/delete-step` |
| 获取日志 | GET | `/pipeline_service/pipeline/log` |
| 添加备注 | POST | `/pipeline_service/pipeline/note_list/append` |
| 更新备注 | POST | `/pipeline_service/pipeline/note_list/update_one` |
| 删除备注 | POST | `/pipeline_service/pipeline/note_list/delete_one` |
| 更新字段 | POST | `/pipeline_service/pipeline/action_info/update_field` |
| 检查是否存在 | POST | `/pipeline_service/pipeline/check_exists` |
| 检查是否存在V2 | POST | `/pipeline_service/pipeline/check_exists_v2` |
| 获取 Action 信息 | POST | `/pipeline_service/pipeline/action/info` |
| 获取当前用户权限 | POST | `/pipeline_service/pipeline/current_user/permission` |
| Action 状态更新 | POST | `/pipeline_service/pipeline/action/status/update` |
| 设置终面 | POST | `/pipeline_service/pipeline/final_interview/set` |
| 设置 Benchmark | POST | `/pipeline_service/pipeline/set_benchmark` |
| 更新基础信息 | POST | `/pipeline_service/pipeline/basic_info/update` |
| 按岗位获取列表 | POST | `/pipeline_service/pipeline/list_by_jobs` |
| 根据人才ID获取 | POST | `/pipeline_service/pipeline/get_pipeline_ids_by_person_leads_id` |
| 终止 Pipeline | POST | `/pipeline_service/pipeline/terminate` |
| 编辑面试可选时间 | POST | `/pipeline_service/pipeline/interview/optional_time/edit` |
| 获取面试可选时间 | POST | `/pipeline_service/pipeline/interview/optional_time/get` |
| 获取最新面试 | POST | `/pipeline_service/pipeline/lastest_interview` |
| Sourcing 匹配分数 | POST | `/pipeline_service/pipeline/sourcing/match_score` |
| 更新求职意向 | POST | `/pipeline_service/pipeline/update_job_intent` |

### ProjectService 项目服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 项目列表 | POST | `/pipeline_service/project/list` |
| 项目详情 | POST | `/pipeline_service/project/info` |
| 通过简历创建 Pipeline | POST | `/pipeline_service/project/resume_submit` |
| 简历状态 | GET | `/pipeline_service/project/resume_status` |
| 批量查询简历状态 | POST | `/pipeline_service/project/resume_status_by_id` |
| 通过 ChatID 获取项目 | POST | `/pipeline_service/project/project_ids_by_chat_id` |
| 创建 AI 搜索任务 | POST | `/pipeline_service/project/ai_search/create` |
| AI 搜索状态 | POST | `/pipeline_service/project/ai_search/status` |
| 启动 Benchmark | POST | `/pipeline_service/project/benchmark/start` |
| 获取 Benchmark 日志 | POST | `/pipeline_service/project/benchmark/logs` |
| 清除 Benchmark 已尝试ID | POST | `/pipeline_service/project/benchmark/clear_tried_ids` |
| 获取王牌岗位人才ID | GET | `/pipeline_service/project/ace_job/person_leads_ids` |
| 按项目启动王牌岗位 | POST | `/pipeline_service/project/ace_job/start_by_project_id` |
| 按岗位启动王牌岗位匹配 | POST | `/pipeline_service/project/ace_job/start_job_match` |

### TaskService 任务服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 获取当前用户任务类型 | POST | `/pipeline_service/task_service/current_user/task/types` |
| 获取当前用户任务列表 | POST | `/pipeline_service/task_service/current_user/task/list` |
| 按岗位获取任务列表 | POST | `/pipeline_service/task_service/current_user/task/list_by_job` |
| 获取进行中任务 | POST | `/pipeline_service/task_service/current_user/task/in_progress` |
| 更新任务状态 | POST | `/pipeline_service/task_service/task/update` |
| 获取任务类型 | POST | `/pipeline_service/task_service/task/types` |
| 获取任务列表 | POST | `/pipeline_service/task_service/task/list` |
| 发送任务通知 | POST | `/pipeline_service/task_service/send_notifications` |
| 刷新任务数据 | POST | `/pipeline_service/task_service/brush_task_data` |

### NotificationService 通知服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建通知 | POST | `/pipeline_service/pipeline/notification/create` |
| 更新通知 | POST | `/pipeline_service/pipeline/notification/update` |
| 删除通知 | POST | `/pipeline_service/pipeline/notification/delete` |
| 获取通知 | POST | `/pipeline_service/pipeline/notification/get` |
| 按 Pipeline 查询 | POST | `/pipeline_service/pipeline/notification/list_by_pipeline` |
| 按阶段查询 | POST | `/pipeline_service/pipeline/notification/list_by_step` |
| 按 Action 查询 | POST | `/pipeline_service/pipeline/notification/list_by_action` |

### BillingService 账单服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建账单 | POST | `/pipeline_service/billing/create` |
| 获取账单信息 | GET | `/pipeline_service/billing/info` |

### ClientService 客户服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 客户列表 | POST | `/pipeline_service/client/list` |

### UserService 用户服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 用户信息 | GET | `/pipeline_service/user/info` |
| 用户列表 | GET | `/pipeline_service/user/list` |

### FileService 文件服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 文件信息 | GET | `/pipeline_service/file/info` |
| 文件上传 | POST | `/pipeline_service/file/upload` |

### SyncService 同步服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 同步王牌岗位匹配 | POST | `/pipeline_service/sync/ace_job_match_bitable` |

---

## 核心枚举速查

### Pipeline 阶段类型 (StepType)

| 值 | 含义 |
|----|------|
| Recommendation | 推荐阶段 |
| Interview | 面试阶段 |
| Offer | Offer 阶段 |
| Onboarding | 入职阶段 |

### Pipeline 状态 (Status)

| 值 | 含义 |
|----|------|
| Recommendable | 可推荐 |
| NotRecommendable | 不可推荐 |

### Pipeline 活跃状态 (ActiveState)

| 值 | 含义 |
|----|------|
| Progressing | 进行中 |
| Ended | 已终止 |
| Finished | 已完成 |

### 通知类型 (NotificationType)

| 值 | 含义 |
|----|------|
| before | 提前通知 |
| time | 定时通知 |

### 时间单位 (TimeUnit)

| 值 | 含义 |
|----|------|
| day | 天 |
| hour | 小时 |

---

## 相关文档

- [pipeline-base](./references/pipeline-base.md) - 基础类型、枚举、数据结构完整定义
- [pipeline-service](./references/pipeline-service.md) - Pipeline 核心服务详细 API
- [pipeline-project](./references/pipeline-project.md) - 项目服务详细 API
- [pipeline-task](./references/pipeline-task.md) - 任务服务详细 API
- [pipeline-notification](./references/pipeline-notification.md) - 通知服务详细 API

---
