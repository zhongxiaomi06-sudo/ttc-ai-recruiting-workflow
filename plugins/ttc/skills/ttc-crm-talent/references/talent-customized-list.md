---
name: talent-customized-list
description: ttc-crm TalentStore 自定义列表服务，包含名单管理、候选人操作、协作者管理、列表状态等功能。用于灵活管理人才分组和项目跟进。
---

# TalentStore CustomizedList 自定义列表服务

ttc-crm TalentStore 自定义列表服务，提供灵活的人才分组和项目跟进功能。

## 服务概览

| 功能 | 说明 |
|------|------|
| 名单管理 | 创建、更新、删除、移动、搜索名单 |
| 候选人操作 | 添加/移除候选人、修改状态、更新颜色、替换候选人 |
| 协作者管理 | 申请成为协作者、查看参与者 |
| 列表状态 | 状态通知、修改名单状态 |
| AI搜索 | 在名单内进行AI智能搜索 |

---

## 名单管理

### 1. 获取我的名单
- **POST** `/talent_store/v1/customized_list/get`

**请求体:**
```json
{
  "list_name": "名单名称过滤",          // 选填
  "parent_list_id": "父名单ID"          // 选填：获取子名单
}
```

**响应 data:**
```json
{
  "current_user_id": "当前用户ID",
  "person_leads_customized_lists": [
    {
      "key": "list_123",
      "display_name": "高端人才库",
      "color_code": "#4CAF50",
      "total_count": 150,
      "role": "owner",                   // owner/participant
      "status": 2,                       // 1=等待中, 2=Sourcing中, 3=已结束
      "status_name": "Sourcing中",
      "has_sub_list": true,
      "sub_lists": [/* 子名单列表 */],
      "previous_list_id": "前一个名单ID"
    }
  ]
}
```

### 2. 创建名单
- **POST** `/talent_store/v1/customized_list/create`

**请求体:**
```json
{
  "display_name": "新名单名称",
  "color_code": "#FF5722",
  "parent_list_id": "父名单ID",          // 选填：创建子名单
  "previous_list_id": "前一个名单ID"     // 选填：排序位置
}
```

**响应 data:**
```json
{
  "person_leads_customized_list_id": "新名单ID"
}
```

### 3. 更新名单
- **POST** `/talent_store/v1/customized_list/update`

**请求体:**
```json
{
  "person_leads_customized_list_id": "名单ID",
  "display_name": "修改后的名称",
  "color_code": "#2196F3"
}
```

**响应 data:**
```json
{
  "person_leads_customized_list_id": "名单ID"
}
```

### 4. 删除名单
- **POST** `/talent_store/v1/customized_list/remove`

**请求体:**
```json
{
  "person_leads_customized_list_id": "名单ID"
}
```

**响应 data:**
```json
{
  "person_leads_customized_list_id": "删除的名单ID"
}
```

### 5. 移动名单
- **POST** `/talent_store/v1/customized_list/move`

**请求体:**
```json
{
  "customized_list_id": "名单ID",        // 必填
  "parent_list_id": "新父名单ID",        // 移动到新的父级
  "previous_list_id": "前一个名单ID"     // 排序位置
}
```

### 6. 搜索名单
- **GET** `/talent_store/v1/customized_list/search`

**查询参数:**
- `keyword`: 搜索关键词

**响应 data:**
```json
{
  "person_leads_customized_lists": [/* 名单列表 */]
}
```

### 7. 获取列表详情
- **POST** `/talent_store/v1/customized_list/info`

**请求体:**
```json
{
  "key": "名单ID",
  "colors": "颜色过滤",                   // 选填
  "filter": {
    "locations": ["北京"],
    "degree": ["本科"]
  },
  "current_page": 1,
  "page_size": 20
}
```

**响应 data:**
```json
{
  "person_leads_items": [
    {
      "person_leads_id": "人选ID",
      "cn_name": "张三",
      "en_name": "Zhang San",
      "age": 28,
      "gender": 1,
      "degree": "本科",
      "job_title": "高级工程师",
      "locations": "北京",
      "tags": ["Go", "微服务"],
      "work_information": [/* 工作信息 */],
      "education_information": [/* 教育信息 */],
      "has_phone": true,
      "has_email": true,
      "is_merged": false,
      "social_information": [/* 社交信息 */],
      "colors": "green",
      "operator": {
        "unique_id": "操作人ID",
        "name": "李四",
        "avatar_url": "头像URL"
      },
      "is_deleted": false
    }
  ],
  "total_count": 150,
  "participants": [
    {
      "user_id": "用户ID",
      "name": "李四",
      "avatar": "头像URL",
      "is_owner": true,
      "role": "owner"
    }
  ],
  "status": 2,
  "status_name": "Sourcing中"
}
```

