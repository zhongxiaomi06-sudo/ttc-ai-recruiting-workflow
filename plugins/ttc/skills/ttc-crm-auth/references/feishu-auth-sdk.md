# 飞书统一授权 SDK 源码

将以下代码复制到项目中即可使用。

---

## 源文件位置

`ottin-web/src/sdk/feishu-auth.ts`

---

## 完整源码

```typescript
/**
 * 飞书统一授权 SDK
 *
 * 使用方式：
 * 1. 复制此文件到你的项目中
 * 2. 修改 AUTH_URL 为实际的授权页面地址
 * 3. 在应用入口调用 Auth.init() 或检查登录状态
 *
 * @example
 * ```typescript
 * import { Auth } from './feishu-auth';
 *
 * // 检查登录状态
 * if (!Auth.isLoggedIn()) {
 *   const success = await Auth.login();
 *   if (!success) {
 *     console.log('用户取消登录');
 *     return;
 *   }
 * }
 *
 * // 获取 token
 * const token = Auth.getToken();
 *
 * // 配置 axios
 * Auth.setupAxios(axios);
 * ```
 */

// ========== 配置项 ==========
// 授权页面地址，请根据实际部署地址修改
const AUTH_URL = "https://ottin.ttcadvisory.com/auth/authorize";

// Token 存储的 key
const TOKEN_KEY = "auth-token";
const TOKEN_EXPIRE_KEY = "auth-token-expires";

// ========== 类型定义 ==========
interface AuthMessage {
  type: "AUTH_SUCCESS" | "AUTH_CANCEL";
  token?: string;
  expiresAt?: string;
}

interface LoginOptions {
  /** 是否跳过确认页面，直接授权（需要授权页面支持） */
  autoConfirm?: boolean;
  /** popup 窗口宽度 */
  width?: number;
  /** popup 窗口高度 */
  height?: number;
}

// ========== Auth 对象 ==========
export const Auth = {
  /**
   * 检查是否已登录
   */
  isLoggedIn(): boolean {
    const expires = localStorage.getItem(TOKEN_EXPIRE_KEY);
    if (!expires) return false;
    return Date.now() < parseInt(expires);
  },

  /**
   * 获取 token
   */
  getToken(): string | null {
    if (!this.isLoggedIn()) return null;
    return localStorage.getItem(TOKEN_KEY);
  },

  /**
   * 获取 token 过期时间戳
   */
  getTokenExpires(): number | null {
    const expires = localStorage.getItem(TOKEN_EXPIRE_KEY);
    return expires ? parseInt(expires) : null;
  },

  /**
   * 设置 token（通常由 SDK 内部调用）
   */
  setToken(token: string, expiresAt: string | number): void {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(TOKEN_EXPIRE_KEY, String(expiresAt));
  },

  /**
   * 清除 token
   */
  clearToken(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRE_KEY);
  },

  /**
   * 登出
   */
  logout(): void {
    this.clearToken();
  },

  /**
   * 弹窗登录
   * @returns Promise<boolean> 登录成功返回 true，取消或失败返回 false
   */
  login(options: LoginOptions = {}): Promise<boolean> {
    const { autoConfirm = false, width = 500, height = 600 } = options;

    return new Promise((resolve) => {
      const left = (screen.width - width) / 2;
      const top = (screen.height - height) / 2;

      // 构建授权 URL
      const authUrl = new URL(AUTH_URL);
      authUrl.searchParams.set("callback_url", window.location.origin);
      if (autoConfirm) {
        authUrl.searchParams.set("auto", "1");
      }

      // 打开 popup 窗口
      const popup = window.open(
        authUrl.toString(),
        "feishu-auth",
        `width=${width},height=${height},left=${left},top=${top},menubar=no,toolbar=no,location=no,status=no`
      );

      if (!popup) {
        console.error("无法打开登录窗口，请检查是否被浏览器拦截");
        resolve(false);
        return;
      }

      // 监听 message 事件
      const handleMessage = (event: MessageEvent<AuthMessage>) => {
        // 验证来源
        try {
          const authOrigin = new URL(AUTH_URL).origin;
          if (event.origin !== authOrigin) return;
        } catch {
          return;
        }

        const { data } = event;

        if (data.type === "AUTH_SUCCESS" && data.token && data.expiresAt) {
          this.setToken(data.token, data.expiresAt);
          cleanup();
          resolve(true);
        } else if (data.type === "AUTH_CANCEL") {
          cleanup();
          resolve(false);
        }
      };

      // 检测窗口关闭
      const checkClosed = setInterval(() => {
        if (popup.closed) {
          cleanup();
          // 如果窗口关闭但没有收到消息，视为取消
          resolve(false);
        }
      }, 500);

      const cleanup = () => {
        window.removeEventListener("message", handleMessage);
        clearInterval(checkClosed);
        if (!popup.closed) {
          popup.close();
        }
      };

      window.addEventListener("message", handleMessage);
    });
  },

  /**
   * 重定向登录（非 popup 模式）
   * 登录完成后会重定向回当前页面，token 通过 URL 参数传递
   */
  loginWithRedirect(options: { state?: string; autoConfirm?: boolean } = {}): void {
    const { state, autoConfirm = false } = options;

    const authUrl = new URL(AUTH_URL);
    authUrl.searchParams.set("callback_url", window.location.href);
    if (state) {
      authUrl.searchParams.set("state", state);
    }
    if (autoConfirm) {
      authUrl.searchParams.set("auto", "1");
    }

    window.location.href = authUrl.toString();
  },

  /**
   * 处理重定向登录的回调
   * 在页面加载时调用，检查 URL 中是否有 token 参数
   * @returns boolean 是否处理了登录回调
   */
  handleRedirectCallback(): boolean {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const expiresAt = params.get("expires_at");

    if (token && expiresAt) {
      this.setToken(token, expiresAt);

      // 清除 URL 中的参数
      const url = new URL(window.location.href);
      url.searchParams.delete("token");
      url.searchParams.delete("expires_at");
      url.searchParams.delete("state");
      window.history.replaceState(null, "", url.toString());

      return true;
    }

    return false;
  },

  /**
   * 配置 axios 实例
   * - 自动添加 Authorization header
   * - 401 时自动触发登录
   */
  setupAxios(
    axios: {
      interceptors: {
        request: { use: (fn: (config: { headers: Record<string, string> }) => unknown) => void };
        response: { use: (onFulfilled: (response: unknown) => unknown, onRejected: (error: { response?: { status: number } }) => unknown) => void };
      };
    },
    options: {
      /** 401 时是否自动触发登录，默认 true */
      autoLoginOn401?: boolean;
      /** 登录成功后是否刷新页面，默认 true */
      reloadAfterLogin?: boolean;
    } = {}
  ): void {
    const { autoLoginOn401 = true, reloadAfterLogin = true } = options;

    // 请求拦截器 - 添加 token
    axios.interceptors.request.use((config: { headers: Record<string, string> }) => {
      const token = this.getToken();
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // 响应拦截器 - 处理 401
    axios.interceptors.response.use(
      (response: unknown) => response,
      async (error: { response?: { status: number } }) => {
        if (error.response?.status === 401 && autoLoginOn401) {
          this.clearToken();
          const success = await this.login();
          if (success && reloadAfterLogin) {
            window.location.reload();
          }
        }
        return Promise.reject(error);
      }
    );
  },

  /**
   * 初始化
   * 1. 检查是否是登录回调
   * 2. 检查登录状态
   * 3. 如果未登录，触发登录
   */
  async init(options: LoginOptions & { required?: boolean } = {}): Promise<boolean> {
    const { required = true, ...loginOptions } = options;

    // 处理重定向回调
    this.handleRedirectCallback();

    // 如果已登录，直接返回
    if (this.isLoggedIn()) {
      return true;
    }

    // 如果需要登录
    if (required) {
      return this.login(loginOptions);
    }

    return false;
  },
};

export default Auth;
```

