# TTC 自动化猎头工作流 · API 接口文档

服务启动后，自动生成 OpenAPI/Swagger 文档：

- Swagger UI：`http://127.0.0.1:8766/docs`
- OpenAPI JSON：`http://127.0.0.1:8766/openapi.json`
- 测试控制台：`http://127.0.0.1:8766/console`
- 工作台：`http://127.0.0.1:8766/dashboard`

如果配置了 `TTC_API_TOKEN`，所有 POST/PUT/DELETE 接口需要在请求头携带 `X-TTC-Token`。

本机如果配置了 HTTP/HTTPS 代理，建议 curl 增加 `--noproxy "*"`，否则访问 `127.0.0.1` 可能被代理成 502。

推荐本地启动方式：

```bash
source venv/bin/activate
source ~/.ttc/mysql.env          # 可选：启用云端 Source MySQL 人才库
export TTC_SOURCE_TALENT_ENABLED=true
export TTC_API_TOKEN=localtest
scripts/run_local_daemon.sh
```

通用变量：

```bash
export TTC_URL=http://127.0.0.1:8766
export TTC_API_TOKEN=localtest
```

---

## 1. 摄入输入

### 1.1 提交网页 / ChatGPT 链接读取任务

```bash
curl --noproxy "*" -X GET "$TTC_URL/ingest/read-link?url=https://chatgpt.com/share/xxx" \
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
curl --noproxy "*" -X POST "$TTC_URL/ingest/feishu" \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{
    "source_type": "feishu_docx",
    "source_url": "https://jxog8b3tny.feishu.cn/docx/xxx",
    "title": "某 AI 公司后端负责人 JD",
    "raw_text": "岗位职责：...\n任职要求：..."
  }'
```

真实 JD smoke 示例：

```bash
curl --noproxy "*" -X POST "$TTC_URL/ingest/feishu" \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{
    "source_type": "manual_jd",
    "source_url": "manual://smoke/ai-pm",
    "title": "AI 产品经理 JD",
    "raw_text": "招聘 AI 产品经理，地点杭州/上海。岗位职责：负责 AI Agent 产品规划、需求分析、商业化落地。任职要求：熟悉 AI、LLM、Python、Redis，有大厂或智能硬件经验优先。薪资 35-65K。"
  }'
```

### 1.3 提交候选人简历

```bash
curl --noproxy "*" -X POST "$TTC_URL/ingest/resume" \
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

注意：服务器部署时，`/ingest/file` 读取的是服务器本地路径，不是顾问电脑路径。顾问电脑上的 PDF/Word 简历建议先用 `scripts/batch_ingest_resumes.py` 本地解析，再通过 `/ingest/link` 或 `/ingest/resume` 上传文本。

```bash
curl --noproxy "*" -X POST "$TTC_URL/ingest/file" \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{
    "file_path": "/path/to/resume.pdf",
    "source_type": "candidate_resume"
  }'
```

### 1.5 查询 read_job 状态

```bash
curl --noproxy "*" "$TTC_URL/ingest/job/rjob_xxx"
```

关键字段：

- `status`：`pending` / `running` / `succeeded` / `failed` / `needs_human`
- `read_status`：`succeeded` / `empty` / `failed`
- `content_type_guess`：`jd` / `candidate` / `chat` / `unknown`
- `error_reason`：`empty_content` / `login_required` / `file_missing` / `unsupported_file` / `runtime_error`
- `method`：`provided` / `requests` / `playwright` / `firecrawl` / `crawl4ai` / `markitdown`

---

## 2. Mission 编排

### 2.1 手动启动 Mission

```bash
# 从最新未路由的 JD artifact 启动
curl --noproxy "*" -X POST "$TTC_URL/mission/start" \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{}'

# 或指定 artifact
curl --noproxy "*" -X POST "$TTC_URL/mission/start" \
  -H "Content-Type: application/json" \
  -H "X-TTC-Token: $TTC_API_TOKEN" \
  -d '{"normalized_artifact_id": "art_xxx"}'
