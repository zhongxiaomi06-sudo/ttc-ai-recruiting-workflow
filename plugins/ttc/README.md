# TTC Codex Plugin

TTC AI 猎头工作流的 Codex 插件骨架，参考 [openai/plugins](https://github.com/openai/plugins) 的 manifest 与 skill 结构。

## 结构

```
plugins/ttc/
├── .codex-plugin/
│   └── plugin.json       # 插件元数据
├── skills/
│   ├── ttc/              # TTC Daemon 工作流
│   └── ttc-talent-search/# TalentStore/Source 搜索
└── README.md
```

## 使用方式

1. Source MySQL 搜索需要 `~/.ttc/mysql.env`；TTC API 搜索需要 `~/.ttc/ttc_jwt.env`。
2. 运行人才搜索：
   ```bash
   venv/bin/python scripts/ttc_talent_search.py --source-only --keyword "AI" --limit 20
   ```
3. 使用插件创建工具校验 `plugins/ttc/`，再按本地插件方式安装。

## 待实现

- **MCP Server 端点**：Daemon 尚未实现 `/mcp`，因此当前插件只声明可用 Skills，不声明无效的 MCP/App 配置。
- **工具实现**：后续可把现有 REST API 包装成 MCP tools。

## 参考

- [openai/plugins](https://github.com/openai/plugins)
- `plugins/linear/` 示例
