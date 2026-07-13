---
name: crm-base
description: ttc-crm CRM 基础类型定义。包含枚举定义（标签类型/职位状态/资源类型/客户归属等）、以及公司/职位/联系人/合同等核心数据结构。被所有 CRM 服务共享使用。
---

# CRM Base 基础类型

ttc-crm CRM 基础类型定义，包含枚举定义和核心数据结构。

## 概览

| 类型 | 说明 |
|------|------|
| 业务枚举 | TagType, JobStatus, ResourceType, JobPriority, CompanyBelongType, JobDemandStatus 等 |
| 数据结构 | Company, Job, Contact, Note, Tag, Contract, User, GroupChat 等 |

---

## 枚举定义

### 标签类型 (TagType)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | company_manual | 公司人工标签 |
| 2 | company_industry | 公司行业标签 |
| 3 | job_manual | 岗位人工标签 |
| 4 | job_industry | 岗位行业标签 |
| 5 | job_title_manual | 岗位职称人工标签 |
| 6 | job_title_industry | 岗位职称标准标签 |

### 职位状态 (JobStatus)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | inprogress | 进展中 |
| 5 | paused | 暂停 |
| 10 | successed | 成功 |
| 20 | canceled | 取消 |

### 资源类型 (ResourceType)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | company | 公司 |
| 2 | job | 职位 |
| 3 | contact | 联系人 |
| 4 | note | 备注 |

### 职位优先级 (JobPriority)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 1 | focus | 王牌职位 |

### 客户归属类型 (CompanyBelongType)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 5 | self | 属于当前查询人（我的客户） |
| 10 | public | 公海客户（没有客户经理） |
| 15 | all | 所有客户（我的 + 公海客户） |

### 职位需求状态 (JobDemandStatus)

| 值 | 常量名 | 含义 |
|----|--------|------|
| 10 | newly | 新建 |
| 15 | open | 开放 |
| 20 | close | 关闭 |

---

## 数据结构

### Response 基础响应

| 字段 | 类型 | 说明 |
|------|------|------|
| code | i32 | 响应码 |
| msg | string | 响应消息 |
| data | binary | JSON 格式数据（可选） |

### User 用户信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 是 | 用户唯一ID |
| name | string | 否 | 用户名称 |
| avatar_url | string | 否 | 用户头像 |

### Tag 标签信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | i64 | 否 | 标签ID（创建时不需要） |
| name | string | 是 | 标签名称 |
| type | TagType | 是 | 标签类型 |
| category | string | 否 | 标签分类 |

### City 城市信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | i64 | 城市ID |
| name | string | 城市名称 |
| en_name | string | 英文名称 |

### AuthCompanyInfo 企业认证信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| useful_id | string | 是 | 有用ID |
| reg_no | string | 是 | 注册号 |
| location | string | 是 | 位置 |
| operator_name | string | 否 | 操作者名称 |
| operator_time | string | 否 | 操作时间 |
| auth_name | string | 是 | 认证名称 |
| company_unique_id | string | 否 | 客户唯一ID |

### Company 公司信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unique_id | string | 否 | 唯一ID（创建时不需要） |
| name | string | 是 | 公司名称 |
| auth_company_info | AuthCompanyInfo | 否 | 认证信息 |
| cities | list&lt;string&gt; | 否 | 城市列表 |
| industry_tags | list&lt;Tag&gt; | 否 | 行业标签 |
| manual_tags | list&lt;Tag&gt; | 否 | 人工标签 |
| provider | User | 否 | 提供者 |
| manager | User | 是 | 管理者（客户经理） |
| collaborators | list&lt;User&gt; | 否 | 协作人 |
| reg_no | string | 否 | 企业统一信用码 |

**返回时附加字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| doc_link | string | 文档链接 |
| group_chat_id | string | 分组ID |
| group_chat_icon | string | 分组图标 |
| collaboration_share | string | 协作分享 |
| contract_status | string | 签约状态 |
| create_time | i64 | 创建时间 |
| creator | User | 创建者 |
| job_demand_status | JobDemandStatus | 职位需求状态 |
| inprocess_job_count | i64 | 进行中的职位数量 |
| active_level | string | 活跃度 |
| last_activity_time | i64 | 最后活跃时间 |
| ka | i32 | 大客户标识 |
| group_share_link | string | 分享链接 |
| gulu_id | string | 谷露ID |
| is_ordered | bool | 是否成单 |
| expiration_date | string | 掉保日期 |
| expiration_days | i32 | 掉保天数 |
| name_for_c | string | C端公司名称 |
| customer_archive_doc_link | string | AI生成的客户档案文档链接 |