```

### 2.2 查看 Mission 状态

```bash
curl --noproxy "*" "$TTC_URL/mission/miss_xxx"
```

Mission 状态：

- `created`：已创建，等待/准备 JD 解析
- `jd_parsed`：JD 字段已结构化
- `sourcing`：已召回候选人
- `scored`：候选人已评分
- `human_pending`：电话任务或真人业务动作待完成
- `problem_pending`：异常/信息缺失，等待问题任务恢复
- `feedback`：电话反馈完成，等待收口
- `closed`：流程结束

### 2.3 手动推进一步（调试）

```bash
curl --noproxy "*" -X POST "$TTC_URL/mission/miss_xxx/step" \
  -H "X-TTC-Token: $TTC_API_TOKEN"
```

---

## 3. 人类任务

### 3.1 查看任务列表

```bash
# 待办任务
curl --noproxy "*" "$TTC_URL/human/tasks"

# 指定状态
curl --noproxy "*" "$TTC_URL/human/tasks?status=completed&limit=10"
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

异常任务常见 outcome：

- `resolved` — 已解决，系统按 `resume_action` 恢复
- `cannot_resolve` — 无法解决，Mission 关闭或等待后续人工处理

问题任务按类型展示结构化字段：

- `empty_content` / `read_failed` / `login_required`：可填替代 URL 或人工粘贴正文
- `classify_uncertain`：可人工选择 `jd` / `candidate` / `evidence` / `chat` / `unknown`
- `jd_clarify` / `source_help`：可补岗位、地点、薪资、技能、目标公司和备注

---

## 4. 输出

### 4.1 查看电话清单

```bash
curl --noproxy "*" "$TTC_URL/api/call-list" | python3 -m json.tool
```

### 4.2 查看反馈

```bash
curl --noproxy "*" -X POST "$TTC_URL/feedback" \
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
curl --noproxy "*" "$TTC_URL/admin/source-talent"
```

返回示例：

```json
{
  "ok": true,
  "enabled": true,
  "file_path": "",
  "candidate_count": 0,
  "mysql_enabled": true,
  "mysql_host": "121.40.2.48",
  "mysql_database": "recruit_bot",
  "mysql_sample_count": 5
}
```

### 5.2 验证/刷新 Source 人才库

```bash
curl --noproxy "*" -X POST "$TTC_URL/admin/reload-source-talent" \
  -H "X-TTC-Token: $TTC_API_TOKEN"
```

### 5.3 重试失败的 read_job

```bash
curl --noproxy "*" -X POST "$TTC_URL/admin/read-job/rjob_xxx/retry" \
  -H "X-TTC-Token: $TTC_API_TOKEN"
```

---

## 6. 健康检查

```bash
curl --noproxy "*" "$TTC_URL/health"
```

---

## 7. 推荐测试流程

1. 启动服务：`scripts/run_local_daemon.sh` 或 `docker compose up -d --build`
2. 访问 `http://127.0.0.1:8766/admin/source-talent`，确认 `mysql_enabled=true` 或 JSON 文件数量正常。
3. 访问 `http://127.0.0.1:8766/console`，填入 API Token，再粘贴真实 JD 或 ChatGPT share link。
4. 等待 10~60 秒后访问 `http://127.0.0.1:8766/dashboard`，查看 Mission、电话清单和待办任务。
5. 打开 `http://127.0.0.1:8766/human/task/xxx` 查看生成的电话任务。
6. 如进入 `problem_pending`，查看问题任务中的 `problem`、`resume_action` 和结构化字段，补充后提交恢复。

完整 smoke 预期：

```text
read_job: succeeded
artifact: jd / mission_created
mission: created → jd_parsed → sourcing → scored → human_pending
call_list: > 0
human_tasks: task_type=call
```
