---
name: ttc-crm-talent
description: 调用 ttc-crm TalentStore 后端服务。包含人才搜索、人才管理、档案管理、附件管理、自定义列表、推荐报告等模块，用于完整的人才库管理业务闭环。
---

# TalentStore 人才库服务

ttc-crm TalentStore 后端服务，提供完整的人才库管理 API。

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
接口路径：/talent_store/v1/person_leads/basic_info

线上环境：https://api.ttcadvisory.com/api/talent_store/v1/person_leads/basic_info
测试环境：https://api-int.ttcadvisory.com/api/talent_store/v1/person_leads/basic_info
```

### 请求头配置

所有接口都需要在请求头中携带 JWT Token：

```http
Authorization: Bearer <your_jwt_token>
Content-Type: application/json
```

> **注意：** JWT Token 需要向管理员申请获取，不同环境的 Token 可能不同。

### 请求示例

以获取人才基础信息为例（测试环境）：

```bash
curl -X POST 'https://api-int.ttcadvisory.com/api/talent_store/v1/person_leads/basic_info' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json' \
  -d '{
    "person_leads_id": "pl_123456",
    "refresh": false
  }'
```

### 常用接口完整 URL（以线上环境为例）

| 接口 | 方法 | 完整 URL |
|------|------|----------|
| 搜索人才 | POST | `https://api.ttcadvisory.com/api/talent_store/v1/search` |
| 获取基础信息 | POST | `https://api.ttcadvisory.com/api/talent_store/v1/person_leads/basic_info` |
| 获取详细信息 | POST | `https://api.ttcadvisory.com/api/talent_store/v1/person_leads/detail_info` |
| 创建人才 | POST | `https://api.ttcadvisory.com/api/talent_store/v1/person_leads/create` |
| AI搜索 | POST | `https://api.ttcadvisory.com/api/talent_store/v1/ai_search` |
| 获取名单列表 | POST | `https://api.ttcadvisory.com/api/talent_store/v1/customized_list/get` |
| 获取报告列表 | POST | `https://api.ttcadvisory.com/api/talent_store/v1/recommendation_report/list` |

---

## 模块概览

| 模块 | 说明 | 详细文档 |
|------|------|----------|
| **Search** | 人才搜索：关键词搜索、AI搜索、智能列表、过滤器 | [talent-search](./references/talent-search.md) |
| **PersonLeads** | 人才管理：创建/更新人才、档案、附件、评论、关系 | [talent-person-leads](./references/talent-person-leads.md) |
| **CustomizedList** | 自定义列表：名单管理、候选人操作、协作者 | [talent-customized-list](./references/talent-customized-list.md) |
| **RecommendationReport** | 推荐报告：报告生成、下载、简历解析 | [talent-recommendation-report](./references/talent-recommendation-report.md) |
| **Base** | 基础类型：枚举、数据结构定义 | [talent-base](./references/talent-base.md) |

---

## 服务架构

