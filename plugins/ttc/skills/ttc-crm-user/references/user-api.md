---
name: ttc-user-api
description: TTC 内部用户服务 API 详细文档。包含 OAuth 认证、用户查询、人才库用户等接口。
---

# TTC User API

ttc-go-mono/app/user 用户服务 API 详细文档。

---

## OAuth 认证

### OAuth 登录

```
POST /api/user_service/v1/login/oauth
```

**请求体**:

```json
{
  "platform": 4,                    // 必填：ThirdLoginPlatform
  "source": "APP",                  // 选填：来源
  "code": "auth_code",              // 选填：授权码
  "authing_app_id": "app_id"        // 选填：Authing App ID
}
```

**响应 data**:

```json
{
  "access_token": "jwt_token",
  "expire_time": 1706400000,
  "access_token_map": {
    "APP": {
      "access_token": "jwt_token",
      "expire_time": 1706400000
    }
  },
  "auth_action": "login"            // login 或 register
}
```

### Authing 登录

```
POST /api/user_service/v1/login/oauth/authing
```

与 OAuth 登录相同，但 platform 必须为 4 (AUTHING)。

### 获取登录用户

```
GET /api/user_service/v1/login/user
```

需要 JWT 认证。

**响应 data**: LoginUser 对象

---

## 用户查询

### 搜索用户

```
POST /api/user_service/v1/user/search
```

需要 JWT 认证。

**请求体**:

```json
{
  "keyword": "搜索关键词",  // 必填
  "limit": 20,              // 选填
  "offset": 0               // 选填
}
```

**响应 data**:

```json
{
  "users": [User, ...]
}
```

### 获取用户详情（内部）

```
GET /api/user_service/v1/internal/user/:unique_id
```

**响应 data**:

```json
{
  "user": User,
  "user_third_bind": UserThirdBind
}
```

### 获取领导 UnionID 列表（内部）

```
GET /api/user_service/v1/internal/user/leader_union_id_list/:union_id
```

返回指定用户的领导链 UnionID 列表。

### 批量获取用户（内部）

```
POST /api/user_service/v1/internal/user/batch
```

**请求体**:

```json
{
  "unique_ids": ["U123", "U456"]
}
```

**响应 data**:

```json
{
  "user_map": {
    "U123": User,
    "U456": User
  }
}
```

### 按 UnionIDs 批量获取（内部）

```
POST /api/user_service/v1/internal/user/batch/unionids
```

**请求体**:

```json
{
  "union_ids": ["union_id_1", "union_id_2"],
  "third_login_platform": 4         // 必填：ThirdLoginPlatform
}
```

**响应 data**:

```json
{
  "user_map": {
    "union_id_1": User,
    "union_id_2": User
  }
}
```

### 按 TTC UserID 批量获取（内部）

```
POST /api/user_service/v1/internal/user/batch/ttc_user_ids
```

**请求体**:

```json
{
  "ttc_user_ids": ["ttc_001", "ttc_002"],
  "tenant_id": "tenant_001",        // 选填
  "status": 0                       // 选填
}
```

### 按手机号批量获取（内部）

```
POST /api/user_service/v1/internal/user/batch/mobile
```

**请求体**:

```json
{
  "mobiles": ["13800138000"],
  "external": false                 // 选填：是否获取外部用户
}
```

### 批量获取三方绑定（内部）

```
POST /api/user_service/v1/internal/third_binds
```

**请求体**:

```json
{
  "unique_ids": ["U123", "U456"],
  "third_login_platform": 4         // 必填
}
```

**响应 data**:

```json
{
  "user_third_bind_map": {
    "U123": UserThirdBind,
    "U456": UserThirdBind
  }
}
```

---

## 人才库用户

### 创建或获取人才用户（内部）

```
POST /api/user_service/v1/internal/talent_user/createOrGet
```

**请求体**:

```json
{
  "unique_id": "U123456",
  "platform": 4                     // ThirdLoginPlatform
}
```

**响应 data**:

```json
{
  "talent_user_entity": TalentStoreUserEntity
}
```

---

## 飞书事件处理

服务自动处理飞书通讯录事件：

| 事件 | 说明 |
|------|------|
| P2UserCreatedV3 | 员工入职，自动创建用户 |
| P2UserDeletedV3 | 员工离职，更新用户状态 |
| P2UserUpdatedV3 | 员工更新，同步用户信息 |

支持的飞书应用：
- TTC 主应用
- JS 应用
- 菜多对上海应用

---

## 数据结构

### User 完整字段

```go
type User struct {
    ID                int64     // 用户ID
    UniqueID          string    // 用户唯一ID
    Name              string    // 名称
    Email             string    // 邮箱
    Mobile            string    // 手机号
    AvatarURL         string    // 头像URL
    TtcUserID         string    // TTC 用户ID
    ThirdPlatformBind int32     // 三方平台绑定
    Source            string    // 来源
    Status            int32     // 状态
    RealName          string    // 真实姓名
    LeaderTtcID       string    // 领导 TTC ID
    HireTime          time.Time // 入职时间
    ResignationTime   time.Time // 离职时间
    FirstTeamNo       string    // 一级团队编号
    FirstTeamName     string    // 一级团队名称
    SecondTeamNo      string    // 二级团队编号
    SecondTeamName    string    // 二级团队名称
    OpNo              string    // OP 编号
    OpName            string    // OP 名称
    Position          string    // 职位
    PositionLevel     string    // 职级
    PositionType      string    // 职位类型
    Type              string    // 类型
    Location          string    // 位置
    Company           string    // 公司
    Department        string    // 部门
    GuluID            string    // Gulu ID
    External          bool      // 是否外部用户
    CreatedAt         time.Time // 创建时间
    UpdatedAt         time.Time // 更新时间
}
```

### UserThirdBind 完整字段

```go
type UserThirdBind struct {
    ID             int32     // ID
    UserUniqueID   string    // 用户唯一ID
    ThirdPlatform  int32     // 三方平台
    ThirdNickname  string    // 三方昵称
    ThirdOpenID    string    // Open ID
    ThirdUnionID   string    // Union ID
    ThirdTenantID  string    // Tenant ID
    ThirdAvatarURL string    // 三方头像
    ThirdExt       string    // 扩展信息
    TtcUnionID     string    // TTC Union ID
    CreatedAt      time.Time // 创建时间
    UpdatedAt      time.Time // 更新时间
}
```

### TTCUserEntity 完整字段

```go
type TTCUserEntity struct {
    UserOpenID  string          // 用户 Open ID（主键）
    UserUnionID string          // 用户 Union ID
    Name        string          // 用户名
    Mobile      string          // 手机号
    PersonID    string          // 人才库 ID
    Profile     *TTCUserProfile // 用户详情
    InService   string          // 在职状态
    DisplayName string          // 显示名称
}
```

### TalentStoreUserEntity 完整字段

```go
type TalentStoreUserEntity struct {
    ID          string      // 用户ID（主键）
    LarkUnionID string      // 飞书 Union ID
    Name        string      // 名称
    Avatar      string      // 头像
    Phone       string      // 手机号
    ConfigData  *UserConfig // 配置数据
    TTCUnionID  string      // TTC Union ID
    CreatedAt   time.Time   // 创建时间
    UpdatedAt   time.Time   // 更新时间
}
```

---
