---
name: talentmatch-ui
description: TalentMatch 猎头智能匹配系统 UI 设计规范。基于 React + Ant Design v6 的企业级后台管理界面。当需要修改/重构/扩展猎头系统前端时使用此 skill，确保 UI 风格与现有 Ant Design 设计语言一致。
---

# TalentMatch UI Design System

## 技术栈
- React 19 + Ant Design v6 + Vite 8
- 图标：`@ant-design/icons`
- 无额外 UI 库，纯 Ant Design 原生组件
- 构建产出：`frontend/react-app/dist/`，部署到阿里云 ECS 的 `/opt/recruit-bot-v5/frontend/react-dist/`

## 页面结构

```
Layout (Sider + Header + Content)
├── Dashboard      仪表盘 — KPI 卡片 + 快速操作 + 系统状态
├── Candidates     人才库 — 卡片/列表双视图 + 职业画像弹窗
├── Jobs           职位库 — 状态筛选 + 新建职位表单
├── Match          智能匹配 — JD 粘贴即用
├── Search         全局搜索
├── Batch          批量导入
└── Stats          数据洞察
```

## 设计原则

### 1. Ant Design 原生优先
- 复用 antd 内置组件（Card, Table, Form, Modal, Tabs, Descriptions, Progress, Tag, Badge, Statistic, Flex, Input, Row, Col, Space, Spin, Empty, Avatar, Divider, Select, Radio, Tooltip, Segmented）
- 所有组件必须是 antd 原生，不使用自定义 HTML table/div 构建列表
- 表单使用 `Form + Form.Item` 而非手写布局
- 列表页用 `<Table>` 组件替代手写 `<table>/<tr>/<td>`
- 头像使用 antd `<Avatar>` 组件（非手写 div）

### 2. 人才库页面（Candidates.jsx）
- 核心入口页面，卡片 + 列表双视图
- 统计栏使用 4 个 Card（总候选人/优秀80+/合格60-79/平均分）带 Avatar 图标
- 工具栏 Card 包含：搜索 Input + 排序 Select + 刷新 Button + 列表/卡片切换 Radio
- 列表视图使用 antd `<Table>`（rowSelection + sorter + pagination）
- 姓名列使用 `NameCell` 组件：antd Avatar（36px）+ 姓名文字 + inline Badge 展示分数
- 详细 Modal 弹窗（职业画像/技能/工作经历/教育背景四 Tab）
- 猎头关注的字段（角色@公司、经验、薪资、技能标签、地点）
- 高分指示器（>=80 强烈推荐标签）

### 3. 卡片式候选人卡片（CandidateCard）
- 顶部 3px 渐变色条色彩层次
- 左上角 Avatar（40px），右上角环形分数
- 姓名 + 角色@公司
- 经验/薪资行
- 技能 Tag（最多3个 + 更多Tooltip）
- 地点信息
- 高分（>=80）绿色边框 + 强烈推荐标签
- 良好（>=70）蓝色边框
- 过渡动画 transition: all 0.25s ease

### 4. 列表视图
- 姓名列 `NameCell`：32px Avatar + 姓名 + inline Badge 分数
- 技能列用分类染色 Tag（见第5条）
- 经验列用 Tag 显示
- 薪资列用紫色文字
- 提供行选择（rowSelection）、列排序（sorter）

### 5. 技能标签分类染色
```
  frontend (React/Vue/Angular/JS/TS)       → #1677ff
  backend (Java/Go/Python/Spring/Django)   → #722ed1
  data (Spark/Flink/Hadoop/ETL/SQL/BI)     → #13c2c2
  AI/ML (LLM/GPT/BERT/ML/DL/NLP/CV)       → #eb2f96
  cloud (AWS/Azure/GCP/K8s/Docker)         → #fa8c16
  mobile (Android/iOS/Flutter/RN)          → #52c41a
  devops (CI/CD/Jenkins/GitLab)            → #fa541c
  database (MySQL/PostgreSQL/Redis/Mongo)  → #2f54eb
  default                                  → #595959
```
使用 `Tag color={color}` 渲染。关键词匹配规则支持中英文。

