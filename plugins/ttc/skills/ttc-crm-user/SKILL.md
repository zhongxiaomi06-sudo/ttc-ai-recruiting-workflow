---
name: ttc-crm-user
description: TTC 内部用户服务（ttc-go-mono/app/user）。管理 TTC 内部员工信息，包含飞书通讯录同步、员工查询、ID 映射、人才库用户等功能。
---

# TTC User 内部用户服务

ttc-go-mono/app/user 项目提供 TTC 内部员工用户管理服务。

> **注意**：本服务与 lovtalent 用户服务不同，主要面向 TTC 内部员工而非外部求职者。

## 服务概览

| 功能 | 说明 |
|------|------|
| 飞书同步 | 通讯录事件（入职/离职/更新）自动同步 |
| 员工查询 | 批量获取、搜索 |
| 人才库 | 人才库用户管理 |
| OAuth | 内部员工登录认证 |

---

## 相关文档

- [user-api](references/user-api.md) - 用户服务 API 详细文档

## 服务架构

```
TTC User Service
├── OAuth 认证
│   ├── OAuth 登录
│   └── Authing 登录
│
├── 用户查询
│   ├── 获取登录用户
│   ├── 获取用户详情
│   ├── 搜索用户
│   └── 批量获取用户
│
├── 人才库用户
│   └── 创建或获取
│
└── 飞书事件
    ├── 员工入职
    ├── 员工离职
    └── 员工更新
```

---

## 通用响应格式

```json
{
  "code": 0,           // 0=成功
  "msg": "success",
  "data": {}           // 业务数据
}
```

---

## API 速查

### OAuth 认证（外部路由）

| 操作 | 方法 | 路径 |
|------|------|------|
| OAuth 登录 | POST | `/api/user_service/v1/login/oauth` |
| Authing 登录 | POST | `/api/user_service/v1/login/oauth/authing` |
| 获取登录用户 | GET | `/api/user_service/v1/login/user` |

### 用户查询（外部路由，需 JWT）

| 操作 | 方法 | 路径 |
|------|------|------|
| 搜索用户 | POST | `/api/user_service/v1/user/search` |

### 用户查询（内部路由）

| 操作 | 方法 | 路径 |
|------|------|------|
| 获取用户详情 | GET | `/api/user_service/v1/internal/user/:unique_id` |
| 获取领导 UnionID 列表 | GET | `/api/user_service/v1/internal/user/leader_union_id_list/:union_id` |
| 批量获取用户 | POST | `/api/user_service/v1/internal/user/batch` |
| 按 UnionIDs 批量获取 | POST | `/api/user_service/v1/internal/user/batch/unionids` |
| 按 TTC UserID 批量获取 | POST | `/api/user_service/v1/internal/user/batch/ttc_user_ids` |
| 按手机号批量获取 | POST | `/api/user_service/v1/internal/user/batch/mobile` |
| 批量获取三方绑定 | POST | `/api/user_service/v1/internal/third_binds` |
| 搜索用户 | POST | `/api/user_service/v1/internal/user/search` |

### 人才库用户（内部路由）

| 操作 | 方法 | 路径 |
|------|------|------|
| 创建或获取人才用户 | POST | `/api/user_service/v1/internal/talent_user/createOrGet` |

---

## 核心数据结构

### User 用户

| 字段 | 类型 | 说明 |
|------|------|------|
| id | i64 | 用户ID |
| unique_id | string | 用户唯一ID |
| name | string | 名称 |
| email | string | 邮箱 |
| mobile | string | 手机号 |
| avatar_url | string | 头像URL |
| ttc_user_id | string | TTC 用户ID |
| real_name | string | 真实姓名 |
| position | string | 职位 |
| position_level | string | 职级 |
| department | string | 部门 |
| company | string | 公司 |
| location | string | 位置 |
| first_team_name | string | 一级团队 |
| second_team_name | string | 二级团队 |
| leader_ttc_id | string | 领导 TTC ID |
| hire_time | time | 入职时间 |
| resignation_time | time | 离职时间 |
| external | bool | 是否外部用户 |
| status | i32 | 状态 |

### UserThirdBind 三方绑定

| 字段 | 类型 | 说明 |
|------|------|------|
| id | i32 | ID |
| user_unique_id | string | 用户唯一ID |
| third_platform | i32 | 三方平台 |
| third_open_id | string | Open ID |
| third_union_id | string | Union ID |
| third_tenant_id | string | Tenant ID |
| ttc_union_id | string | TTC Union ID |

### TalentStoreUserEntity 人才库用户

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 用户ID |
| lark_union_id | string | 飞书 Union ID |
| name | string | 名称 |
| avatar | string | 头像 |
| phone | string | 手机号 |
| ttc_union_id | string | TTC Union ID |

---

## 第三方登录平台

| 值 | 说明 |
|----|------|
| 2 | 微信小程序 |
| 3 | 微信PC网页 |
| 4 | Authing |
| 20 | 微信开放平台 |

---