---

## 候选人操作

### 1. 切换候选人在名单中的状态
- **POST** `/talent_store/v1/customized_list/action`

**请求体:**
```json
{
  "person_leads_ids": ["人选ID1", "人选ID2"],
  "customized_list_ids": ["名单ID1", "名单ID2"],
  "action": "add"                         // "add" 或 "remove"
}
```

### 2. 修改候选人在名单中的状态
- **POST** `/talent_store/v1/customized_list/modify_person_leads_in_list`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "customized_list_ids": ["名单ID1", "名单ID2"]  // 候选人应该在哪些名单中
}
```

### 3. 更新候选人颜色
- **POST** `/talent_store/v1/customized_list/update_colors`

**请求体:**
```json
{
  "customized_list_id": "名单ID",
  "person_leads_id": "人选ID",
  "colors": "green"                       // 颜色值
}
```

### 4. 替换名单中的候选人
- **POST** `/talent_store/v1/customized_list/replace_person_leads`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "replace_by_parent": true,              // 是否用父级人选替换
  "customized_list_id": "名单ID"
}
```

**响应 data:**
```json
{
  "parent_in_customized_list": true       // 父级人选是否已在名单中
}
```

---

## 协作者管理

### 申请成为协作者
- **POST** `/talent_store/v1/customized_list/apply_to_participant`

**请求体:**
```json
{
  "person_leads_customized_list_id": "名单ID",
  "share_user_union_id": "分享人的UnionID"
}
```

---

## 列表状态

### 1. 名单状态通知 (SSE)
- **GET** `/talent_store/v1/customized_list/status`

> 服务器发送事件 (Server-Sent Events)，实时推送名单状态变更

**响应事件:**
```json
{
  "customized_list_id": "名单ID",
  "status": 2,
  "status_name": "Sourcing中"
}
```

### 2. 修改名单状态
- **POST** `/talent_store/v1/customized_list/update_status`

**请求体:**
```json
{
  "customized_list_id": "名单ID",
  "status": 3                             // 1=等待中, 2=Sourcing中, 3=已结束
}
```

**响应 data:**
```json
{
  "customized_list_id": "名单ID"
}
```

---

## AI搜索

### 在名单内AI搜索
- **POST** `/talent_store/v1/customized_list/ai_search`

**请求体:**
```json
{
  "customized_list_id": "名单ID",
  "job_description": "找一个有5年Go开发经验的后端工程师",
  "only_match": false,                    // 是否只返回匹配结果
  "match_score_threshold": 60,            // 匹配分数阈值
  "max_loop_num": 3                       // 最大循环次数
}
```

**响应 data:**
```json
{
  "results": [
    {
      "person_leads_id": "人选ID",
      "cn_name": "张三",
      "evaluation": {
        "match_score": 85,
        "recommendation": "该候选人有6年Go开发经验，曾在字节跳动担任技术负责人...",
        "is_match": true
      }
    }
  ]
}
```

---

## 名单状态枚举

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | WAITING | 等待中 |
| 2 | SOURCING | Sourcing中 |
| 3 | COMPLETED | 已结束 |

---

## 使用场景

### 1. 创建项目名单并添加候选人
```json
// 1. 创建名单
POST /talent_store/v1/customized_list/create
{
  "display_name": "XX项目-高端人才",
  "color_code": "#4CAF50"
}

// 2. 添加候选人
POST /talent_store/v1/customized_list/action
{
  "person_leads_ids": ["人选ID1", "人选ID2"],
  "customized_list_ids": ["新名单ID"],
  "action": "add"
}
```

### 2. 在名单中进行AI筛选
```json
POST /talent_store/v1/customized_list/ai_search
{
  "customized_list_id": "名单ID",
  "job_description": "寻找有大厂背景的资深后端工程师，熟悉微服务架构",
  "match_score_threshold": 70
}
```

### 3. 为候选人设置标记颜色
```json
POST /talent_store/v1/customized_list/update_colors
{
  "customized_list_id": "名单ID",
  "person_leads_id": "人选ID",
  "colors": "green"  // 已面试
}
```

### 4. 更新项目状态
```json
POST /talent_store/v1/customized_list/update_status
{
  "customized_list_id": "名单ID",
  "status": 3  // 项目完成
}
```