### 6. 分数体系
- `scoreMeta(s)` 函数：返回 { color, bg, label } 五级评分
  - 90+ 顶级 (#389e0d)
  - 80+ 优秀 (#52c41a)
  - 70+ 良好 (#1677ff)
  - 60+ 一般 (#faad14)
  - <60 待定 (#ff4d4f)
- 分数使用 antd `<Badge>` 内置样式展示
- 环形进度条 Progress type="circle" 64px (详情弹窗) 或 44px (卡片视图)

### 7. 弹窗详情（Modal）
- 标题区：Avatar + 姓名 + 公司/职位
- 内容分四页 Tab：（1）职业画像（高亮标签 + AI摘要）、（2）技能标签（按分类分组）、（3）工作经历（时间线样式）、（4）教育背景
- 顶部信息卡：环形分数 + 6格信息（工作经验/当前公司/所在地/期望薪资/邮箱/电话）
- 宽度 800px

### 8. 全局主题 (main.jsx)
- 使用 antd `ConfigProvider` 设置全局 token
- 组件特有 token：Table（headerBg, rowHoverBg）、Card、Menu、Layout
- 中文 locale `zhCN`
- 圆角统一 6px，字体 13px，wireframe: false

### 9. 布局 (Layout.jsx)
- 侧边栏：220px 宽（collapsible）
- Logo 区域使用渐变色块 + "T" 文字 + "TalentMatch · 猎头人岗匹配系统"
- 顶栏：56px 高，sticky 定位
  - 左侧：折叠按钮 + 当前页面名称
  - 右侧：通知铃铛（Badge）+ 用户头像（梯度色Avatar）+ 名称/角色
- 侧边栏底部品牌："上海决胜人力资源"
- hover 动效：头像区域 hover 背景色、折叠按钮 hover 背景色

### 10. 仪表盘 (Dashboard.jsx)
- 问候语 + 日期
- 4个 KPI 卡片（候选人/活跃职位/匹配记录/反馈标注）含环比进度 vs 上月
- 快速操作区（4个彩色背景卡片，分别对应人才库/职位库/智能匹配/批量导入）
- 系统状态（AI服务+数据层 两个状态卡片，含进度条和服务信息）
- 最近动态列表

### 11. 搜索 (Search.jsx)
- Segmented 切换候选人/岗位搜索
- 大输入框 + 大按钮（borderRadius: 8）
- 搜索结果 Table

### 12. 职位库 (Jobs.jsx)
- 3个统计 Card（活跃/关闭/紧急）
- 工具栏：状态筛选 Select + 新建 Button
- 职位信息列：名称 + 公司/地点
- 匹配按钮带 Thunderbolt 图标
- 新建 Modal：Form 表单，含职位名称/公司/地点/薪资/紧急度/描述

### 13. 智能匹配 (Match.jsx)
- 左侧 JD 输入 TextArea + 开始匹配按钮
- 右侧匹配结果统计（匹配人数/平均匹配度/高分人数）
- 底部匹配候选人列表 Table

## 后端 API 约定
```
GET  /api/candidates             列表
GET  /api/candidates/:id         详情
GET  /api/candidates/search/:q   搜索
GET  /api/jobs?status=active     职位列表
POST /api/jobs                   创建职位
GET  /api/jobs/:id               职位详情
POST /api/fast-match             快速匹配（form-urlencoded）
GET  /api/stats                  统计数据
GET  /api/health                 系统健康检查
```
所有 API 返回 JSON，前端在 `src/api/index.js` 中封装 `api` 对象。
API 通过 nginx 反向代理到后端的 8878 端口。

## 构建与部署

```bash
# 安装依赖
cd frontend/react-app && npm install

# 开发
npm run dev

# 构建
npx vite build

# 部署（本地执行，需要 SSH 密钥权限）
rsync -avz --delete \
  -e "ssh -i <KEY> -o StrictHostKeyChecking=no -p 22" \
  frontend/react-app/dist/ \
  root@47.110.93.137:/opt/recruit-bot-v5/frontend/react-dist/

# 重启 nginx
ssh -i <KEY> root@47.110.93.137 "nginx -s reload"
```

## 文件结构
```
frontend/react-app/src/
├── api/index.js      — 统一 API 封装
├── App.jsx           — 路由分发
├── main.jsx          — 入口（ConfigProvider 主题 + zhCN locale）
├── components/
│   └── Layout.jsx    — Sider + Header + Content 布局
└── pages/
    ├── Dashboard.jsx — 仪表盘（KPI + 快速操作 + 系统状态）
    ├── Candidates.jsx — 人才库（双视图 + 详情弹窗 + 职业画像）
    ├── Jobs.jsx       — 职位库（状态筛选 + 新建表单）
    ├── Match.jsx      — 智能匹配（JD输入 + 结果展示）
    ├── Search.jsx     — 全局搜索（候选人/岗位双模式）
    ├── Batch.jsx      — 批量导入
    └── Stats.jsx      — 数据洞察
```

## 生产环境
- 阿里云 ECS: 47.110.93.137 (Ubuntu 26.04, 2vCPU/8GiB, 5Mbps)
- 部署路径: `/opt/recruit-bot-v5/frontend/react-dist/`
- 域名: 无独立域名，通过 IP 直接访问
- SSH 密钥: `rsa` (本地文件)
