---
name: crm-contact
description: ttc-crm CRM 联系人管理服务。包含联系人创建/更新/搜索、备注管理、标签管理、城市搜索、飞书群聊等功能。
---

# CRM Contact 联系人与辅助服务

ttc-crm CRM 联系人管理及辅助服务，提供联系人、备注、标签、城市、群聊相关的 API。

## 概览

| 功能模块 | 说明 |
|----------|------|
| 联系人管理 | 创建、更新、搜索联系人 |
| 备注管理 | 创建、搜索备注 |
| 标签管理 | 获取行业标签、搜索标签、创建标签 |
| 城市管理 | 搜索城市、获取热门城市 |
| 群聊管理 | 飞书群聊、职位群、客户小麦群 |

---

## 联系人管理接口

### 创建联系人

创建新的联系人。

**接口路径：** `POST /crm/v1/contact`

**请求体 (CreateContactRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| contact | Contact | 是 | 联系人信息 |

**Contact 必填字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 联系人姓名 |
| company_unique_id | string | 所属客户ID |

**Contact 可选字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| title | string | 职位 |
| phones | list&lt;string&gt; | 电话号码列表 |
| emails | list&lt;string&gt; | 邮箱列表 |
| wechats | list&lt;string&gt; | 微信号列表 |
| remark | string | 备注 |

**响应数据 (CreateContactData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| contact | Contact | 创建的联系人信息 |

**请求示例：**

```bash
curl -X POST 'https://api.ttcadvisory.com/api/crm/v1/contact' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "contact": {
      "name": "李四",
      "title": "招聘经理",
      "company_unique_id": "CIZEBHS",
      "phones": ["13900139000"],
      "emails": ["lisi@example.com"]
    }
  }'
```

---

### 获取联系人详情

根据唯一ID获取联系人详细信息。

**接口路径：** `GET /crm/v1/contact/:unique_id`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 联系人唯一ID |

**响应数据 (GetContactDetailData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| contact | Contact | 联系人详细信息 |

---

### 更新联系人信息

更新指定联系人的信息。

**接口路径：** `POST /crm/v1/contact/:unique_id`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 联系人唯一ID |

**请求体 (UpdateContactRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| contact | Contact | 是 | 联系人信息（必须包含 unique_id） |

**响应数据 (UpdateContactData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| contact | Contact | 更新后的联系人信息 |

---

### 搜索联系人

根据条件搜索联系人列表。

**接口路径：** `POST /crm/v1/contact/search`

**请求体 (SearchContactRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_unique_id | string | 是 | 公司ID |
| name | string | 否 | 联系人姓名 |
| cursor | i64 | 否 | 分页游标 |
| size | i64 | 否 | 每页大小 |

**响应数据 (SearchContactData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| contacts | list&lt;Contact&gt; | 联系人列表 |
| has_more | bool | 是否有更多数据 |
| cursor | i64 | 下一页游标 |

**请求示例：**

```bash
curl -X POST 'https://api.ttcadvisory.com/api/crm/v1/contact/search' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "company_unique_id": "CIZEBHS",
    "size": 20
  }'
```

---

## 备注管理接口

### 创建备注

创建新的备注。

**接口路径：** `POST /crm/v1/note`

**请求体 (CreateNoteRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| note | Note | 是 | 备注信息 |
| audio_text | string | 否 | 录音文本 |

**Note 必填字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| content | string | 备注内容 |
| company_unique_id | string | 公司ID |

**Note 可选字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| contacts | list&lt;Contact&gt; | 相关联系人 |
| jobs | list&lt;Job&gt; | 相关职位 |

**响应数据 (CreateNoteData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| note | Note | 创建的备注信息 |

**请求示例：**

```bash
curl -X POST 'https://api.ttcadvisory.com/api/crm/v1/note' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "note": {
      "content": "与HR沟通，确认职位需求",
      "company_unique_id": "CIZEBHS"
    }
  }'
```

---

### 搜索备注

根据条件搜索备注列表。

**接口路径：** `POST /crm/v1/note/search`

**请求体 (SearchNoteRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_unique_id | string | 是 | 公司ID |
| cursor | i64 | 否 | 分页游标 |
| size | i64 | 否 | 每页大小 |

**响应数据 (SearchNoteData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| notes | list&lt;Note&gt; | 备注列表 |
| has_more | bool | 是否有更多数据 |
| cursor | i64 | 下一页游标 |

---

## 标签管理接口

### 获取行业标签

获取所有行业标签列表。

**接口路径：** `GET /crm/v1/tag/industry`

**响应数据 (GetIndustryTagsData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| industry_tags | list&lt;Tag&gt; | 行业标签列表 |

---

### 搜索标签

根据条件搜索标签。

**接口路径：** `GET /crm/v1/tag/search`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 标签名称 |
| type | TagType | 是 | 标签类型 |
| cursor | i64 | 否 | 分页游标 |
| size | i64 | 否 | 每页大小 |

**响应数据 (SearchTagsData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| tags | list&lt;Tag&gt; | 标签列表 |
| has_more | bool | 是否有更多数据 |
| cursor | i64 | 下一页游标 |

---

### 创建标签

创建新的标签。

**接口路径：** `POST /crm/v1/tag`

**请求体 (CreateTagRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 标签名称 |
| type | TagType | 是 | 标签类型 |

**响应数据 (CreateTagData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| tag | Tag | 创建的标签信息 |

---

## 城市管理接口

### 搜索城市

根据关键词搜索城市。

**接口路径：** `GET /crm/v1/city/search`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |

**响应数据 (SearchCityData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| cities | list&lt;City&gt; | 城市列表 |

---

### 获取热门城市

获取热门城市列表。

**接口路径：** `GET /crm/v1/city/hot`

**响应数据 (GetHotCitiesData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| hot_cities | list&lt;City&gt; | 热门城市列表 |

---

## 群聊管理接口

### 创建飞书群聊

为客户创建飞书群聊。

**接口路径：** `POST /crm/v1/feishu/group/chat`

**请求体 (CreateGroupChatRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_unique_id | string | 是 | 公司ID |

**响应数据 (CreateGroupChatData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| group_chat_id | string | 群聊ID |
| group_chat_icon | string | 群聊图标 |
| group_share_link | string | 分享链接 |

---

### 创建职位群

为职位创建飞书群聊。

**接口路径：** `POST /crm/v1/job/group/chat`

**请求体 (CreateJobGroupChatRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| job_unique_id | string | 是 | 职位ID |

---

### 获取客户小麦群列表

获取客户关联的小麦群列表。

**接口路径：** `GET /crm/v1/company/group/list/:company_unique_id`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_unique_id | string | 是 | 客户ID |

**响应数据 (ListCompanyGroupChatsData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| group_chats | list&lt;GroupChat&gt; | 小麦群列表 |

---

### 创建客户小麦群

为客户创建小麦群。

**接口路径：** `POST /crm/v1/company/group/create`

**请求体 (CreateCompanyGroupChatRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_unique_id | string | 是 | 客户ID |
| job_unique_ids | list&lt;string&gt; | 是 | 关联的职位列表 |
| name | string | 是 | 群聊名称 |

**响应数据 (CreateCompanyGroupChatData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| group_chat | GroupChat | 小麦群信息 |

---

## 预览数据接口

### 创建预览数据

创建预览数据（用于临时数据存储）。

**接口路径：** `POST /crm/v1/preview_data`

**请求体 (CreatePreviewDataRequest)：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| preview_data | PreviewData | 是 | 预览数据 |

---

### 获取预览数据

根据 key 获取预览数据。

**接口路径：** `GET /crm/v1/preview_data/:key`

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| key | string | 是 | 预览数据键 |

**响应数据 (GetPreviewDataData)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| preview_data | PreviewData | 预览数据 |

---

## 使用说明

### 联系人管理最佳实践

1. 创建客户时会同时创建首个联系人
2. 后续可通过 `CreateContact` 添加更多联系人
3. 联系人必须关联到客户（company_unique_id）

### 备注管理

1. 备注可关联联系人和职位
2. 支持录音转文本（audio_text 字段）
3. 备注按时间倒序排列

### 标签类型说明

| 类型值 | 说明 | 使用场景 |
|--------|------|----------|
| 1 | 公司人工标签 | 用户自定义的公司标签 |
| 2 | 公司行业标签 | 系统预设的行业分类 |
| 3 | 岗位人工标签 | 用户自定义的岗位标签 |
| 4 | 岗位行业标签 | 系统预设的岗位行业分类 |
| 5 | 岗位职称人工标签 | 用户自定义的职称标签 |
| 6 | 岗位职称标准标签 | 系统预设的标准职称 |
