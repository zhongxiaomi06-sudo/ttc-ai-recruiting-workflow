---
name: talent-person-leads
description: ttc-crm TalentStore 人才管理服务，包含人才创建/更新、档案管理、附件管理、评论管理、人才关系、外部事件、用户配置等功能。
---

# TalentStore PersonLeads 人才管理服务

ttc-crm TalentStore 人才管理服务，提供完整的人才档案管理功能。

## 服务概览

| 服务 | 功能 |
|------|------|
| PersonLeadsService | 创建/更新人才、拨打电话、操作日志、人才关系、事件处理 |
| PersonLeadsProfileService | 档案获取/更新、基础信息、详细信息、发布档案 |
| PersonLeadsAttachmentService | 附件列表、附件详情、文件上传 |
| PersonLeadsCommentsService | 创建评论、编辑评论、事件通知 |
| ExternalEventService | 创建外部事件 |
| UserConfigService | 用户配置、可见性 |
| ObjectUniqService | 学校/公司归一化搜索 |
| TimeBasedProfileService | 时间线档案 |

---

## PersonLeadsService 人才服务

### 1. 创建人才
- **POST** `/talent_store/v1/person_leads/create`

**请求体:**
```json
{
  "profile": {
    "cn_name": "张三",
    "mobile": "13800138000",
    "email": "zhangsan@example.com"
  },
  "attachment_id": "简历附件ID",
  "source": "manual",                    // 来源：manual/import/api
  "security_level": 1                     // 安全级别
}
```

**响应 data:**
```json
{
  "person_leads_id": "新创建的人选ID",
  "is_processing": true,                  // 是否正在处理中
  "attachment_id": "附件ID"
}
```

### 2. 更新人才
- **POST** `/talent_store/v1/person_leads/update`

**请求体:**
```json
{
  "person_leads_id": "人选ID",            // 必填
  "profile": {
    "cn_name": "张三",
    "job_title": "高级工程师"
  },
  "attachment_id": "新简历附件ID",
  "source": "manual",
  "security_level": 1,
  "uniq_id": "唯一标识"
}
```

**响应 data:**
```json
{
  "person_leads_id": "人选ID",
  "is_processing": true
}
```

### 3. 拨打电话
- **POST** `/talent_store/v1/person_leads/make_call`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "phone": "13800138000"
}
```

### 4. 获取操作日志列表
- **POST** `/talent_store/v1/person_leads/operation_logs/list`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "only_comments": false,                 // 是否只显示评论
  "current_page": 1,
  "page_size": 20
}
```

**响应 data:**
```json
{
  "operation_log_items": [
    {
      "log_id": "日志ID",
      "operate_date": "2024-01-15 10:30:00",
      "operator_user_id": "操作人ID",
      "operator_user_name": "李四",
      "operator_user_avatar": "头像URL",
      "operate_type": "update_profile",
      "key": "job_title",
      "display_name": "职位",
      "modify_data": {
        "old_data": "工程师",
        "new_data": "高级工程师"
      }
    }
  ],
  "total_count": 50
}
```

### 5. 获取人才关系
- **POST** `/talent_store/v1/person_leads/relation/single_scope`

**请求体:**
```json
{
  "person_leads_id": "人选ID"
}
```

**响应 data:**
```json
{
  "root_person_leads_id": "根人选ID",
  "neighbor_or_children_person_leads_ids": ["关联人选ID1", "关联人选ID2"],
  "children_person_leads_info": [/* 子人选信息列表 */]
}
```

### 6. 批量获取人才关系
- **POST** `/talent_store/v1/person_leads/relation/single_scope/mget`

**请求体:**
```json
{
  "person_leads_ids": ["人选ID1", "人选ID2"]
}
```

**响应 data:**
```json
{
  "root_person_leads_ids": {
    "人选ID1": "根人选ID1",
    "人选ID2": "根人选ID2"
  }
}
```

### 7. 重新解析档案
- **POST** `/talent_store/v1/person_leads/profile/reparse_from_attachment`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "attachment_id": "附件ID"
}
```

### 8. 事件处理通知
- **GET** `/talent_store/v1/person_leads/profile/event_processing_notice`

**查询参数:**
- `person_leads_id`: 人选ID
- `wait_for_merge`: 是否等待合并

### 9. 获取事件Job状态
- **POST** `/talent_store/v1/person_leads/job_status`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "event_job_id": "事件JobID"
}
```

**响应 data:**
```json
{
  "is_processing": true,
  "current_status": "parsing",
  "job_start_at": "2024-01-15 10:30:00"
}
```

### 10. 获取引流信息
- **GET** `/talent_store/v1/person_leads/invite_info`

**查询参数:**
- `person_leads_id`: 人选ID