```
TalentStore
├── Search (搜索服务)
│   ├── Search                    # 人才搜索
│   ├── SearchForLovtalent        # Lovtalent专用搜索
│   ├── AISearch                  # AI智能搜索
│   ├── SearchRaw                 # 原始查询搜索
│   ├── GetSearchFilters          # 获取搜索过滤条件
│   ├── GetSearchHistoryList      # 获取搜索历史
│   ├── PersonLeadsMatch          # 人才匹配
│   └── GetSystemTagList          # 获取系统标签列表
│
├── SmartList (智能列表)
│   ├── GetSmartList              # 获取智能列表
│   └── GetSmartListDetail        # 获取智能列表详情
│
├── PersonLeads (人才管理)
│   ├── CreatePersonLeads         # 创建人才
│   ├── UpdatePersonLeads         # 更新人才
│   ├── MakeCall                  # 拨打电话
│   ├── GetOperationLogsList      # 获取操作日志
│   ├── GetPersonLeadsSingleScopeRelation  # 获取人才关系
│   ├── ReparsePersonLeadsProfileFromAttachment  # 重新解析档案
│   ├── PersonLeadsEventProcessingNotice  # 事件处理通知
│   ├── GetPersonLeadsEventJobStatus  # 获取事件Job状态
│   ├── GetPersonLeadsInviteInfo  # 获取引流信息
│   └── PublicPersonLeads         # 公开人才
│
├── PersonLeadsProfile (档案服务)
│   ├── GetPersonLeadsProfile     # 获取档案详情
│   ├── UpdatePersonLeadsProfileByProfile  # 更新档案
│   ├── UpdatePersonLeadsProfile  # KV形式更新档案
│   ├── CalculatePersonLeadsProfile  # 计算档案
│   ├── GetPersonLeadsBasicInfo   # 获取基础信息
│   ├── GetPersonLeadsDetailInfo  # 获取详细信息
│   ├── PublishPersonLeadsProfile # 发布档案
│   └── GetPersonLeadsCreator     # 获取创建人
│
├── PersonLeadsAttachment (附件服务)
│   ├── GetPersonLeadsAttachmentList  # 获取附件列表
│   ├── GetPersonLeadsAttachmentByID  # 获取附件详情
│   └── UploadFile                # 上传文件
│
├── PersonLeadsComments (评论服务)
│   ├── CreatePersonLeadsComments # 创建评论
│   ├── EditPersonLeadsComments   # 编辑评论
│   ├── PersonLeadsCommentsEventProcessingNotice  # 评论事件通知
│   └── CreatePersonLeadsCommentsTxt  # 创建txt解析备注
│
├── CustomizedList (自定义列表)
│   ├── GetPersonLeadsCustomizedListMine  # 获取我的名单
│   ├── CreatePersonLeadsCustomizedList   # 创建名单
│   ├── UpdatePersonLeadsCustomizedList   # 更新名单
│   ├── RemovePersonLeadsCustomizedList   # 删除名单
│   ├── TogglePersonLeadsInCustomizedList # 切换候选人状态
│   ├── ModifyPersonLeadsInCustomizedLists  # 修改候选人在名单状态
│   ├── UpdatePersonLeadsColors   # 更新颜色
│   ├── GetMyListDetail           # 获取列表详情
│   ├── ApplyToParticipant        # 申请成为协作者
│   ├── ReplacePersonLeadsInCustomizedList  # 替换候选人
│   ├── AISearchInCustomizedList  # AI搜索名单
│   ├── CustomizedListStatusNotice  # 名单状态通知
│   ├── UpdateCustomizedListStatus  # 修改名单状态
│   ├── MoveCustomizedList        # 移动名单
│   └── SearchCustomizedList      # 搜索名单
│
├── RecommendationReport (推荐报告)
│   ├── ListRecommendationReport  # 获取报告列表
│   ├── GetRecommendationReportByExternalEntity  # 通过外部实体获取报告
│   ├── GetRecommendationReport   # 获取报告详情
│   ├── SaveRecommendationReport  # 保存报告
│   ├── SaveRecommendationReportV2  # 保存报告V2
│   ├── DownloadRecommendationReport  # 下载报告
│   ├── ParseResume               # 解析简历
│   ├── ReparseResumeSpecifiedContent  # 重新解析简历指定内容
│   ├── StreamReparseResumeSpecifiedContent  # 流式重新解析
│   ├── FormatContent             # 格式化内容
│   └── GetRecommendationReportOperationLogs  # 获取操作日志
│
├── ObjectUniq (归一化服务)
│   ├── SearchSchool              # 学校归一化搜索
│   └── SearchCompany             # 公司归一化搜索
│
├── UserConfig (用户配置)
│   ├── UpdateUserConfig          # 更新用户配置
│   └── GetUserVisibility         # 获取用户可见性
│
├── ExternalEvent (外部事件)
│   └── CreateExternalEventByUser # 创建外部事件
│
└── TimeBasedProfile (时间线档案)
    ├── GetTimeBasedProfileDetail # 获取时间线档案详情
    └── SaveNewTimeBasedProfileSource  # 保存新来源
```

---

## 快速参考

