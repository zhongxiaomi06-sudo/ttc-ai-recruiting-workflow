---
name: talent-recommendation-report
description: ttc-crm TalentStore 推荐报告服务，包含报告列表/详情/保存/下载、简历解析、内容格式化等功能。用于生成和管理人才推荐报告。
---

# TalentStore RecommendationReport 推荐报告服务

ttc-crm TalentStore 推荐报告服务，提供人才推荐报告的生成、管理和下载功能。

## 服务概览

| 功能 | 说明 |
|------|------|
| 报告管理 | 获取报告列表、详情、保存、下载 |
| 简历解析 | 解析简历生成报告内容、重新解析指定内容 |
| 内容格式化 | 格式化报告内容 |
| 操作日志 | 获取报告操作日志 |

---

## 报告管理

### 1. 获取推荐报告列表
- **POST** `/talent_store/v1/recommendation_report/list`

**请求体:**
```json
{
  "person_leads_id": "人选ID"            // 必填
}
```

**响应 data:**
```json
{
  "recommendation_reports": [
    {
      "id": "报告ID",
      "person_leads_id": "人选ID",
      "report_name": "推荐报告_张三_20240115",
      "client": "客户名称",
      "attachment_id": "附件ID",
      "creator": "创建人ID",
      "created_at": "2024-01-15 10:30:00",
      "creator_avatar": "头像URL",
      "updated_at": "2024-01-15 10:30:00",
      "creator_name": "李四",
      "bind_pipeline": true,
      "editable": true,
      "client_id": "客户ID",
      "client_name": "XX公司",
      "project_name": "后端工程师招聘",
      "brief_profile": {
        "company_name": "字节跳动",
        "title": "高级工程师",
        "age": "28",
        "gender": "男",
        "degree": "本科",
        "location": "北京",
        "recommendation": "优秀候选人",
        "name": "张三"
      },
      "project_id": "项目ID",
      "pipeline_id": "流程ID",
      "download_url": "下载链接"
    }
  ],
  "total": 10
}
```

### 2. 通过外部实体获取报告
- **POST** `/talent_store/v1/recommendation_report/get_by_external_entity`

**请求体:**
```json
{
  "external_entity_id": "外部实体ID",
  "external_entity_type": "pipeline",
  "source": "crm"
}
```

### 3. 获取报告详情
- **POST** `/talent_store/v1/recommendation_report/get`

**请求体:**
```json
{
  "report_id": "报告ID",                  // 必填
  "source": "crm"
}
```

**响应 data:**
```json
{
  "person_leads_id": "人选ID",
  "report_id": "报告ID",
  "attachment_id": "附件ID",
  "recommented_project_id": "推荐项目ID",
  "with_attachment": true,
  "report_style": "standard",
  "report_detail": {
    "report_name": "推荐报告_张三",
    "modules": [
      {
        "module_name": "基本信息",
        "module_type": "basic_info",
        "module_id": 1,
        "sections": [
          {
            "section_name": "个人信息",
            "section_type": "personal",
            "section_id": 1,
            "items": [
              {
                "item_name": "姓名",
                "item_content": "张三",
                "item_type": "text",
                "item_id": 1,
                "item_style": "title"
              }
            ]
          }
        ]
      }
    ],
    "report_template": 2                  // 1=快速, 2=标准
  },
  "source": "crm",
  "download_url": "下载链接",
  "external_entity_id": "外部实体ID",
  "external_entity_type": "pipeline",
  "project_id": "项目ID",
  "client_id": "客户ID",
  "client_name": "客户名称",
  "project_name": "项目名称",
  "brief_profile": { /* 简要档案 */ },
  "report_name": "报告名称",
  "creator": "创建人ID",
  "created_at": "2024-01-15 10:30:00",
  "creator_avatar": "头像URL",
  "updated_at": "2024-01-15 10:30:00",
  "creator_name": "李四",
  "recommendation_raw_content": "原始推荐内容",
  "report_details": [/* 多个报告详情 */]
}
```

### 4. 保存推荐报告
- **POST** `/talent_store/v1/recommendation_report/save`

**请求体:**
```json
{
  "person_leads_id": "人选ID",            // 必填
  "report_id": "报告ID",                  // 更新时必填
  "attachment_id": "附件ID",
  "recommented_project_id": "推荐项目ID",
  "recommented_project_remark": "推荐备注",
  "with_attachment": true,
  "report_style": "standard",
  "report_detail": {
    "report_name": "推荐报告_张三",
    "modules": [/* 报告模块 */],
    "report_template": 2
  },
  "external_entity_id": "外部实体ID",
  "external_entity_type": "pipeline",
  "recommendation_report_html": "报告HTML内容",
  "source": "crm",
  "project_id": "项目ID",
  "recommendation_raw_content": "原始推荐内容",
  "report_details": [/* 多个报告详情 */],
  "masked_recommendation_report_html": "脱敏后的HTML"
}
```

**响应 data:**
```json
{
  "report_id": "报告ID",
  "source": "crm"
}
```

### 5. 保存推荐报告V2
- **POST** `/talent_store/v1/recommendation_report/save_v2`

> 与 save 接口参数相同，V2版本增强功能

### 6. 下载推荐报告
- **POST** `/talent_store/v1/recommendation_report/download`

