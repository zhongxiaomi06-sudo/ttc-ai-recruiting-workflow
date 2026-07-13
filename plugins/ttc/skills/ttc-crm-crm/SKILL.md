---
name: ttc-crm-crm
description: 调用 ttc-crm CRM 后端服务。包含客户管理、职位管理、联系人管理、标签管理、备注管理、合同管理、飞书群聊等模块，用于完整的 CRM 业务闭环。
---

# CRM 客户关系管理服务

ttc-crm CRM 后端服务，提供完整的客户关系管理 API。

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
接口路径：/crm/v1/company/search

线上环境：https://api.ttcadvisory.com/api/crm/v1/company/search
测试环境：https://api-int.ttcadvisory.com/api/crm/v1/company/search
```

### 请求头配置

所有接口都需要在请求头中携带 JWT Token：

```http
Authorization: Bearer <your_jwt_token>
Content-Type: application/json
```

> **注意：** JWT Token 需要向管理员申请获取，不同环境的 Token 可能不同。

### 请求示例

以获取客户详情为例（线上环境）：

```bash
# 获取客户详情
curl -X GET 'https://api.ttcadvisory.com/api/crm/v1/company/CIZEBHS' \
  -H 'Authorization: Bearer <your_jwt_token>'
```

以搜索客户为例（测试环境）：

```bash
# 搜索客户
curl -X POST 'https://api-int.ttcadvisory.com/api/crm/v1/company/search' \
  -H 'Authorization: Bearer <your_jwt_token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "belong_type": 5,
    "keyword": "腾讯",
    "size": 20
  }'
```

### 常用接口完整 URL（以线上环境为例）

| 接口 | 方法 | 完整 URL | 示例 |
|------|------|----------|------|
| 获取客户详情 | GET | `/crm/v1/company/:unique_id` | `https://api.ttcadvisory.com/api/crm/v1/company/CIZEBHS` |
| 搜索客户 | POST | `/crm/v1/company/search` | `https://api.ttcadvisory.com/api/crm/v1/company/search` |
| 创建客户 | POST | `/crm/v1/company` | `https://api.ttcadvisory.com/api/crm/v1/company` |
| 获取职位详情 | GET | `/crm/v1/job/:unique_id` | `https://api.ttcadvisory.com/api/crm/v1/job/JABCDEF` |
| 搜索职位 | POST | `/crm/v1/job/search` | `https://api.ttcadvisory.com/api/crm/v1/job/search` |
| 创建职位 | POST | `/crm/v1/job` | `https://api.ttcadvisory.com/api/crm/v1/job` |
| 搜索联系人 | POST | `/crm/v1/contact/search` | `https://api.ttcadvisory.com/api/crm/v1/contact/search` |
| 获取行业标签 | GET | `/crm/v1/tag/industry` | `https://api.ttcadvisory.com/api/crm/v1/tag/industry` |

> **ID 格式说明：** 
> - Company unique_id 格式如 `CIZEBHS`（7位大写字母）
> - Job unique_id 格式如 `JABCDEF`（以 J 开头的7位大写字母）

---

## 模块概览

| 模块 | 说明 | 详细文档 |
|------|------|----------|
| **Company** | 客户管理：创建/更新客户、搜索客户、认证企业、合并检测 | [crm-company](./references/crm-company.md) |
| **Job** | 职位管理：创建/更新职位、搜索、王牌职位、AI评估、批量导入 | [crm-job](./references/crm-job.md) |
| **Contact** | 联系人管理：创建/更新联系人、搜索联系人 | [crm-contact](./references/crm-contact.md) |
| **Base** | 基础类型：枚举、数据结构定义 | [crm-base](./references/crm-base.md) |

---

## 服务架构