### Search 搜索服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 搜索人才 | POST | `/talent_store/v1/search` |
| Lovtalent搜索 | POST | `/talent_store/v1/search-for-lovtalent` |
| 获取过滤条件 | GET | `/talent_store/v1/search/filters` |
| 获取搜索历史 | POST | `/talent_store/v1/search/history/list` |
| 人才匹配 | POST | `/talent_store/v1/person_leads/match` |
| 原始查询 | POST | `/talent_store/v1/search_raw` |
| AI搜索 | POST | `/talent_store/v1/ai_search` |
| 获取系统标签 | GET | `/talent_store/v1/system_tags` |

### SmartList 智能列表

| 操作 | 方法 | 路径 |
|------|------|------|
| 获取智能列表 | GET | `/talent_store/v1/search/smart_list/list` |
| 获取列表详情 | POST | `/talent_store/v1/search/smart_list/info` |

### PersonLeads 人才管理

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建人才 | POST | `/talent_store/v1/person_leads/create` |
| 更新人才 | POST | `/talent_store/v1/person_leads/update` |
| 拨打电话 | POST | `/talent_store/v1/person_leads/make_call` |
| 获取操作日志 | POST | `/talent_store/v1/person_leads/operation_logs/list` |
| 获取人才关系 | POST | `/talent_store/v1/person_leads/relation/single_scope` |
| 批量获取人才关系 | POST | `/talent_store/v1/person_leads/relation/single_scope/mget` |
| 重新解析档案 | POST | `/talent_store/v1/person_leads/profile/reparse_from_attachment` |
| 事件处理通知 | GET | `/talent_store/v1/person_leads/profile/event_processing_notice` |
| 获取Job状态 | POST | `/talent_store/v1/person_leads/job_status` |
| 获取引流信息 | GET | `/talent_store/v1/person_leads/invite_info` |
| 公开人才 | POST | `/talent_store/v1/person_leads/public` |

### PersonLeadsProfile 档案服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 获取档案详情 | POST | `/talent_store/v1/person_leads/profile/get` |
| 更新档案(profile) | POST | `/talent_store/v1/person_leads/profile/update` |
| 更新档案(KV) | POST | `/talent_store/v1/person_leads/profile_update` |
| 计算档案 | POST | `/talent_store/v1/person_leads/profile/calculate` |
| 获取基础信息 | POST | `/talent_store/v1/person_leads/basic_info` |
| 获取详细信息 | POST | `/talent_store/v1/person_leads/detail_info` |
| 发布档案 | POST | `/talent_store/v1/person_leads/profile/publish` |
| 获取创建人 | POST | `/talent_store/v1/person_leads/creator_info` |

### PersonLeadsAttachment 附件服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 获取附件列表 | POST | `/talent_store/v1/person_leads/resume/attachment/list` |
| 获取附件详情 | POST | `/talent_store/v1/person_leads/resume/attachment/get_by_id` |
| 上传文件 | POST | `/talent_store/v1/file/upload` |

### PersonLeadsComments 评论服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建评论 | POST | `/talent_store/v1/person_leads/comments/create` |
| 编辑评论 | POST | `/talent_store/v1/person_leads/comments/edit` |
| 评论事件通知 | GET | `/talent_store/v1/person_leads/comments/event_processing_notice` |
| 创建txt解析备注 | POST | `/talent_store/v1/person_leads/comments/create_txt` |

### CustomizedList 自定义列表

| 操作 | 方法 | 路径 |
|------|------|------|
| 获取我的名单 | POST | `/talent_store/v1/customized_list/get` |
| 创建名单 | POST | `/talent_store/v1/customized_list/create` |
| 更新名单 | POST | `/talent_store/v1/customized_list/update` |
| 删除名单 | POST | `/talent_store/v1/customized_list/remove` |
| 切换候选人状态 | POST | `/talent_store/v1/customized_list/action` |
| 修改候选人在名单状态 | POST | `/talent_store/v1/customized_list/modify_person_leads_in_list` |
| 更新颜色 | POST | `/talent_store/v1/customized_list/update_colors` |
| 获取列表详情 | POST | `/talent_store/v1/customized_list/info` |
| 申请成为协作者 | POST | `/talent_store/v1/customized_list/apply_to_participant` |
| 替换候选人 | POST | `/talent_store/v1/customized_list/replace_person_leads` |
| AI搜索名单 | POST | `/talent_store/v1/customized_list/ai_search` |
| 名单状态通知 | GET | `/talent_store/v1/customized_list/status` |
| 修改名单状态 | POST | `/talent_store/v1/customized_list/update_status` |
| 移动名单 | POST | `/talent_store/v1/customized_list/move` |
| 搜索名单 | GET | `/talent_store/v1/customized_list/search` |

