# TTC 自动化猎头工作流 · API 接口文档

服务启动后，自动生成 OpenAPI/Swagger 文档：

- Swagger UI：`http://127.0.0.1:8766/docs`
- OpenAPI JSON：`http://127.0.0.1:8766/openapi.json`
- 测试控制台：`http://127.0.0.1:8766/console`
- 工作台：`http://127.0.0.1:8766/dashboard`

如果配置了 `TTC_API_TOKEN`，所有 POST/PUT/DELETE 接口需要在请求头携带 `X-TTC-Token`。

---

## 1. 摄入输入

### 1.1 提交网页 / ChatGPT 链接读取任务

```bash
curl -X GET "http://127.0.0.1:8766/ingest/read-link?url=https://chatgpt.com/share/xxx" \
  -H "X-TTC-Token: $TTC_API_TOKEN"
```

返回：

```json
{
  "ok": true,
  "read_job_id": "rjob_xxx",
  "url": "https://chatgpt.com/share/xxx"
}
```

调度器会自动完成：读取 → 分类 → 归一化 → 路由 → 创建 Mission。

### 1.2 提交飞书 / JD 文本

```bash
curl -X POST http://127.0.0.1:8766/ingest/feishu \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{
    "source_type": "feishu_docx",
    "source_url": "https://jxog8b3tny.feishu.cn/docx/xxx",
    "title": "某 AI 公司后端负责人 JD",
    "raw_text": "岗位职责：...\n任职要求：..."
  }'
```

### 1.3 提交候选人简历

```bash
curl -X POST http://127.0.0.1:8766/ingest/resume \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{
    "candidate": {
      "name": "张三",
      "phone": "13800000000",
      "email": "zhangsan@example.com",
      "skills": ["Python", "LLM", "Kubernetes"],
      "current_company": "某大厂",
      "current_title": "AI Infra 工程师"
    }
  }'
```

### 1.4 提交本地文件

```bash
curl -X POST http://127.0.0.1:8766/ingest/file \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{
    "file_path": "/path/to/resume.pdf",
    "source_type": "candidate_resume"
  }'
```

### 1.5 查询 read_job 状态

```bash
curl http://127.0.0.1:8766/ingest/job/rjob_xxx
```

---

## 2. Mission 编排

### 2.1 手动启动 Mission

```bash
# 从最新未路由的 JD artifact 启动
curl -X POST http://127.0.0.1:8766/mission/start \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{}'

# 或指定 artifact
curl -X POST http://127.0.0.1:8766/mission/start \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{"normalized_artifact_id": "art_xxx"}'
```

### 2.2 查看 Mission 状态

```bash
curl http://127.0.0.1:8766/mission/miss_xxx
```

### 2.3 手动推进一步（调试）

```bash
curl -X POST http://127.0.0.1:8766/mission/miss_xxx/step \
  -H "X-TTC-Token: $TTC_API_TOKEN"
```

---

## 3. 人类任务

### 3.1 查看任务列表

```bash
# 待办任务
curl http://127.0.0.1:8766/human/tasks

# 指定状态
curl "http://127.0.0.1:8766/human/tasks?status=completed&limit=10"
```

### 3.2 打开 HTML 任务页

浏览器访问：

```text
http://127.0.0.1:8766/human/task/htask_xxx
```

### 3.3 完成任务

```bash
curl -X POST http://127.0.0.1:8766/human/task/htask_xxx/complete \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d "outcome=interested&notes=候选人有意向，下周面试"
```

电话任务常见 outcome：

- `interested` — 有意向
- `not_interested` — 无兴趣
- `no_answer` — 未接通
- `wrong_info` — 信息有误

---

## 4. 输出

### 4.1 查看电话清单

```bash
curl http://127.0.0.1:8766/api/call-list | python3 -m json.tool
```

### 4.2 查看反馈

```bash
curl -X POST http://127.0.0.1:8766/feedback \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{
    "candidate_id": "cand_xxx",
    "call_list_id": "call_xxx",
    "outcome": "interested",
    "notes": "已通过初筛"
  }'
```

---

## 5. 管理接口

### 5.1 Source 公司人才库状态

```bash
curl http://127.0.0.1:8766/admin/source-talent
```

### 5.2 验证/刷新 Source 人才库

```bash
curl -X POST http://127.0.0.1:8766/admin/reload-source-talent \
  -H "X-TTC-Token: $TTC_API_TOKEN"
```

### 5.3 重试失败的 read_job

```bash
curl -X POST http://127.0.0.1:8766/admin/read-job/rjob_xxx/retry \
  -H "X-TTC-Token: $TTC_API_TOKEN"
```

---

## 6. 健康检查

```bash
curl http://127.0.0.1:8766/health
```

---

## 7. 推荐测试流程

1. 启动服务：`python3 ttc_daemon.py` 或 `docker compose up -d --build`
2. 访问 `http://127.0.0.1:8766/console`
3. 在控制台粘贴一个真实 JD 或 ChatGPT share link，点击提交。
4. 等待 10~60 秒后访问 `http://127.0.0.1:8766/dashboard`，查看 Mission 和待办任务。
5. 打开 `http://127.0.0.1:8766/human/task/xxx` 查看生成的电话任务。
