---
name: talent-base
description: ttc-crm TalentStore 基础类型定义。包含枚举定义（列表状态/公司类型/关键词类型/报告模板等）、以及人才档案/工作信息/教育信息等核心数据结构。被所有 TalentStore 服务共享使用。
---

# TalentStore Base 基础类型

ttc-crm TalentStore 基础类型定义，包含枚举定义和核心数据结构。

## 概览

| 类型 | 说明 |
|------|------|
| 业务枚举 | CustomizedListStatus, CompanyEnum, KeywordEnum, RecommendationReportTemplate 等 |
| 数据结构 | SearchResponseItem, WorkInformationItem, EducationInformationItem, BasicProfile, RichProfile 等 |

---

## 枚举定义

### 自定义列表状态 (CustomizedListStatus)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | WAITING | 等待中 |
| 2 | SOURCING | Sourcing中 |
| 3 | COMPLETED | 已结束 |

### 公司筛选类型 (CompanyEnum)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | CURRENT | 用户当前在这家公司 |
| 2 | FORMER | 用户曾经在这家公司 |

### 关键词查询类型 (KeywordEnum)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | OR | 或 |
| 2 | AND | 且 |

### 推荐报告模板类型 (RecommendationReportTemplate)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | QUICK | 快速模板 |
| 2 | STANDARD | 标准模板 |

### 推荐报告项样式 (RecommendationReportItemStyle)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | TITLE | 标题 |
| 2 | DATE | 时间 |
| 3 | DESCRIPTION | 内容 |

---

## 数据结构

### Filter 搜索过滤器

| 字段 | 类型 | 说明 |
|------|------|------|
| locations | list&lt;string&gt; | 地区列表 |
| university_category | list&lt;string&gt; | 大学类别 |
| overseas_experience | list&lt;string&gt; | 海外经历 |
| age_range | list&lt;string&gt; | 年龄范围 |
| degree | list&lt;string&gt; | 学历 |
| owner_id | list&lt;string&gt; | 归属人ID |
| has_raw_resume | bool | 是否有原始简历 |
| has_mobile | bool | 是否有手机号 |
| is_merged | bool | 是否已合并 |
| has_system_tag_gulu | bool | 是否有咕噜标签 |
| has_system_tag_ttc | bool | 是否有TTC标签 |
| system_tags | list&lt;string&gt; | 系统标签列表 |
| work_experience_years_range | list&lt;string&gt; | 工作年限范围 |
| sources | list&lt;string&gt; | 来源列表 |

### WorkInformationItem 工作信息

| 字段 | 类型 | 说明 |
|------|------|------|
| duration_in_years | double | 工作年限 |
| company | string | 公司名称 |
| department | string | 部门 |
| job_title | string | 职位 |
| title | string | 职位 |
| start_time | string | 开始时间 |
| end_time | string | 结束时间 |
| company_id | string | 公司ID |
| formatted_company | string | 格式化后的公司名称 |

### EducationInformationItem 教育信息

| 字段 | 类型 | 说明 |
|------|------|------|
| duration_in_years | double | 持续时间（年） |
| school | string | 学校名称 |
| degree | string | 学历 |
| major | string | 专业 |
| start_time | string | 开始时间 |
| end_time | string | 结束时间 |
| school_id | string | 学校ID |
| formatted_school | string | 格式化后的学校名称 |

### SocialPlatformInformation 社交平台信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 平台ID |
| url | string | 平台URL |
| platform | string | 平台名称 |
| last_active_time | i64 | 最后活跃时间（可选） |

### SearchResponseItem 搜索结果项

| 字段 | 类型 | 说明 |
|------|------|------|
| person_leads_id | string | 人选ID |
| cn_name | string | 中文姓名 |
| en_name | string | 英文姓名 |
| age | i64 | 年龄（可选） |
| gender | i32 | 性别 |
| degree | string | 学历 |
| job_title | string | 职位 |
| locations | string | 所在地 |
| tags | list&lt;string&gt; | 标签列表 |
| work_information | list&lt;WorkInformationItem&gt; | 工作信息列表 |
| education_information | list&lt;EducationInformationItem&gt; | 教育信息列表 |
| has_phone | bool | 是否有手机号 |
| has_email | bool | 是否有邮箱 |
| is_merged | bool | 是否已合并 |
| social_information | list&lt;SocialInformationItem&gt; | 社交信息列表 |
| full_text | list&lt;string&gt; | 全文索引 |
| customized_lists | list&lt;CustomizedList&gt; | 自定义列表信息 |
| is_deleted | bool | 是否已删除 |
| system_tags | list&lt;string&gt; | 系统标签 |
| locations_display | string | 显示用地区 |
| first_work_start_time | i64 | 首次工作开始时间戳 |
| university_category | list&lt;string&gt; | 大学类别 |

### CustomizedList 自定义列表信息

| 字段 | 类型 | 说明 |
|------|------|------|
| customized_list_id | string | 列表ID |
| colors | string | 颜色 |
| operator | string | 操作人 |

### BasicProfile 基础档案