**响应 data:**
```json
{
  "root_person_leads_id": "根人选ID",
  "owner_user_id": "归属人ID",
  "invite_user": {
    "unique_id": "用户ID",
    "name": "邀请人姓名",
    "avatar_url": "头像URL"
  },
  "invite_user_add_time": "2024-01-15 10:30:00"
}
```

### 11. 公开人才
- **POST** `/talent_store/v1/person_leads/public`

**请求体:**
```json
{
  "person_leads_id": "人选ID"
}
```

---

## PersonLeadsProfileService 档案服务

### 1. 获取档案详情
- **POST** `/talent_store/v1/person_leads/profile/get`

**请求体:**
```json
{
  "person_leads_id": "人选ID"
}
```

**响应 data:**
```json
{
  "profile_detail": {
    "cn_name": "张三",
    "en_name": "Zhang San",
    "mobile": "13800138000",
    "email": "zhangsan@example.com",
    // ... 其他档案字段
  }
}
```

### 2. 更新档案 (Profile形式)
- **POST** `/talent_store/v1/person_leads/profile/update`

**请求体:**
```json
{
  "person_leads": {
    "id": "人选ID",
    "owner_user_id": "归属人ID",
    "security_level": 1,
    "source": "manual"
  },
  "person_leads_profile": {
    "cn_name": "张三",
    "job_title": "高级工程师"
  },
  "event_operate_id": "事件操作ID",
  "uniq_id": "唯一标识",
  "overwrite": false
}
```

### 3. 更新档案 (KV形式)
- **POST** `/talent_store/v1/person_leads/profile_update`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "person_leads_profile": {
    "cn_name": "张三",
    "job_title": "高级工程师"
  },
  "source": "manual"
}
```

### 4. 计算档案
- **POST** `/talent_store/v1/person_leads/profile/calculate`

**请求体:**
```json
{
  "key": "work_experience_years",
  "contexts": [
    {
      "value": "某个值",
      "operate_type": "calculate"
    }
  ]
}
```

### 5. 获取基础信息
- **POST** `/talent_store/v1/person_leads/basic_info`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "refresh": false                        // 是否刷新缓存
}
```

**响应 data:**
```json
{
  "cn_name": "张三",
  "en_name": "Zhang San",
  "tags": ["Go", "微服务"],
  "age": 28,
  "date_of_birth": "1996-05-15",
  "gender": 1,
  "degree": "本科",
  "job_title": "高级工程师",
  "locations": ["北京"],
  "phone": ["13800138000"],
  "email": ["zhangsan@example.com"],
  "experience": [
    {
      "experience_key": "work",
      "experience_display_name": "字节跳动 高级工程师",
      "color_code": "#4CAF50",
      "reason": "3年工作经验"
    }
  ],
  "personal_highlights": "技术专家，擅长分布式系统",
  "gulu_info": {
    "has_gulu_id": true,
    "gulu_id": "gulu_123",
    "url": "https://gulu.com/profile/123"
  },
  "customized_list_ids": ["list1", "list2"],
  "is_merged": false,
  "parent_person_leads_id": "",
  "is_processing": false,
  "activities": [
    {
      "platform": "maimai",
      "last_active_time": 1705300000000
    }
  ],
  "social_information": [/* 社交信息 */],
  "source": "manual",
  "system_tags": ["gulu"]
}
```

### 6. 获取详细信息
- **POST** `/talent_store/v1/person_leads/detail_info`

**请求体:**
```json
{
  "person_leads_id": "人选ID"
}
```

**响应 data:**
```json
{
  "company_tags": ["大厂", "互联网"],
  "school_tags": ["985", "211"],
  "work_information": [
    {
      "start_time": "2020-01",
      "end_time": "至今",
      "company": "字节跳动",
      "department": "技术部",
      "responsibility": "负责后端架构设计",
      "title": "高级工程师",
      "key": "work_1",
      "duration_years": 4.0,
      "company_id": "company_123",
      "formatted_company": "北京字节跳动科技有限公司"
    }
  ],
  "education_information": [
    {
      "start_time": "2012-09",
      "end_time": "2016-06",
      "school": "北京大学",
      "degree": "本科",
      "major": "计算机科学与技术",
      "key": "edu_1",
      "duration_years": 4.0,
      "school_id": "school_123",
      "formatted_school": "北京大学"
    }
  ]
}
```

### 7. 发布档案
- **POST** `/talent_store/v1/person_leads/profile/publish`

**请求体:**
```json
{
  "person_leads_ids": ["人选ID1", "人选ID2"]
}
```

**响应 data:**
```json
{
  "result": {
    "人选ID1": true,
    "人选ID2": false
  }
}
```

### 8. 获取创建人
- **POST** `/talent_store/v1/person_leads/creator_info`

**请求体:**
```json
{
  "person_leads_id": "人选ID"
}
```

**响应 data:**
```json
{
  "creator_user_id": "创建人用户ID",
  "source": "manual"
}
```

---

## PersonLeadsAttachmentService 附件服务

