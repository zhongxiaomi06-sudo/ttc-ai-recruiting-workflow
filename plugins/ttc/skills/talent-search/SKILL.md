---
name: talent-search
description: 使用 TTC TalentStore API 搜索人才、获取水下信息、操作日志、名单和简历附件，并按活跃度生成候选人推荐。
---

# TTC TalentStore 人才库搜索完整指南

> 本 skill 包含人才库搜索的完整工作流程、API 调用方法和最佳实践
> 创建时间：2026-02-25
> 适用对象：其他 OpenClaw 实例

---

## 一、前置条件

### 1.1 获取 Token
**直接使用用户提供的 JWT Token**

- 用户会在需要时直接提供 JWT Token（以 `eyJhbGciOiJIUzI1Ni` 开头）
- 将用户提供的 token 用于所有 API 调用
- 不要自行去 AI-Foundation 或其他页面获取

### 1.2 API Base URL
```
https://api.ttcadvisory.com
```

---

## 二、核心 API 接口

### 2.1 人才搜索

**Endpoint**: `POST /api/talent_store/v1/search`

**完整 curl 示例**:
```bash
curl 'https://api.ttcadvisory.com/api/talent_store/v1/search' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'accept-language: zh,zh-CN;q=0.9' \
  -H 'authorization: Bearer <JWT_TOKEN>' \
  -H 'content-type: application/json' \
  -H 'origin: https://app.ttcadvisory.com' \
  -H 'referer: https://app.ttcadvisory.com/' \
  -H 'sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-site' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36' \
  --data-raw '{
    "keyword": "搜索关键词",
    "page_size": 100,
    "current_page": 1,
    "filter": {
      "locations": ["不限"],
      "degree": ["不限"],
      "university_category": ["不限"],
      "overseas_experience": ["不限"],
      "age_range": ["", ""],
      "has_system_tag_gulu": false,
      "has_system_tag_ttc": false,
      "has_mobile": false,
      "has_raw_resume": false
    },
    "colors": "",
    "names": [],
    "companies": [],
    "titles": [],
    "keyword_type": 2,
    "company_type": 2
  }'
```

**关键说明**:
- **必须使用浏览器 User-Agent**，不能用 curl 默认（会返回 500 错误）
- `origin` 和 `referer` 必须一致且为 `https://app.ttcadvisory.com`
- `sec-ch-ua` 和 `sec-fetch-*` 头部必须包含

**常用搜索参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| `keyword` | string | 搜索关键词（姓名、公司、职位等） |
| `page_size` | int | 每页数量（建议 20-100） |
| `current_page` | int | 当前页码 |
| `filter.locations` | array | 地点过滤 |
| `filter.age_range` | array | 年龄范围，如 `["25", "36"]` |

---

### 2.2 获取操作日志

**Endpoint**: `POST /api/talent_store/v1/person_leads/operation_logs/list`

**用途**: 查看人才近期活动（查看、上传简历等）

**curl 示例**:
```bash
curl 'https://api.ttcadvisory.com/api/talent_store/v1/person_leads/operation_logs/list' \
  -H 'authorization: Bearer <JWT_TOKEN>' \
  -H 'content-type: application/json' \
  ...其他headers同上 \
  --data-raw '{
    "person_leads_id": "<PERSON_LEADS_ID>",
    "page": 1,
    "page_size": 20
  }'
```

**响应字段**:
- `operate_type`: view（查看）、upload（上传简历）等
- `operator_user_name`: 操作人
- `operate_date`: 操作时间
- `upload_data`: 上传的简历信息

---

### 2.3 获取水下信息（Profile Summary）

**Endpoint**: `GET /api/talent_store/v1/time_based/profile_summary?person_leads_id=<ID>`

**用途**: 获取人才的详细水下信息（基本面、履历、职业动机、软性素质、流程状态）

**curl 示例**（单行版本，避免引号问题）：
```bash
curl -s 'https://api.ttcadvisory.com/api/talent_store/v1/time_based/profile_summary?person_leads_id=<PERSON_LEADS_ID>' -H 'authorization: Bearer <JWT_TOKEN>' -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36' -H 'origin: https://app.ttcadvisory.com' -H 'referer: https://app.ttcadvisory.com/'
```