### RecommendationReport 推荐报告

| 操作 | 方法 | 路径 |
|------|------|------|
| 获取报告列表 | POST | `/talent_store/v1/recommendation_report/list` |
| 通过外部实体获取报告 | POST | `/talent_store/v1/recommendation_report/get_by_external_entity` |
| 获取报告详情 | POST | `/talent_store/v1/recommendation_report/get` |
| 保存报告 | POST | `/talent_store/v1/recommendation_report/save` |
| 保存报告V2 | POST | `/talent_store/v1/recommendation_report/save_v2` |
| 下载报告 | POST | `/talent_store/v1/recommendation_report/download` |
| 解析简历 | GET | `/talent_store/v1/recommendation_report/parse_resume` |
| 重新解析简历内容 | GET | `/talent_store/v1/recommendation_report/reparse_resume_specified_content` |
| 流式重新解析 | GET | `/talent_store/v1/recommendation_report/stream_reparse_resume_specified_content` |
| 格式化内容 | POST | `/talent_store/v1/recommendation_report/format_content` |
| 获取操作日志 | POST | `/talent_store/v1/recommendation_report/get_operation_logs` |

### ObjectUniq 归一化服务

| 操作 | 方法 | 路径 |
|------|------|------|
| 学校归一化搜索 | POST | `/talent_store/v1/object-uniq/search-school` |
| 公司归一化搜索 | POST | `/talent_store/v1/object-uniq/search-company` |

### UserConfig 用户配置

| 操作 | 方法 | 路径 |
|------|------|------|
| 更新用户配置 | POST | `/talent_store/v1/user/config` |
| 获取用户可见性 | GET | `/talent_store/v1/user/visibility` |

### ExternalEvent 外部事件

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建外部事件 | POST | `/talent_store/v1/person_leads/external_event/create_by_user` |

### TimeBasedProfile 时间线档案

| 操作 | 方法 | 路径 |
|------|------|------|
| 获取时间线档案详情 | GET | `/talent_store/v1/time_based/profile_detail` |
| 保存新来源 | POST | `/talent_store/v1/time_based/save_new_source` |

---

## 核心枚举速查

### 自定义列表状态 (CustomizedListStatus)

| 值 | 含义 |
|----|------|
| 1 | 等待中 (WAITING) |
| 2 | Sourcing中 (SOURCING) |
| 3 | 已结束 (COMPLETED) |

### 公司筛选类型 (CompanyEnum)

| 值 | 含义 |
|----|------|
| 1 | 当前公司 (CURRENT) |
| 2 | 曾经公司 (FORMER) |

### 关键词查询类型 (KeywordEnum)

| 值 | 含义 |
|----|------|
| 1 | 或 (OR) |
| 2 | 且 (AND) |

### 推荐报告模板类型 (RecommendationReportTemplate)

| 值 | 含义 |
|----|------|
| 1 | 快速 (QUICK) |
| 2 | 标准 (STANDARD) |

### 推荐报告项样式 (RecommendationReportItemStyle)

| 值 | 含义 |
|----|------|
| 1 | 标题 (TITLE) |
| 2 | 时间 (DATE) |
| 3 | 内容 (DESCRIPTION) |

---

## 相关文档

- [talent-base](./references/talent-base.md) - 基础类型、枚举、数据结构完整定义
- [talent-search](./references/talent-search.md) - 搜索服务详细 API
- [talent-person-leads](./references/talent-person-leads.md) - 人才管理服务详细 API
- [talent-customized-list](./references/talent-customized-list.md) - 自定义列表服务详细 API
- [talent-recommendation-report](./references/talent-recommendation-report.md) - 推荐报告服务详细 API

---