```
CrmService
├── Company (客户管理)
│   ├── CheckCreateCompany          # 检查是否可以创建公司
│   ├── CreateCompany               # 创建公司
│   ├── GetCompanyDetail            # 获取公司详情
│   ├── UpdateCompany               # 更新公司信息
│   ├── SearchCompany               # 搜索公司
│   ├── BatchGetCompanyDetail       # 批量获取公司详情
│   ├── PatchCompany                # 轻量级更新公司字段
│   ├── ClaimCompany                # 认领客户
│   ├── CheckCompanyMerged          # 检查客户是否被合并
│   └── ListCompanyExpirationDate   # 获取客户掉保日期
│
├── AuthCompany (企业认证)
│   ├── SearchAuthCompany           # 搜索认证企业
│   └── GetAuthCompany              # 获取认证企业
│
├── Job (职位管理)
│   ├── CreateJob                   # 创建职位
│   ├── GetJobDetail                # 获取职位详情
│   ├── UpdateJob                   # 更新职位信息
│   ├── SearchJob                   # 搜索职位
│   ├── QueryJob                    # 查询职位（多条件）
│   ├── BatchGetJobDetail           # 批量获取职位详情
│   ├── PatchJob                    # 轻量级更新职位字段
│   ├── UpdateJobStatus             # 更新职位状态
│   ├── FavoriteJob                 # 收藏/取消收藏职位
│   ├── ListCompanyJobs             # 获取客户职位列表
│   ├── GetJobProfile               # 获取职位画像
│   └── CreateJobSharePost          # 创建职位分享海报
│
├── AceJob (王牌职位)
│   ├── ApplyAceJob                 # 申请成为王牌职位
│   ├── AceJobStartMatch            # 开始王牌职位匹配
│   ├── HandleJobPriorityChange     # 处理职位优先级变更
│   ├── UpdateJobEvaluateCriteria   # 更新职位评估标准
│   └── BatchGenerateJobEvaluateCriteria  # 批量生成职位评估标准
│
├── JobVector (职位向量)
│   ├── QueryJobVector              # 基于向量库查询
│   ├── QueryVector                 # 向量查询
│   ├── Embedding                   # 职位向量化
│   └── JobAITags                   # AI生成职位标签
│
├── JobForC (C端职位)
│   ├── ForcPreview                 # forC 预览生成
│   └── SyncLovtalentFields         # 同步Lovtalent字段
│
├── JobAgent (职位代理)
│   ├── JobAgentSessionList         # 获取会话列表
│   ├── JobAgentSessionDetail       # 获取会话详情
│   ├── JobAgentSessionChat         # 会话聊天
│   ├── JobAgentSessionChatSse      # 会话聊天（SSE）
│   ├── JobAgentUpdateMessage       # 存储消息
│   ├── JobEvaluation               # 评测接口
│   ├── FetchEvaluationSet          # 获取评测集
│   └── RecordJobAgentResult        # 记录职位agent结果
│
├── Contact (联系人管理)
│   ├── CreateContact               # 创建联系人
│   ├── GetContactDetail            # 获取联系人详情
│   ├── UpdateContact               # 更新联系人信息
│   └── SearchContact               # 搜索联系人
│
├── Note (备注管理)
│   ├── CreateNote                  # 创建备注
│   └── SearchNote                  # 搜索备注
│
├── Tag (标签管理)
│   ├── GetIndustryTags             # 获取行业标签
│   ├── SearchTags                  # 搜索标签
│   └── CreateTag                   # 创建标签
│
├── City (城市管理)
│   ├── SearchCity                  # 搜索城市
│   └── GetHotCities                # 获取热门城市
│
├── Contract (合同管理)
│   └── SearchCompanyContracts      # 搜索客户合同
│
├── GroupChat (飞书群聊)
│   ├── CreateGroupChat             # 创建飞书群聊
│   ├── CreateJobGroupChat          # 创建职位群
│   ├── ListCompanyGroupChats       # 获取客户小麦群列表
│   └── CreateCompanyGroupChat      # 创建客户小麦群
│
├── PreviewData (预览数据)
│   ├── CreatePreviewData           # 创建预览数据
│   └── GetPreviewData              # 获取预览数据
│
├── BatchImport (批量导入)
│   ├── CreateBatchJobImportTable   # 创建批量导入岗位的多维表格
│   └── BatchImportJobsFromTable    # 从飞书多维表格批量导入岗位
│
└── Misc (其他)
    └── CheckFieldsEditable         # 检查字段是否可编辑
```

---

## 快速参考

### Company 客户管理

| 操作 | 方法 | 路径 |
|------|------|------|
| 检查是否可创建 | GET | `/crm/v1/company/create/check` |
| 创建客户 | POST | `/crm/v1/company` |
| 获取客户详情 | GET | `/crm/v1/company/:unique_id` |
| 更新客户信息 | POST | `/crm/v1/company/:unique_id` |
| 搜索客户 | POST | `/crm/v1/company/search` |
| 批量获取客户详情 | POST | `/crm/v1/company/batch` |
| 轻量级更新客户 | POST | `/crm/v1/company/patch` |
| 认领客户 | POST | `/crm/v1/company/claim` |
| 检查客户是否被合并 | GET | `/crm/v1/company/merged` |
| 获取客户掉保日期 | GET | `/crm/v1/company/expiration_date/list` |

### AuthCompany 企业认证

| 操作 | 方法 | 路径 |
|------|------|------|
| 搜索认证企业 | GET | `/crm/v1/company/auth/search` |
| 获取认证企业 | GET | `/crm/v1/company/auth/:id` |