**完整 headers 版本**（如需更多兼容性）：
```bash
curl -s 'https://api.ttcadvisory.com/api/talent_store/v1/time_based/profile_summary?person_leads_id=<PERSON_LEADS_ID>' \
  -H 'authorization: Bearer <JWT_TOKEN>' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36' \
  -H 'origin: https://app.ttcadvisory.com' \
  -H 'referer: https://app.ttcadvisory.com/' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'accept-language: zh-CN,zh;q=0.9'
```

**水下信息包含**:
| 分类 | 内容 |
|------|------|
| `basic_profile` | 年龄、学历、英语能力、现居地、期望工作地 |
| `professional_experience` | 当前/前公司、职位、核心职能、关键业绩 |
| `motivation` | 跳槽路径、求职诉求、薪资详情 |
| `soft_skills` | 沟通风格、性格特质 |
| `process_status` | 离职交接期、竞业限制、其他Offer |

**关键字段**:
- `source_count`: 信息来源数量
- `last_source_at`: 最后信息来源时间
- `updated_at`: 水下信息更新时间

---

### 2.4 获取简历附件列表

**Endpoint**: `POST /api/talent_store/v1/person_leads/resume/attachment/list`

**curl 示例**:
```bash
curl 'https://api.ttcadvisory.com/api/talent_store/v1/person_leads/resume/attachment/list' \
  -H 'authorization: Bearer <JWT_TOKEN>' \
  -H 'content-type: application/json' \
  ...其他headers同上 \
  --data-raw '{"person_leads_id":"<PERSON_LEADS_ID>"}'
```

---

### 2.5 获取人才所在名单

**Endpoint**: `POST /api/talent_store/v1/customized_list/get`

**用途**: 查看人才被添加到哪些项目/名单

**curl 示例**:
```bash
curl 'https://api.ttcadvisory.com/api/talent_store/v1/customized_list/get' \
  -H 'authorization: Bearer <JWT_TOKEN>' \
  -H 'content-type: application/json' \
  ...其他headers同上 \
  --data-raw '{"person_leads_id":"<PERSON_LEADS_ID>","page":1,"page_size":20}'
```

---

## 三、工作流程（改进版 - 借鉴 Manus 方法）

### 3.0 核心原则：Show Your Work + 确认理解

**【重要】** 在执行任何搜索前，必须先展示思考过程并确认理解：

#### Step 0.1: 需求解析与展示（Show Your Work）

收到职位需求后，**先不要直接搜索**，而是：

1. **解析职位需求**，提取关键信息：
   - 岗位名称
   - 核心技能要求
   - 经验年限
   - 学历要求
   - 目标公司类型
   - 加分项/排除项

2. **结构化展示理解结果**，格式如下：

```
## 📋 我对这个职位的理解

### 职位基本信息
- **岗位名称**: xxx
- **核心要求**: 
  - Must Have: xxx
  - Nice to Have: xxx
  - Must Not: xxx

### 搜索策略
- **主要关键词**: xxx（原因：xxx）
- **次要关键词**: xxx（原因：xxx）
- **目标公司**: xxx
- **筛选条件**: xxx

### 执行计划
1. 先用关键词"xxx"搜索
2. 再用关键词"xxx"补充
3. 获取候选人水下信息
4. 生成匹配度报告

👉 **请确认以上理解是否正确？如有调整请告诉我，确认后我开始搜索。**
```

#### Step 0.2: 等待用户确认

- **必须等待用户确认或修正**后才能开始搜索
- 如果用户提出调整，更新理解后再展示，直到达成一致
- **不要跳过这一步直接搜索**

---

### 3.1 搜索人才（确认理解后执行）

用户确认后，按以下步骤执行：

1. **展示第一步搜索意图**：
   ```
   🔍 **开始执行搜索**
   
   第一步：使用关键词"xxx"搜索目标候选人...
   ```

2. 使用搜索接口，构造关键词（如 `"AI产品经理 咨询 北京"`）
3. 设置合适的 `page_size`（建议 20-100）
4. 如需年龄限制，设置 `filter.age_range: ["25", "36"]`
5. **展示搜索结果摘要**：
   ```
   ✅ 搜索完成，找到 X 条记录
   初步筛选出以下候选人：
   - 候选人A：xx岁，xx公司，xx职位
   - 候选人B：xx岁，xx公司，xx职位
   ```

### 3.2 筛选结果
- **去重**：排除之前已经推荐过的人选
- **匹配度**：根据用户需求筛选最匹配的人选