**请求体:**
```json
{
  "recommendation_report_html": "报告HTML内容",
  "attachment_id": "附件ID",
  "filename": "推荐报告_张三.pdf",        // 必填
  "with_attachment": true,
  "masked": false,                        // 是否脱敏
  "report_id": "报告ID"
}
```

**响应 data:**
```json
{
  "download_url": "下载链接"
}
```

---

## 简历解析

### 1. 解析简历
- **GET** `/talent_store/v1/recommendation_report/parse_resume`

**查询参数:**
- `attachment_id`: 附件ID
- `person_leads_id`: 人选ID（必填）
- `language`: 语言（cn/en）

**响应 data:**
```json
{
  "recommendation_report_detail": {
    "report_name": "推荐报告",
    "modules": [
      {
        "module_name": "基本信息",
        "module_type": "basic_info",
        "module_id": 1,
        "sections": [
          {
            "section_name": "个人信息",
            "section_type": "personal",
            "section_id": 1,
            "items": [
              {
                "item_name": "姓名",
                "item_content": "张三",
                "item_type": "text",
                "item_id": 1,
                "item_style": "title"
              }
            ]
          }
        ]
      },
      {
        "module_name": "工作经历",
        "module_type": "work_experience",
        "module_id": 2,
        "sections": [/* 工作经历内容 */]
      },
      {
        "module_name": "教育背景",
        "module_type": "education",
        "module_id": 3,
        "sections": [/* 教育背景内容 */]
      }
    ],
    "report_template": 2
  }
}
```

### 2. 重新解析简历指定内容
- **GET** `/talent_store/v1/recommendation_report/reparse_resume_specified_content`

**查询参数:**
- `attachment_id`: 附件ID
- `module_name`: 模块名称（必填）
- `suggestion`: 重新解析建议（必填）
- `language`: 语言
- `pipeline_id`: 流程ID
- `person_leads_id`: 人选ID

**响应 data:**
```json
{
  "content": "重新解析后的内容"
}
```

### 3. 流式重新解析简历指定内容
- **GET** `/talent_store/v1/recommendation_report/stream_reparse_resume_specified_content`

> 参数同上，返回流式响应

---

## 内容格式化

### 格式化内容
- **POST** `/talent_store/v1/recommendation_report/format_content`

**请求体:**
```json
{
  "content": "需要格式化的内容"           // 必填
}
```

**响应 data:**
```json
{
  "content": "格式化后的内容"
}
```

---

## 操作日志

### 获取报告操作日志
- **POST** `/talent_store/v1/recommendation_report/get_operation_logs`

**请求体:**
```json
{
  "report_id": "报告ID",
  "pipeline_id": "流程ID"
}
```

**响应 data:**
```json
{
  "operation_logs": [
    {
      "id": "日志ID",
      "report_id": "报告ID",
      "report_name": "报告名称",
      "operation_type": "create",
      "operation_time": "2024-01-15 10:30:00",
      "operation_user_id": "操作人ID",
      "operation_source": "crm"
    }
  ]
}
```

---

## 报告结构

### RecommendationReportDetail 报告详情

```json
{
  "report_name": "推荐报告_张三",
  "modules": [
    {
      "module_name": "基本信息",
      "module_type": "basic_info",
      "module_id": 1,
      "sections": [
        {
          "section_name": "个人信息",
          "section_type": "personal",
          "section_id": 1,
          "items": [
            {
              "item_name": "姓名",
              "item_content": "张三",
              "item_type": "text",
              "item_id": 1,
              "item_style": "title"        // title/date/description
            }
          ]
        }
      ]
    }
  ],
  "report_template": 2                      // 1=快速, 2=标准
}
```

### RecommendationReportBriefProfile 简要档案

```json
{
  "company_name": "字节跳动",
  "title": "高级工程师",
  "age": "28",
  "gender": "男",
  "degree": "本科",
  "location": "北京",
  "recommendation": "该候选人技术能力强...",
  "name": "张三"
}
```

---

## 枚举

### 报告模板类型 (RecommendationReportTemplate)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | QUICK | 快速模板 |
| 2 | STANDARD | 标准模板 |

### 报告项样式 (RecommendationReportItemStyle)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | TITLE | 标题 |
| 2 | DATE | 时间 |
| 3 | DESCRIPTION | 内容 |

---

## 使用场景

### 1. 创建新的推荐报告
```json
// 1. 解析简历获取基础信息
GET /talent_store/v1/recommendation_report/parse_resume?person_leads_id=xxx&language=cn

// 2. 保存报告
POST /talent_store/v1/recommendation_report/save
{
  "person_leads_id": "xxx",
  "report_detail": { /* 解析结果 */ },
  "with_attachment": true
}
```

### 2. 下载带附件的报告
```json
POST /talent_store/v1/recommendation_report/download
{
  "report_id": "报告ID",
  "filename": "推荐报告_张三.pdf",
  "with_attachment": true,
  "masked": false
}
```

### 3. 重新解析某个模块
```json
GET /talent_store/v1/recommendation_report/reparse_resume_specified_content
  ?attachment_id=xxx
  &module_name=工作经历
  &suggestion=请更详细地描述项目经验
  &language=cn
```