### 1. 获取附件列表
- **POST** `/talent_store/v1/person_leads/resume/attachment/list`

**请求体:**
```json
{
  "person_leads_id": "人选ID"
}
```

**响应 data:**
```json
{
  "attachment_items": [
    {
      "attachment_id": "附件ID",
      "name": "简历_张三.pdf",
      "link": "下载链接",
      "preview_url": "预览URL",
      "source_user_id": "上传用户ID",
      "source_user_name": "上传用户名",
      "source_user_avatar": "头像URL",
      "source_channel_name": "上传渠道",
      "created_at": "2024-01-15 10:30:00",
      "updated_at": "2024-01-15 10:30:00",
      "updated_at_timestamp": 1705300200000
    }
  ]
}
```

### 2. 获取附件详情
- **POST** `/talent_store/v1/person_leads/resume/attachment/get_by_id`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "attachment_id": "附件ID"
}
```

**响应:** 返回 PersonLeadsAttachmentItem 结构

### 3. 上传文件
- **POST** `/talent_store/v1/file/upload`
- **Content-Type:** multipart/form-data

**表单字段:**
- `file`: 文件内容

**响应 data:**
```json
{
  "attachment_id": "新附件ID"
}
```

---

## PersonLeadsCommentsService 评论服务

### 1. 创建评论
- **POST** `/talent_store/v1/person_leads/comments/create`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "attachment_id": "附件ID",            // 选填
  "content": "评论内容",
  "is_public": true,                     // 是否公开
  "source": "manual",
  "source_type": "manual",               // manual/ai_phone/xiaomai_group
  "forwarder_union_id": "转发人UnionID"  // 选填
}
```

**响应 data:**
```json
{
  "person_leads_comments_id": "评论ID",
  "person_leads_event_operate_log_id": "操作日志ID"
}
```

### 2. 编辑评论
- **POST** `/talent_store/v1/person_leads/comments/edit`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "person_leads_comments_id": "评论ID",
  "content": "修改后的评论内容",
  "source": "manual",
  "source_type": "manual",
  "forwarder_union_id": "转发人UnionID"
}
```

**响应 data:**
```json
{
  "operation_log": { /* 操作日志 */ }
}
```

### 3. 评论事件通知
- **GET** `/talent_store/v1/person_leads/comments/event_processing_notice`

**查询参数:**
- `person_leads_id`: 人选ID

### 4. 创建txt解析备注
- **POST** `/talent_store/v1/person_leads/comments/create_txt`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "attachment_id": "txt附件ID",
  "source": "manual"
}
```

---

## ExternalEventService 外部事件服务

### 创建外部事件
- **POST** `/talent_store/v1/person_leads/external_event/create_by_user`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "external_platform": "maimai",
  "event_type": "profile_update",
  "event_data": {}
}
```

---

## UserConfigService 用户配置服务

### 1. 更新用户配置
- **POST** `/talent_store/v1/user/config`

**请求体:**
```json
{
  "user_id": "用户ID",
  "visible_tabs": ["search", "my_talents", "customized_list"]
}
```

### 2. 获取用户可见性
- **GET** `/talent_store/v1/user/visibility`

**响应 data:**
```json
{
  "visible_tabs": ["search", "my_talents", "customized_list"],
  "person_leads_default_tab": "basic_info"
}
```

---

## ObjectUniqService 归一化服务

### 1. 学校归一化搜索
- **POST** `/talent_store/v1/object-uniq/search-school`

**请求体:**
```json
{
  "school_name": "北京大学"
}
```

**响应 data:**
```json
{
  "school_id": "school_123",
  "school_name": "北京大学",
  "score": 0.98,
  "is_good": true
}
```

### 2. 公司归一化搜索
- **POST** `/talent_store/v1/object-uniq/search-company`

**请求体:**
```json
{
  "company_name": "字节跳动"
}
```

**响应 data:**
```json
{
  "company_id": "company_123",
  "company_name": "北京字节跳动科技有限公司",
  "score": 0.95,
  "is_good": true
}
```

---

## TimeBasedProfileService 时间线档案服务

### 1. 获取时间线档案详情
- **GET** `/talent_store/v1/time_based/profile_detail`

**查询参数:**
- `person_leads_id`: 人选ID

**响应 data:**
```json
{
  "items": {
    "job_title": [
      {
        "key": "job_title",
        "content": "高级工程师",
        "reason": "简历解析",
        "source": "resume_parse",
        "source_created_at": "2024-01-15 10:30:00"
      }
    ]
  }
}
```

### 2. 保存新来源
- **POST** `/talent_store/v1/time_based/save_new_source`

**请求体:**
```json
{
  "person_leads_id": "人选ID",
  "source_id": "来源ID",
  "source_type": "ai_phone",
  "source_created_at": "2024-01-15 10:30:00",
  "content": "内容",
  "user_id": "用户ID"
}
```