### Job 职位信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 职位名称 |
| cities | list&lt;string&gt; | 是 | 城市列表 |
| head_count | i64 | 是 | 招聘人数 |
| analytics | string | 是 | 职位描述（人选画像） |
| description | string | 否 | JD详情 |
| salary | string | 否 | 薪资 |
| industry_tags | list&lt;Tag&gt; | 否 | 行业标签 |
| manual_tags | list&lt;Tag&gt; | 否 | 人工标签 |
| contacts | list&lt;Contact&gt; | 否 | 联系人列表 |
| provider | User | 是 | 提供者 |
| managers | list&lt;User&gt; | 是 | 管理者 |
| participants | list&lt;User&gt; | 否 | 参与者 |
| expect_amount | i64 | 否 | 预计收费 |
| secrecy | string | 否 | 保密信息 |
| cooperation | string | 否 | 合作方式 |
| company_unique_id | string | 是 | 公司ID |
| status | JobStatus | 是 | 职位状态 |
| group_chat_id | string | 否 | 群聊ID |
| group_chat_icon | string | 否 | 群聊图标 |
| company_name | string | 否 | 公司名称 |
| evaluate_criteria | string | 否 | AI生成的评价维度 |

**返回时附加字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| unique_id | string | 职位唯一ID |
| creator | User | 创建者 |
| create_time | i64 | 创建时间 |
| has_permission | bool | 是否有权限 |
| status_tags | list&lt;string&gt; | 职位状态标签 |
| update_time | i64 | 更新时间 |
| group_share_link | string | 分享链接 |
| gulu_id | string | 谷露ID |
| is_favorited | bool | 是否收藏 |
| group_chat | GroupChat | 小麦群信息 |
| pipeline_info | PipelineInfo | 交付系统数据 |
| priority | i32 | 业务优先级 |
| ace_job_status | i32 | 王牌职位状态 |
| name_for_c | string | C端职位名称 |
| company_name_for_c | string | C端公司名称 |
| qualification_for_c | string | C端职位要求 |
| description_for_c | string | C端JD |
| tags_for_c | list&lt;string&gt; | C端标签 |
| company_profile | string | 公司简介 |
| is_lovtalent | bool | 是否是lovtalent职位 |
| is_non_headhunter | bool | 是否为非猎头职位 |
| need_blur | bool | 预览是否脱敏 |
| format_analytics | string | 王牌岗位格式的人选画像 |

### Contact 联系人信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 联系人姓名 |
| title | string | 否 | 职位 |
| phones | list&lt;string&gt; | 否 | 电话号码列表 |
| emails | list&lt;string&gt; | 否 | 邮箱列表 |
| wechats | list&lt;string&gt; | 否 | 微信号列表 |
| remark | string | 否 | 备注 |
| company_unique_id | string | 否 | 客户ID（创建时可不填） |

**返回时附加字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| unique_id | string | 唯一ID |
| creator | User | 创建者 |
| create_time | i64 | 创建时间 |

### Note 备注信息

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 是 | 备注内容 |
| contacts | list&lt;Contact&gt; | 否 | 相关联系人 |
| jobs | list&lt;Job&gt; | 否 | 相关职位 |
| company_unique_id | string | 是 | 公司ID |

**返回时附加字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | i64 | 备注ID |
| creator | User | 创建者 |
| create_time | i64 | 创建时间 |

### Contract 合同信息

| 字段 | 类型 | 说明 |
|------|------|------|
| contract_name | string | 合同名称 |
| contract_number | string | 合同编号 |
| contract_status | string | 合同状态 |
| signer | User | 签约人 |
| start_time | string | 合同生效时间 |
| end_time | string | 合同结束时间 |
| counter_party_name | string | 对方主体名称 |
| contract_category_name | string | 合同类别名称 |
| contract_description | string | 合同说明 |
| preserved | string | 是否禁猎 |
| creator_name | string | 创建人 |
| created_at | string | 创建时间 |
| report_url | string | 报表URL |
| file_name | string | 文件名称 |
| file_id | string | 文件ID |
| company_unique_id | string | 客户ID |
| download_url | string | 下载URL |
| has_permission | bool | 是否有下载权限 |
| fee_rate | string | 费率 |
| guarantee_period | string | 保证期 |
| base_salary | string | 年薪基数 |
| refund_amount | string | 退款 |
| compensation | string | 赔偿 |
| tax | string | 含税 |
| min_fee | string | 最低收费 |
| first_payment | string | 首付款比例 |
| payment_cycle | string | 付款周期 |

### GroupChat 群聊信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 群聊ID |
| name | string | 群聊名称 |
| icon | string | 群聊图标 |
| share_link | string | 群聊分享链接 |
| creator | User | 创建者 |
| created_at | i64 | 创建时间 |
| job_unique_ids | list&lt;string&gt; | 关联的职位ID列表 |

### PipelineInfo 交付系统数据

| 字段 | 类型 | 说明 |
|------|------|------|
| pipeline_step_count | map&lt;string, i32&gt; | 各阶段候选人数量 |
| total_pipeline_count | i32 | 总候选人数量 |

### PreviewData 预览数据

| 字段 | 类型 | 说明 |
|------|------|------|
| value | string | 预览值 |
| resource_type | ResourceType | 资源类型 |
| id | i64 | ID |
| key | string | 键 |
| created_at | i64 | 创建时间 |
| updated_at | i64 | 更新时间 |

---

## 使用说明

此文件定义了 ttc-crm CRM 服务的基础类型，被以下服务共享：

- **crm-company**: 客户管理服务
- **crm-job**: 职位管理服务
- **crm-contact**: 联系人管理服务

在调用 API 时，请参考此文档中的枚举值和数据结构定义。
