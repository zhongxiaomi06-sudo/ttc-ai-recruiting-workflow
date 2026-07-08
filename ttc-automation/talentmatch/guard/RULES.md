# 白屏防护规则 v1.0

## 强制规则

1. **每次部署后必须运行** `python3 guard/whitescreen_guard.py`
2. **任一检查失败 = 不可交付**，立即回滚上一次 tar.gz 备份
3. **开发期间不接外部请求的调试代码禁止提交**

## 三层防护

| 层级 | 组件 | 作用 |
|------|------|------|
| 1. React ErrorBoundary | `components/ErrorBoundary.jsx` | 捕获 React 渲染树异常 |
| 2. window.onerror / onunhandledrejection | `App.jsx` useEffect | 捕获全局 JS 异常 + Promise rejection |
| 3. WhiteScreen Guard | `guard/whitescreen_guard.py` | 部署后自动验证 6 项 |

## 白屏根因知识库

| 日期 | 根因 | 症状 | 修复 |
|------|------|------|------|
| 2026-06-19 | jobs 表无 source 列 | save_job INSERT 500 | 去掉 valid_cols 中的 source |
| 2026-06-19 | matching/__init__ 双引擎 | import 链炸 | 改以 v2 为主 |

## 禁止操作（每次改代码前检查）

- 在 valid_cols 加 DB schema 不存在的列 → 500
- 删除已有 DB 列 → 旧数据 INSERT/UPDATE 崩
- bare `except: pass` → 真实错误被吞
- 修改 API 路由路径不同步前端 → 404