### 3.3 判断活跃度
| 标志 | 说明 |
|------|------|
| ✅ **上传新简历** | 近期有人上传简历附件（从操作日志判断） |
| ✅ **被添加到多个名单** | 从 customized_list 接口查看 |
| ✅ **有水下信息** | profile_summary 返回详细内容 |
| ✅ **近期更新水下信息** | `updated_at` 或 `last_source_at` 较新 |
| ❌ **单纯有人查看** | 不算活跃 |

### 3.4 获取水下信息
对每个候选人调用 profile_summary 接口，获取详细背景信息。

### 3.5 优先级排序
| 优先级 | 条件 | 说明 |
|--------|------|------|
| ⭐⭐⭐⭐⭐ | 有水下信息 + 近期更新 + 有投递流程 | 最优先 |
| ⭐⭐⭐⭐ | 有水下信息 + 近期更新 | 很活跃，有顾问跟进 |
| ⭐⭐⭐ | 有水下信息但更新较旧 | 有一定了解 |
| ⭐⭐ | 无水下信息但近期有人上传简历 | 有更新 |
| ⭐ | 无水下信息，只有基本履历 | 了解较少 |

**注意**：投递情况（Pipeline）需要额外的 token/接口，目前无法直接获取。

### 3.6 输出格式
每次推荐必须包含：
- 排名/序号
- 姓名
- 年龄
- 职位
- 公司背景
- 地点
- 薪资（如有水下信息）
- 水下信息更新时间
- **人才库链接**（格式：`https://app.ttcadvisory.com/app/talent/<person_leads_id>`）

### 3.7 获取简历
1. 调用简历附件列表接口
2. 找到最新的 PDF 文件（按 `updated_at` 排序）
3. 直接下载并发送给用户，不要只给链接

---

## 四、错误排查

| 错误 | 原因 | 解决 |
|------|------|------|
| `invalid token` | Token 失效或格式错误 | 请用户重新提供 token |
| `Internal Server Error` / HTTP 500 | User-Agent 不正确 | 必须使用浏览器 User-Agent |
| `404 page not found` | 接口不存在或路径错误 | 检查接口路径 |
| `missing or invalid token` | 未带 authorization 头部 | 确保请求头包含 `authorization: Bearer <token>` |

---

## 五、关键注意事项

1. **Token 来源**：直接使用用户提供的 JWT Token，不要自行获取
2. **User-Agent**：必须使用浏览器标识，curl 默认会导致 500 错误
3. **Headers 完整性**：origin、referer、sec-ch-ua、sec-fetch-* 都必须包含
4. **人才库链接格式**：`https://app.ttcadvisory.com/app/talent/<person_leads_id>`
5. **简历下载**：用户要求时直接下载 PDF，不要只给链接
6. **去重**：不要重复推荐之前已经推荐过的人选

---

## 六、示例：完整搜索流程

```bash
# 1. 搜索人才
curl 'https://api.ttcadvisory.com/api/talent_store/v1/search' \
  -H 'authorization: Bearer <TOKEN>' \
  ...其他headers \
  --data-raw '{"keyword":"AI产品经理 咨询 北京","page_size":20,...}'

# 2. 获取水下信息（对每个候选人）
curl 'https://api.ttcadvisory.com/api/talent_store/v1/time_based/profile_summary?person_leads_id=<ID>' \
  -H 'authorization: Bearer <TOKEN>' \
  ...其他headers

# 3. 获取操作日志（判断活跃度）
curl 'https://api.ttcadvisory.com/api/talent_store/v1/person_leads/operation_logs/list' \
  -H 'authorization: Bearer <TOKEN>' \
  ...其他headers \
  --data-raw '{"person_leads_id":"<ID>","page":1,"page_size":20}'

# 4. 获取简历附件列表
curl 'https://api.ttcadvisory.com/api/talent_store/v1/person_leads/resume/attachment/list' \
  -H 'authorization: Bearer <TOKEN>' \
  ...其他headers \
  --data-raw '{"person_leads_id":"<ID>"}'

# 5. 下载最新 PDF 简历
curl -L -o /tmp/<文件名>.pdf '<PDF下载链接>'
```

---

## 七、文件位置

本 skill 文件应保存在：
```
/root/.openclaw/workspace/skills/talent-search/SKILL.md
```

确保所有 OpenClaw 实例都能读取到此文件，以实现技能和记忆的同步。
