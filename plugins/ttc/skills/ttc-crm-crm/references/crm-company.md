---
name: crm-company
description: ttc-crm CRM 客户管理服务。包含客户创建/更新/搜索、企业认证、客户合并检测、批量获取等功能。
---

# CRM Company 客户管理服务

ttc-crm CRM 客户管理服务，提供客户（公司）相关的完整 API。

## 概览

| 功能模块 | 说明 |
|----------|------|
| 客户管理 | 创建、更新、搜索、批量获取客户 |
| 企业认证 | 搜索和获取认证企业信息 |
| 客户认领 | 认领公海客户 |
| 合并检测 | 检查客户是否被合并 |
| 掉保管理 | 获取即将掉保的客户 |

---

## 客户管理接口

### 检查是否可以创建公司

检查指定公司名是否可以创建。

**接口路径：** `GET /crm/v1/company/create/check`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 公司名称 |

**响应数据 (CheckCreateCompanyData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| can_create | bool | 是否可以创建 |

**请求示例：**

```bash
curl -X GET 'https://api-int.ttcadvisory.com/api/crm/v1/company/create/check?name=腾讯科技' \
  -H 'Authorization: Bearer <token>'
```

---

### 创建公司

创建新的客户（公司）信息。

**接口路径：** `POST /crm/v1/company`

**请求体 (CreateCompanyRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company | Company | 是 | 公司信息 |
| contact | Contact | 是 | 联系人信息 |

**响应数据 (CreateCompanyData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| company | Company | 创建的公司信息 |
| contact | Contact | 创建的联系人信息 |

**请求示例：**

```bash
curl -X POST 'https://api-int.ttcadvisory.com/api/crm/v1/company' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "company": {
      "name": "腾讯科技有限公司",
      "cities": ["深圳"],
      "manager": {
        "unique_id": "ou_xxxxxxxxxxxxxxxx"
      }
    },
    "contact": {
      "name": "张三",
      "title": "HR总监",
      "phones": ["13800138000"]
    }
  }'
```

> **说明：** `manager.unique_id` 使用飞书用户的 open_id 或 union_id 格式（如 `ou_xxxxxxxxxxxxxxxx`）

---

### 获取公司详情

根据唯一ID获取公司详细信息。

**接口路径：** `GET /crm/v1/company/:unique_id`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 公司唯一ID |

**响应数据 (GetCompanyDetailData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| company | Company | 公司详细信息 |

**请求示例：**

```bash
# 线上环境
curl -X GET 'https://api.ttcadvisory.com/api/crm/v1/company/CIZEBHS' \
  -H 'Authorization: Bearer <token>'

# 测试环境
curl -X GET 'https://api-int.ttcadvisory.com/api/crm/v1/company/CIZEBHS' \
  -H 'Authorization: Bearer <token>'
```

---

### 更新公司信息

更新指定公司的信息。

**接口路径：** `POST /crm/v1/company/:unique_id`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 公司唯一ID |

**请求体 (UpdateCompanyRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company | Company | 是 | 公司信息 |

**响应数据 (UpdateCompanyData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| company | Company | 更新后的公司信息 |

---

### 搜索公司

根据条件搜索公司列表。

**接口路径：** `POST /crm/v1/company/search`

**请求体 (SearchCompanyRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| belong_type | CompanyBelongType | 否 | 归属类型（5=我的，10=公海，15=所有） |
| industry_tag_id | i64 | 否 | 行业标签ID |
| active_levels | list&lt;string&gt; | 否 | 活跃度（"活跃"、"交付中"） |
| job_demand_status | list&lt;JobDemandStatus&gt; | 否 | 职位需求状态 |
| keyword | string | 否 | 关键词搜索 |
| cursor | i64 | 否 | 分页游标 |
| size | i64 | 否 | 每页大小 |
| manager_id | string | 否 | 客户经理ID |
| is_ordered | bool | 否 | 是否成单 |

**响应数据 (SearchCompanyData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| companies | list&lt;Company&gt; | 公司列表 |
| has_more | bool | 是否有更多数据 |
| cursor | i64 | 下一页游标 |

**请求示例：**

```bash
# 搜索我的客户
curl -X POST 'https://api.ttcadvisory.com/api/crm/v1/company/search' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "belong_type": 5,
    "keyword": "腾讯",
    "size": 20
  }'

# 搜索公海客户
curl -X POST 'https://api.ttcadvisory.com/api/crm/v1/company/search' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "belong_type": 10,
    "size": 20
  }'
```

---

### 批量获取公司详情

批量获取多个公司的详细信息。

**接口路径：** `POST /crm/v1/company/batch`

**请求体 (BatchGetCompanyDetailRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_ids | list&lt;string&gt; | 是 | 公司ID列表 |

**响应数据 (BatchGetCompanyDetailData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| companies | list&lt;Company&gt; | 公司列表 |

---

### 轻量级更新公司字段

轻量级更新公司的特定字段（用于系统间调用，无权限验证）。

**接口路径：** `POST /crm/v1/company/patch`

**请求体 (PatchCompanyRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 公司ID |
| customer_archive_doc_link | string | 否 | AI生成的客户档案文档链接 |
| operator | string | 否 | 操作人 |
| source | string | 否 | 操作来源 |

---

### 认领客户

认领公海客户。

**接口路径：** `POST /crm/v1/company/claim`

**请求体 (ClaimCompanyRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_unique_id | string | 是 | 客户ID |

---

### 检查客户是否被合并

检查客户是否已被合并到其他客户。

**接口路径：** `GET /crm/v1/company/merged`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 客户ID |

**响应数据 (CheckCompanyMergedData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| is_merged | bool | 是否被合并 |
| merged_company_unique_id | string | 合并后的客户ID |

---

### 获取客户掉保日期

获取即将掉保的客户列表。

**接口路径：** `GET /crm/v1/company/expiration_date/list`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| days | i32 | 是 | 天数范围 |

**响应数据 (ListCompanyExpirationDateData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| companies | list&lt;Company&gt; | 即将掉保的客户列表 |
| has_company | bool | 是否有客户 |

---

## 企业认证接口

### 搜索认证企业

根据关键词搜索认证企业。

**接口路径：** `GET /crm/v1/company/auth/search`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |

**响应数据 (SearchAuthCompanyData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| companies | list&lt;AuthCompanyInfo&gt; | 认证企业列表 |

---

### 获取认证企业

根据ID获取认证企业详情。

**接口路径：** `GET /crm/v1/company/auth/:id`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 认证企业ID |

**响应数据 (GetAuthCompanyData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| company | AuthCompanyInfo | 认证企业信息 |

---

## 合同接口

### 搜索客户合同

搜索指定客户的合同列表。

**接口路径：** `POST /crm/v1/contract/search`

**请求体 (SearchCompanyContractsRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_unique_id | string | 是 | 客户ID |

**响应数据 (SearchCompanyContractsData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| contracts | list&lt;Contract&gt; | 合同列表 |

---

## 字段编辑权限检查

### 检查字段是否可编辑

检查当前用户是否有权限编辑指定资源的字段。

**接口路径：** `GET /crm/v1/fields/editable/check`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| resource_type | ResourceType | 是 | 资源类型 |
| unique_id | string | 是 | 资源唯一ID |

**响应数据 (CheckFieldsEditableData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| editable | bool | 是否可编辑 |

---

## 使用说明

### 创建客户流程

1. 调用 `CheckCreateCompany` 检查公司名是否可以创建
2. 如果可以创建，调用 `CreateCompany` 创建客户和首个联系人
3. 创建后可继续添加更多联系人、备注等

### 客户搜索技巧

- 使用 `belong_type` 筛选我的客户/公海客户
- 使用 `active_levels` 筛选活跃状态
- 使用 `job_demand_status` 筛选职位需求状态
- 支持 `keyword` 关键词模糊搜索

### 客户合并处理

当客户被合并时：
1. 调用 `CheckCompanyMerged` 检查客户是否被合并
2. 如果被合并，使用返回的 `merged_company_unique_id` 获取新客户信息