### Job 职位管理

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建职位 | POST | `/crm/v1/job` |
| 获取职位详情 | GET | `/crm/v1/job/:unique_id` |
| 更新职位信息 | POST | `/crm/v1/job/:unique_id` |
| 搜索职位 | POST | `/crm/v1/job/search` |
| 查询职位 | POST | `/crm/v1/job/query` |
| 查询开放公司 | POST | `/crm/v1/job/query-companies` |
| 批量获取职位详情 | POST | `/crm/v1/job/batch` |
| 轻量级更新职位 | POST | `/crm/v1/job/patch` |
| 更新职位状态 | POST | `/crm/v1/job/status` |
| 收藏/取消收藏 | POST | `/crm/v1/job/favorite` |
| 获取客户职位列表 | GET | `/crm/v1/job/list/:company_unique_id` |
| 获取职位画像 | GET | `/crm/v1/job/profile/:unique_id` |

### AceJob 王牌职位

| 操作 | 方法 | 路径 |
|------|------|------|
| 申请成为王牌职位 | POST | `/crm/v1/job/ace/apply` |
| 开始王牌职位匹配 | POST | `/crm/v1/job/ace/start_match` |
| 处理职位优先级变更 | POST | `/crm/v1/job/priority/change` |
| 更新职位评估标准 | POST | `/crm/v1/job/evaluate_criteria` |
| 批量生成评估标准 | POST | `/crm/v1/job/evaluate_criteria/batch/generate` |

### JobForC C端职位

| 操作 | 方法 | 路径 |
|------|------|------|
| forC预览生成 | POST | `/crm/v1/job/forc/preview` |
| 创建职位分享海报 | POST | `/crm/v1/job/:job_id/poster` |

### Contact 联系人

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建联系人 | POST | `/crm/v1/contact` |
| 获取联系人详情 | GET | `/crm/v1/contact/:unique_id` |
| 更新联系人信息 | POST | `/crm/v1/contact/:unique_id` |
| 搜索联系人 | POST | `/crm/v1/contact/search` |

### Note 备注

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建备注 | POST | `/crm/v1/note` |
| 搜索备注 | POST | `/crm/v1/note/search` |

### Tag 标签

| 操作 | 方法 | 路径 |
|------|------|------|
| 获取行业标签 | GET | `/crm/v1/tag/industry` |
| 搜索标签 | GET | `/crm/v1/tag/search` |
| 创建标签 | POST | `/crm/v1/tag` |

### City 城市

| 操作 | 方法 | 路径 |
|------|------|------|
| 搜索城市 | GET | `/crm/v1/city/search` |
| 获取热门城市 | GET | `/crm/v1/city/hot` |

### Contract 合同

| 操作 | 方法 | 路径 |
|------|------|------|
| 搜索客户合同 | POST | `/crm/v1/contract/search` |

### GroupChat 飞书群聊

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建飞书群聊 | POST | `/crm/v1/feishu/group/chat` |
| 创建职位群 | POST | `/crm/v1/job/group/chat` |
| 获取客户小麦群列表 | GET | `/crm/v1/company/group/list/:company_unique_id` |
| 创建客户小麦群 | POST | `/crm/v1/company/group/create` |

### BatchImport 批量导入

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建批量导入表格 | POST | `/crm/v1/feishu/batch_job_import_table` |
| 从表格批量导入岗位 | POST | `/crm/v1/batch_import_jobs` |

---

## 核心枚举速查

### 标签类型 (TagType)

| 值 | 含义 |
|----|------|
| 1 | 公司人工标签 (company_manual) |
| 2 | 公司行业标签 (company_industry) |
| 3 | 岗位人工标签 (job_manual) |
| 4 | 岗位行业标签 (job_industry) |
| 5 | 岗位职称人工标签 (job_title_manual) |
| 6 | 岗位职称标准标签 (job_title_industry) |

### 职位状态 (JobStatus)

| 值 | 含义 |
|----|------|
| 1 | 进展中 (inprogress) |
| 5 | 暂停 (paused) |
| 10 | 成功 (successed) |
| 20 | 取消 (canceled) |

### 资源类型 (ResourceType)

| 值 | 含义 |
|----|------|
| 1 | 公司 (company) |
| 2 | 职位 (job) |
| 3 | 联系人 (contact) |
| 4 | 备注 (note) |

### 职位优先级 (JobPriority)

| 值 | 含义 |
|----|------|
| 1 | 王牌职位 (focus) |

### 客户归属类型 (CompanyBelongType)

| 值 | 含义 |
|----|------|
| 5 | 我的客户 (self) |
| 10 | 公海客户 (public) |
| 15 | 所有客户 (all) |

### 职位需求状态 (JobDemandStatus)

| 值 | 含义 |
|----|------|
| 10 | 新建 (newly) |
| 15 | 开放 (open) |
| 20 | 关闭 (close) |

---

## 相关文档

- [crm-base](./references/crm-base.md) - 基础类型、枚举、数据结构完整定义
- [crm-company](./references/crm-company.md) - 客户管理服务详细 API
- [crm-job](./references/crm-job.md) - 职位管理服务详细 API
- [crm-contact](./references/crm-contact.md) - 联系人管理服务详细 API

---
