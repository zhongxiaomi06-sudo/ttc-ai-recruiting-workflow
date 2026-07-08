# TTC Codex Plugin

TTC AI 猎头工作流的 Codex 插件骨架，参考 [openai/plugins](https://github.com/openai/plugins) 的 manifest 与 skill 结构。

## 结构

```
plugins/ttc/
├── .codex-plugin/
│   └── plugin.json       # 插件元数据
├── .app.json             # 依赖的本地 App/服务
├── .mcp.json             # MCP Server 入口
├── skills/
│   └── ttc/
│       └── SKILL.md      # 工作流与可用工具说明
└── README.md
```

## 使用方式

1. 确保 TTC Daemon 已启动：
   ```bash
   scripts/run_local_daemon.sh
   ```
2. 在 Codex / Claude Code 中加载本插件（指向 `plugins/ttc/.codex-plugin`）。
3. 调用 `ingest_jd` 等工具即可驱动工作流。

## 待实现

- **MCP Server 端点**：Daemon 需要新增 `/mcp` 路由，按 MCP 协议暴露工具（health、ingest_jd、get_mission、get_call_list、complete_human_task 等）。
- **OAuth/认证**：当前 `.mcp.json` 使用本地无认证；生产环境应接入 `TTC_API_TOKEN`。
- **工具实现**：把现有 REST API 包装成 MCP tools。

## 参考

- [openai/plugins](https://github.com/openai/plugins)
- `plugins/linear/` 示例
