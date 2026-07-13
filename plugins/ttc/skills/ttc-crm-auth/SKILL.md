---
name: ttc-crm-auth
description: 飞书统一授权登录接入。通过 ottin-web 提供的授权页面，让其他 Web 应用快速接入飞书登录，获取 token。
---

# 飞书统一授权登录

通过 ottin-web 提供的统一授权页面，让其他 Web 应用快速接入飞书登录。

---

## 概述

基于弹窗授权的统一登录方案：应用通过 popup 打开 ottin-web 的授权页面，用户完成飞书登录后，token 通过 `postMessage` 传回原应用。

### 优势

- **零配置**：新应用不需要在飞书开放平台配置回调地址
- **复用登录态**：如果用户在 ottin-web 已登录，直接授权即可
- **简单接入**：只需复制一个 SDK 文件，几行代码即可完成接入

---

## 流程图

```
┌────────────────────────────────────────────────────────────────┐
│ 其他应用                                                        │
│                                                                │
│  1. 调用 Auth.login() 打开 popup                                │
│     ↓                                                          │
│  ottin-web/auth/authorize?callback_url=xxx                     │
│     ↓                                                          │
│  2. 授权页面检查登录状态                                          │
│     - 已登录 → 显示确认页或直接授权 (auto=1)                       │
│     - 未登录 → 跳转飞书 OAuth                                     │
│     ↓                                                          │
│  3. postMessage 传回 token                                      │
│     ↓                                                          │
│  4. 应用收到 token，存储并使用                                    │
└────────────────────────────────────────────────────────────────┘
```

---

## 快速接入

### 1. 复制 SDK 文件

将 SDK 文件复制到项目中：

**源文件位置**: `ottin-web/src/sdk/feishu-auth.ts`

### 2. 修改配置

修改 SDK 中的 `AUTH_URL` 为实际的授权页面地址：

```typescript
// 生产环境
const AUTH_URL = "https://app.ttcadvisory.com/auth/authorize";

// 测试环境
const AUTH_URL = "https://int.ttcadvisory.com/auth/authorize";
```

### 3. 使用 SDK

```typescript
import { Auth } from './feishu-auth';

// 检查登录状态，未登录则弹窗授权
async function ensureLogin() {
  if (!Auth.isLoggedIn()) {
    const success = await Auth.login({ autoConfirm: true });
    if (!success) {
      console.log('用户取消登录');
      return false;
    }
  }
  return true;
}

// 获取 token
const token = Auth.getToken();

// 配置 axios（自动添加 token，401 自动触发登录）
Auth.setupAxios(axios);
```

---

## API 参考

### Auth.isLoggedIn(): boolean

检查是否已登录（token 存在且未过期）。

### Auth.getToken(): string | null

获取当前的 token，未登录返回 null。

### Auth.login(options?): Promise<boolean>

弹窗登录，返回是否登录成功。

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| autoConfirm | boolean | false | 是否跳过确认页面 |
| width | number | 500 | popup 窗口宽度 |
| height | number | 600 | popup 窗口高度 |

### Auth.logout(): void

清除 token，登出。

### Auth.setupAxios(axios, options?): void

配置 axios 实例，自动添加 Authorization header，401 时自动触发登录。

**参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| autoLoginOn401 | boolean | true | 401 时是否自动触发登录 |
| reloadAfterLogin | boolean | true | 登录成功后是否刷新页面 |

### Auth.init(options?): Promise<boolean>

初始化方法，检查登录状态，未登录时自动触发登录。

---

## 完整示例

### React 应用入口

```typescript
// src/App.tsx
import { useEffect, useState } from 'react';
import axios from 'axios';
import { Auth } from './feishu-auth';

// 配置 axios
Auth.setupAxios(axios);

function App() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const init = async () => {
      // 初始化登录
      const success = await Auth.init({ autoConfirm: true });
      if (success) {
        setReady(true);
      }
    };
    init();
  }, []);

  if (!ready) {
    return <div>正在登录...</div>;
  }

  return <MainApp />;
}
```

### Vue 应用入口

```typescript
// src/main.ts
import { createApp } from 'vue';
import axios from 'axios';
import App from './App.vue';
import { Auth } from './feishu-auth';

async function bootstrap() {
  // 配置 axios
  Auth.setupAxios(axios);

  // 初始化登录
  const success = await Auth.init({ autoConfirm: true });
  if (!success) {
    return;
  }

  createApp(App).mount('#app');
}

bootstrap();
```

---

## 登录成功后如何使用

### Token 说明

登录成功后获取的 token 是 JWT 格式，用于调用 TTC 后端 API。

