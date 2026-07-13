---
name: talent-search
description: ttc-crm TalentStore 搜索服务，包含人才搜索、AI搜索、智能列表、搜索历史等功能。用于在人才库中进行各种条件的人才检索和匹配。
---

# TalentStore Search 搜索服务

ttc-crm TalentStore 搜索服务，提供人才搜索、AI智能搜索、智能列表等功能。

## 服务概览

| 服务 | 功能 |
|------|------|
| SearchService | 人才搜索、AI搜索、原始查询、过滤条件、搜索历史、人才匹配 |
| SmartListService | 智能列表获取、智能列表详情 |

---

## SearchService 搜索服务

### 1. 搜索人才
- **POST** `/talent_store/v1/search`

**请求体:**
```json
{
  "keyword": "关键词",
  "key_words": ["关键词1", "关键词2"],
  "filter": {
    "locations": ["北京", "上海"],
    "degree": ["本科", "硕士"],
    "age_range": ["25-30"],
    "has_mobile": true,
    "system_tags": ["标签1"]
  },
  "current_page": 1,
  "page_size": 20,
  "search_id": "搜索ID",
  "names": ["姓名1"],
  "companies": ["公司1"],
  "titles": ["职位1"],
  "company_type": 1,                    // 1=当前公司, 2=曾经公司
  "keyword_type": 1,                    // 1=OR, 2=AND
  "allow_incomplete_profile": false     // 是否允许缺少 basic/rich profile
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
      "work_information": [/* 工作信息列表 */],
      "education_information": [/* 教育信息列表 */],
      "has_phone": true,
      "has_email": true,
      "is_merged": false,
      "is_deleted": false,
      "system_tags": ["gulu"]
    }
  ],
  "total_count": 100,
  "search_id": "搜索ID"
}
```

### 2. Lovtalent专用搜索
- **POST** `/talent_store/v1/search-for-lovtalent`

> 与 Search 接口参数相同，针对 Lovtalent 场景优化

### 3. 获取搜索过滤条件
- **GET** `/talent_store/v1/search/filters`

**响应 data:**
```json
{
  "locations": ["北京", "上海", "广州"],
  "degrees": ["本科", "硕士", "博士"],
  "age_ranges": ["20-25", "25-30", "30-35"],
  // ... 其他过滤条件
}
```

### 4. 获取搜索历史
- **POST** `/talent_store/v1/search/history/list`

**请求体:**
```json
{
  "current_page": 1,
  "page_size": 10
}
```

**响应 data:**
```json
{
  "history_items": [
    {
      "keywords": ["Python", "后端"],
      "date": "2024-01-15"
    }
  ],
  "total_count": 50
}
```

### 5. 人才匹配
- **POST** `/talent_store/v1/person_leads/match`

**请求体:**
```json
{
  "name": "张三",
  "work": [
    {
      "company": "字节跳动",
      "position": "高级工程师",
      "work_start_time": "2020-01",
      "work_end_time": "2023-06"
    }
  ],
  "edu": [
    {
      "school": "北京大学",
      "major": "计算机科学",
      "degree": "本科",
      "edu_start_time": "2012-09",
      "edu_end_time": "2016-06"
    }
  ],
  "from": 0,
  "size": 10
}
```

**响应 data:**
```json
{
  "items": [
    {
      "id": "匹配的人选ID",
      "score": 95.5,
      "fields": { /* PersonLeadsProfileMessageBodyForES */ }
    }
  ],
  "total": 5
}
```

### 6. 原始查询搜索
- **POST** `/talent_store/v1/search_raw`

**请求体:**
```json
{
  "query": {
    "company": ["字节跳动", "阿里巴巴"],
    "title": ["工程师"]
  },
  "limit": 20,
  "offset": 0,
  "simple_response": false,
  "with_query_or": true,
  "ignore_person_leads_ids": ["id1", "id2"],
  "scores": {
    "company": 10,
    "title": 5
  },
  "not_match": {
    "company": ["腾讯"]
  },
  "without_fulltext": false,
  "allow_incomplete_profile": false
}
```

**响应 data:**
```json
{
  "person_leads_items": [/* 搜索结果列表 */],
  "total_count": 100,
  "miss_match_keys": ["未匹配的键"],
  "not_support_not_match_keys": ["不支持排除的键"]
}
```

### 7. 获取原始查询键列表
- **POST** `/talent_store/v1/search_raw_keys`

