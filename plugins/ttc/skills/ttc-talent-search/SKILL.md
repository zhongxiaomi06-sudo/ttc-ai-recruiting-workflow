---
name: ttc-talent-search
description: 通过 TTC TalentStore API 或 Source MySQL 人才库拉取候选人数据，并生成 HTML/JSON 比赛结果展示。TTC API 模式需要用户配置 JWT Token，Source MySQL 模式不需要 JWT。
---

# TTC 人才搜索数据拉取

本 skill 对应脚本：`scripts/ttc_talent_search.py`

## 前置条件

1. Source MySQL 已配置：`~/.ttc/mysql.env` 已存在且可连接。
2. TTC API 需要 JWT Token。推荐在登录后自行把 token 写入 `~/.ttc/ttc_jwt.env`（不提交到 Git）：
   ```bash
   mkdir -p ~/.ttc
   echo 'TTC_JWT_TOKEN=eyJhbGciOiJIUzI1Ni...' > ~/.ttc/ttc_jwt.env
   chmod 600 ~/.ttc/ttc_jwt.env
   ```
   也可以设置环境变量：
   ```bash
   export TTC_JWT_TOKEN=eyJhbGciOiJIUzI1Ni...
   ```
3. 依赖已安装：`pymysql` 已加入 `requirements.txt`。

## 常用命令

### 1. 仅查询 Source MySQL 本地人才库
```bash
venv/bin/python scripts/ttc_talent_search.py \
  --source-only \
  --keyword "AI产品经理" \
  --limit 20 \
  --output data/ttc_source_results.html \
  --json-output data/ttc_source_results.json
```

### 2. 调用 TTC TalentStore API
```bash
venv/bin/python scripts/ttc_talent_search.py \
  --keyword "AI产品经理 北京" \
  --limit 20 \
  --output data/ttc_search_results.html \
  --json-output data/ttc_search_results.json
```

### 3. 拉取水下信息（profile_summary）
```bash
venv/bin/python scripts/ttc_talent_search.py \
  --keyword "后端" \
  --limit 10 \
  --profiles \
  --output data/ttc_search_results.html
```

## 输出

- HTML：可直接在浏览器打开，作为比赛结果展示。
- JSON：结构化数据，便于后续二次处理。
- 默认保存位置：`data/ttc_search_results.html`

## 注意事项

- TTC API 必须使用浏览器 User-Agent、origin 与 referer，脚本已自动处理。
- Token 约 2 小时过期，过期后需要重新复制。
- 不要通过任何消息把真实 JWT Token 明文发送给他人。
- Source MySQL 的本地记录 ID 不一定等于 TTC `person_leads_id`，因此本地结果不生成可能错误的线上详情链接。