| 属性 | 说明 |
|------|------|
| 格式 | JWT (JSON Web Token) |
| 有效期 | 约 2 小时（具体以 `expiresAt` 为准） |
| 存储位置 | localStorage (`auth-token`, `auth-token-expires`) |

### 后端 API 基地址

| 环境 | 地址 |
|------|------|
| 生产环境 | `https://app.ttcadvisory.com/api` |
| 测试环境 | `https://int.ttcadvisory.com/api` |

### 在 API 请求中使用 Token

Token 需要放在请求头的 `Authorization` 字段中：

```typescript
// 方式一：使用 Auth.setupAxios 自动添加（推荐）
import axios from 'axios';
import { Auth } from './feishu-auth';

Auth.setupAxios(axios);

// 之后所有请求会自动带上 Authorization header
const res = await axios.get('/api/user_service/v1/user/current');
```

```typescript
// 方式二：手动添加 header
const token = Auth.getToken();

const res = await fetch('/api/user_service/v1/user/current', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
});
```

### 常用 API 示例

#### 获取当前用户信息

```typescript
// GET /api/user_service/v1/user/current
const res = await axios.get('/api/user_service/v1/user/current');
console.log(res.data);
// {
//   code: 0,
//   data: {
//     unique_id: "xxx",
//     name: "张三",
//     email: "zhangsan@ttcadvisory.com",
//     avatar_url: "https://...",
//     ...
//   }
// }
```

#### 处理 Token 过期

当 token 过期时，API 会返回 401 状态码。如果使用了 `Auth.setupAxios`，会自动触发重新登录：

```typescript
// setupAxios 会自动处理 401
Auth.setupAxios(axios, {
  autoLoginOn401: true,      // 401 时自动弹出登录
  reloadAfterLogin: true,    // 登录成功后刷新页面
});
```

如果需要手动处理：

```typescript
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      Auth.logout();  // 清除过期 token

      // 方式一：重新登录
      const success = await Auth.login();
      if (success) {
        window.location.reload();
      }

      // 方式二：跳转到登录页
      // window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

### 完整的 API 配置示例

```typescript
// src/api/index.ts
import axios from 'axios';
import { Auth } from './feishu-auth';

// 创建 axios 实例
const api = axios.create({
  baseURL: process.env.NODE_ENV === 'production'
    ? 'https://app.ttcadvisory.com'
    : 'https://int.ttcadvisory.com',
  timeout: 30000,
});

// 配置认证
Auth.setupAxios(api);

// 导出
export default api;

// 使用
// import api from './api';
// const res = await api.get('/api/user_service/v1/user/current');
```

---

## 授权页面参数

授权页面 `/auth/authorize` 支持以下 URL 参数：

| 参数 | 必填 | 说明 |
|------|------|------|
| callback_url | 是 | 回调地址（用于 postMessage 的 origin 验证） |
| state | 否 | 透传参数，会在回调时原样返回 |
| auto | 否 | 设为 1 时跳过确认页面，直接授权 |

---

## 域名白名单

授权页面会验证 `callback_url` 的域名，只有白名单内的域名才能接收 token。

### 当前白名单

| 配置值 | 匹配范围 | 说明 |
|--------|---------|------|
| `localhost` | localhost | 本地开发 |
| `127.0.0.1` | 127.0.0.1 | 本地开发 |
| `.ttcadvisory.com` | *.ttcadvisory.com | TTC 主域名 |
| `.ottin.com` | *.ottin.com | Ottin 域名 |
| `.feishu.cn` | *.feishu.cn | 飞书域名 |
| `.feishuapp.cn` | *.feishuapp.cn | 飞书应用域名 |

### 匹配规则

- 以 `.` 开头的配置：匹配该域名及所有子域名（如 `.ttcadvisory.com` 匹配 `app.ttcadvisory.com`、`int.ttcadvisory.com`）
- 不以 `.` 开头的配置：精确匹配（如 `localhost` 只匹配 `localhost`）

### 新增白名单域名

修改文件：`ottin-web/src/commonComponents/Auth/AuthorizePage/index.tsx`

找到 `ALLOWED_DOMAINS` 数组，添加新域名：

```typescript
const ALLOWED_DOMAINS = [
  "localhost",
  "127.0.0.1",
  ".ttcadvisory.com",
  ".ottin.com",
  ".feishu.cn",
  ".feishuapp.cn",
  // 新增域名示例：
  ".example.com",        // 匹配 *.example.com
  "specific.domain.com", // 精确匹配 specific.domain.com
];
```

修改后需要重新部署 ottin-web 才能生效。

---

## 相关文档

- [feishu-auth-sdk](./references/feishu-auth-sdk.md) - SDK 完整源码

---
