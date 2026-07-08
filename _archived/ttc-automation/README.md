# TTC 猎头工作流自动化组件

配合 [方案三_AI猎头工作流_第一层架构.html](../方案三_AI猎头工作流_第一层架构.html) 使用，实现：

- 飞书页面一键推送到本地工作流
- ChatGPT share link 自动读取
- 本地 Daemon 统一接收、存储、编排
- 猎头最终只需打电话

## 文件结构

```
ttc-automation/
├── README.md                          # 本文件
├── ttc-feishu-bridge.user.js          # 飞书 → Daemon 油猴脚本
├── ttc-chatgpt-reader.user.js         # ChatGPT share link 读取油猴脚本
└── daemon/
    ├── requirements.txt
    ├── run.sh                         # 一键启动 Daemon
    ├── ttc_daemon.py                  # FastAPI 本地服务
    └── link_reader.py                 # ChatGPT/网页/PDF 读取器
```

## 快速部署

### 1. 启动本地 Daemon

```bash
cd ttc-automation/daemon
./run.sh
```

默认监听 `http://127.0.0.1:8766`。

首次运行会自动创建虚拟环境并安装依赖；Playwright 浏览器需要单独安装：

```bash
playwright install chromium
```

### 2. 安装浏览器油猴脚本

1. 安装 [Tampermonkey](https://www.tampermonkey.net/) 或 Violentmonkey。
2. 安装 [Feishu Toolkit](https://github.com/BlueSkyXN/feishu-toolkit)（解除复制限制、去水印）。
3. 在油猴管理器中点击“添加新脚本”，把 `ttc-feishu-bridge.user.js` 的内容粘贴进去并保存。
4. 同样方式安装 `ttc-chatgpt-reader.user.js`。

### 3. 启动 candidate-collector

```bash
cd candidate-collector
./run.sh
```

candidate-collector 默认监听 `http://127.0.0.1:8765`，Daemon 后续会通过 `/api/export-jd` 拉取已评分候选人。

## 使用方式

### 飞书页面

打开任意飞书文档 / Wiki / 表格 / 群聊页面，右下角会出现 **TTC** 悬浮面板：

- **发送整页 → TTC**：提取页面可见文本并发送到 Daemon。
- **发送选中 → TTC**：只发送当前选中的文本。
- **设置 Daemon 地址**：如果本机端口不是 8766 可修改。
- **自动识别 JD**：开启后检测到招聘关键词会自动推送。

### ChatGPT share link

打开 `https://chatgpt.com/share/...`，右下角会出现 **TTC ChatGPT** 面板：

- 默认自动等待对话加载完成后发送到 Daemon。
- 如果自动失败，可点击“发送对话 → TTC”手动重试。

### Daemon API

常用端点：

```bash
# 健康检查 + 统计
curl http://127.0.0.1:8766/status

# 手动让 Daemon 读取一个链接（适合 ChatGPT / 网页）
curl -X POST "http://127.0.0.1:8766/link/read?url=https://chatgpt.com/share/..."

# 查看已收录的记录
curl "http://127.0.0.1:8766/records?limit=10"
```

## 数据存放

所有原始快照和提取内容都保存在本机 `ttc-automation/daemon/data/` 下：

- `data/feishu/`：来自飞书的 JSON 原文
- `data/links/<hash>/`：每个链接的 `raw.html`、`extracted.md`、`meta.json`
- `data/resumes/`：candidate-collector 推送的简历
- `data/ttc.db`：SQLite 索引与元数据

## 注意事项

- 油猴脚本通过 `GM_xmlhttpRequest` 绕过浏览器跨域限制，直接向本机 Daemon 发送数据。
- ChatGPT share link 能否读取取决于你本机网络能否打开该页面；如果网络层直接拒绝（如当前服务器环境），Playwright 也会失败。
- 只采集你已授权访问的页面；不绕过登录、验证码、付费墙。
- 本组件仅完成“采集 + 归集”，人才库接口对接、评分排序、生成电话清单需继续集成。

## 下一步

1. 提供公司人才库 API 文档，完成 `Talent DB Gateway`。
2. 集成 TalentMatch / GoldScoreEngine 评分。
3. 生成“今日待打电话”清单并推送到飞书 Bot。