---

## 配置说明

### AUTH_URL

授权页面地址，根据环境修改：

| 环境 | 地址 |
|------|------|
| 生产 | `https://ottin.ttcadvisory.com/auth/authorize` |
| 测试 | `https://ottin-dev.ttcadvisory.com/auth/authorize` |

### TOKEN_KEY / TOKEN_EXPIRE_KEY

Token 在 localStorage 中的存储 key，可以根据需要修改避免冲突。

---

## JavaScript 版本

如果项目不使用 TypeScript，可以删除类型定义：

```javascript
const AUTH_URL = "https://ottin.ttcadvisory.com/auth/authorize";
const TOKEN_KEY = "auth-token";
const TOKEN_EXPIRE_KEY = "auth-token-expires";

export const Auth = {
  isLoggedIn() {
    const expires = localStorage.getItem(TOKEN_EXPIRE_KEY);
    if (!expires) return false;
    return Date.now() < parseInt(expires);
  },

  getToken() {
    if (!this.isLoggedIn()) return null;
    return localStorage.getItem(TOKEN_KEY);
  },

  setToken(token, expiresAt) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(TOKEN_EXPIRE_KEY, String(expiresAt));
  },

  clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRE_KEY);
  },

  logout() {
    this.clearToken();
  },

  login(options = {}) {
    const { autoConfirm = false, width = 500, height = 600 } = options;

    return new Promise((resolve) => {
      const left = (screen.width - width) / 2;
      const top = (screen.height - height) / 2;

      const authUrl = new URL(AUTH_URL);
      authUrl.searchParams.set("callback_url", window.location.origin);
      if (autoConfirm) {
        authUrl.searchParams.set("auto", "1");
      }

      const popup = window.open(
        authUrl.toString(),
        "feishu-auth",
        `width=${width},height=${height},left=${left},top=${top},menubar=no,toolbar=no,location=no,status=no`
      );

      if (!popup) {
        resolve(false);
        return;
      }

      const handleMessage = (event) => {
        try {
          const authOrigin = new URL(AUTH_URL).origin;
          if (event.origin !== authOrigin) return;
        } catch {
          return;
        }

        const { data } = event;

        if (data.type === "AUTH_SUCCESS" && data.token && data.expiresAt) {
          this.setToken(data.token, data.expiresAt);
          cleanup();
          resolve(true);
        } else if (data.type === "AUTH_CANCEL") {
          cleanup();
          resolve(false);
        }
      };

      const checkClosed = setInterval(() => {
        if (popup.closed) {
          cleanup();
          resolve(false);
        }
      }, 500);

      const cleanup = () => {
        window.removeEventListener("message", handleMessage);
        clearInterval(checkClosed);
        if (!popup.closed) {
          popup.close();
        }
      };

      window.addEventListener("message", handleMessage);
    });
  },

  setupAxios(axios, options = {}) {
    const { autoLoginOn401 = true, reloadAfterLogin = true } = options;

    axios.interceptors.request.use((config) => {
      const token = this.getToken();
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401 && autoLoginOn401) {
          this.clearToken();
          const success = await this.login();
          if (success && reloadAfterLogin) {
            window.location.reload();
          }
        }
        return Promise.reject(error);
      }
    );
  },

  async init(options = {}) {
    const { required = true, ...loginOptions } = options;

    this.handleRedirectCallback();

    if (this.isLoggedIn()) {
      return true;
    }

    if (required) {
      return this.login(loginOptions);
    }

    return false;
  },
};

export default Auth;
```

---