**响应 data:**
```json
{
  "keys": ["company", "title", "school", "degree", ...]
}
```

### 8. 获取原始查询键详情
- **POST** `/talent_store/v1/search_raw_keys_detail/get`

**响应 data:**
```json
{
  "key_detail": {
    "company": "公司名称，支持模糊匹配",
    "title": "职位名称",
    // ...
  }
}
```

### 9. 设置原始查询键详情
- **POST** `/talent_store/v1/search_raw_keys_detail/set`

**请求体:**
```json
{
  "key_detail": {
    "company": "公司名称说明",
    "title": "职位名称说明"
  },
  "use_function_score": true
}
```

### 10. AI智能搜索
- **POST** `/talent_store/v1/ai_search`

**请求体:**
```json
{
  "msg": "找一个有5年Go开发经验的后端工程师，最好有大厂背景",
  "ignore_person_leads_ids": ["id1", "id2"],
  "recommend_talents_num": 10,          // 推荐人才数量
  "batch_num": 5,                        // 批次数量
  "max_loop_num": 3,                     // 最大循环次数
  "match_score_threshold": 60,           // 匹配分数阈值
  "version": 1
}
```

**响应 data:**
```json
{
  "items": {
    "batch_1": [
      {
        "person_leads_id": "人选ID",
        "name": "张三",
        "title": "高级后端工程师",
        "company": ["字节跳动"],
        "degree": "本科",
        "school": ["北京大学"],
        "phone": ["138****1234"],
        "attachment_ids": ["附件ID"],
        "match_score": 85,
        "recommendation": "该候选人有6年Go开发经验，曾在字节跳动担任技术负责人..."
      }
    ]
  }
}
```

### 11. 获取系统标签列表
- **GET** `/talent_store/v1/system_tags`

**查询参数:**
- `tag_type`: 标签类型

**响应 data:**
```json
{
  "tags": ["gulu", "ttc", "vip", ...]
}
```

---

## SmartListService 智能列表服务

### 1. 获取智能列表
- **GET** `/talent_store/v1/search/smart_list/list`

**响应 data:**
```json
{
  "smart_list_items": [
    {
      "key": "recent_updated",
      "display_name": "最近更新",
      "color_code": "#FF5722",
      "enable": true,
      "total_count": 1500
    },
    {
      "key": "my_talents",
      "display_name": "我的人才",
      "color_code": "#2196F3",
      "enable": true,
      "total_count": 200
    }
  ]
}
```

### 2. 获取智能列表详情
- **POST** `/talent_store/v1/search/smart_list/info`

**请求体:**
```json
{
  "key": "recent_updated",
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
  "person_leads_items": [/* 搜索结果列表 */],
  "total_count": 1500
}
```

---

## Filter 过滤器结构

```json
{
  "locations": ["北京", "上海"],           // 地区列表
  "university_category": ["985", "211"],   // 大学类别
  "overseas_experience": ["有"],            // 海外经历
  "age_range": ["25-30", "30-35"],         // 年龄范围
  "degree": ["本科", "硕士"],               // 学历
  "owner_id": ["user_id_1"],               // 归属人ID
  "has_raw_resume": true,                   // 是否有原始简历
  "has_mobile": true,                       // 是否有手机号
  "is_merged": false,                       // 是否已合并
  "has_system_tag_gulu": true,             // 是否有咕噜标签
  "has_system_tag_ttc": false,             // 是否有TTC标签
  "system_tags": ["gulu", "vip"],          // 系统标签列表
  "work_experience_years_range": ["3-5", "5-10"],  // 工作年限范围
  "sources": ["maimai", "linkedin"]        // 来源列表
}
```

---

## 搜索技巧

### 1. 使用关键词组合搜索
```json
{
  "key_words": ["Python", "后端", "微服务"],
  "keyword_type": 2  // AND - 同时包含所有关键词
}
```

### 2. 按公司类型筛选
```json
{
  "companies": ["字节跳动"],
  "company_type": 1  // 1=当前在职, 2=曾经任职
}
```

### 3. AI智能搜索自然语言
```json
{
  "msg": "找一个有大厂背景的资深前端工程师，熟悉React和Vue",
  "match_score_threshold": 70
}
```

### 4. 原始查询精确匹配
```json
{
  "query": {
    "company": ["阿里巴巴"],
    "title": ["P7", "P8"]
  },
  "not_match": {
    "company": ["外包"]
  }
}
```