| 字段 | 类型 | 说明 |
|------|------|------|
| cn_name | string | 中文姓名 |
| en_name | string | 英文姓名 |
| gender | string | 性别 |
| mobile | list&lt;string&gt; | 手机号列表 |
| email | list&lt;string&gt; | 邮箱列表 |
| date_of_birth | i64 | 出生日期时间戳 |
| locations | list&lt;string&gt; | 所在地列表 |
| locations_display | list&lt;string&gt; | 显示用地区列表 |
| work_information | list&lt;WorkInformation&gt; | 工作信息列表 |
| education_information | list&lt;EducationInformation&gt; | 教育信息列表 |

### RichProfile 富档案

| 字段 | 类型 | 说明 |
|------|------|------|
| expected_work_location | list&lt;string&gt; | 期望工作地点 |
| highest_degree | string | 最高学历 |
| university_category | list&lt;string&gt; | 大学类别 |
| overseas_experience | list&lt;string&gt; | 海外经历 |
| expected_salary_k | list&lt;i64&gt; | 期望薪资（K） |
| work_experience_years | double | 工作年限 |
| professional | list&lt;string&gt; | 专业 |
| position | list&lt;string&gt; | 职位 |
| industry | list&lt;string&gt; | 行业 |
| job_search_status | string | 求职状态 |
| job_interest_level | string | 求职意向等级 |
| availability | string | 到岗时间 |
| preferred_industry | list&lt;string&gt; | 期望行业 |
| preferred_position | list&lt;string&gt; | 期望职位 |
| key_skills | list&lt;string&gt; | 关键技能 |
| language_proficiency | list&lt;string&gt; | 语言能力 |
| published_papers | list&lt;string&gt; | 发表论文 |
| awards | list&lt;string&gt; | 获奖情况 |
| certifications | list&lt;string&gt; | 证书 |
| other_experience_list | list&lt;string&gt; | 其他经历 |
| highest_position_level | string | 最高职级 |
| social_information_maimai | list&lt;SocialInformationMaimai&gt; | 脉脉信息 |
| social_information_wechat | list&lt;SocialInformationWechat&gt; | 微信信息 |
| social_information_boss | list&lt;SocialInformationBoss&gt; | Boss直聘信息 |
| social_information_liepin | list&lt;SocialInformationLiePin&gt; | 猎聘信息 |
| activities | list&lt;Activities&gt; | 活动信息 |

### PersonLeadsEntity 人才实体

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 人选ID |
| owner_user_id | string | 归属人用户ID |
| creator_user_id | string | 创建人用户ID |
| is_merged | bool | 是否已合并 |
| security_level | byte | 安全级别 |
| source | string | 来源 |
| created_at | i64 | 创建时间戳 |
| updated_at | i64 | 更新时间戳 |

### PersonLeadsAttachmentItem 附件项

| 字段 | 类型 | 说明 |
|------|------|------|
| attachment_id | string | 附件ID |
| name | string | 文件名 |
| link | string | 下载链接 |
| preview_url | string | 预览URL |
| source_user_id | string | 来源用户ID |
| source_user_name | string | 来源用户名 |
| source_user_avatar | string | 来源用户头像 |
| source_channel_name | string | 来源渠道名称 |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |
| updated_at_timestamp | i64 | 更新时间戳 |

### OperationLog 操作日志

| 字段 | 类型 | 说明 |
|------|------|------|
| log_id | string | 日志ID |
| operate_date | string | 操作日期 |
| operator_user_union_id | string | 操作人UnionID |
| operator_user_id | string | 操作人用户ID |
| operator_user_name | string | 操作人姓名 |
| operator_user_avatar | string | 操作人头像 |
| operate_type | string | 操作类型 |
| key | string | 键 |
| display_name | string | 显示名称 |
| add_data | string | 新增数据 |
| upload_data | OperationLogUploadData | 上传数据 |
| modify_data | OperationLogModifyData | 修改数据 |
| operate_related_id | string | 操作关联ID |

### User 用户信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 用户唯一ID |
| name | string | 是 | 用户名称 |
| avatar_url | string | 是 | 用户头像 |

---

## 社交平台相关结构

### SocialInformationMaimai 脉脉信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 脉脉ID |
| url | string | 脉脉URL |

### SocialInformationWechat 微信信息

| 字段 | 类型 | 说明 |
|------|------|------|
| open_id | string | OpenID |
| wechat_id | string | 微信号 |
| nickname | string | 昵称 |
| union_id | string | UnionID |
| avatar | string | 头像 |

### SocialInformationBoss Boss直聘信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | Boss直聘ID |

### SocialInformationLiePin 猎聘信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 猎聘ID |

### SocialInformationLinkedin LinkedIn信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | LinkedIn ID |
| url | string | LinkedIn URL |

### Activities 活动信息

| 字段 | 类型 | 说明 |
|------|------|------|
| platform | string | 平台 |
| last_active_time | i64 | 最后活跃时间戳 |

---

## 使用说明

此文件定义了 ttc-crm TalentStore 服务的基础类型，被以下服务共享：

- **talent-search**: 搜索服务
- **talent-person-leads**: 人才管理服务
- **talent-customized-list**: 自定义列表服务
- **talent-recommendation-report**: 推荐报告服务

在调用 API 时，请参考此文档中的枚举值和数据结构定义。
