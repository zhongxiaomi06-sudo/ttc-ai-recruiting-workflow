# TTC 交易系统 · 项目进度

> 最后更新：2026-07-13
> 当前分支：`feature/merge-talentmatch`
> 核心目标：大量简历进入人才库（0.1 版本）

---

## 一、项目目标

解决猎头团队简历供给不足问题，实现人均每日有效简历从 5 份 → 50 份。

**0.1 版本关键结果**：
- [ ] BOSS 直聘公共邮箱通路日同步 ≥30 份简历
- [ ] 浏览器插件（脉脉 + 公域人才库）日采集 ≥15 份简历
- [ ] 人才库总简历数（1 周内）≥ 500
- [ ] 有效简历率（4 要素全满足）≥ 60%

---

## 二、已完成模块

### 2.1 candidate-collector（简历采集器 v2）

| 模块 | 状态 | 说明 |
|---|---|---|
| 浏览器扩展 | ✅ | 支持 BOSS/脉脉/猎聘，平台解析器已拆分 |
| 自动阅读列表页 | ✅ | 最多 10 人/批，8 秒间隔 |
| 本地文件解析 | ✅ | PDF/DOC/DOCX/图片 OCR |
| 邮箱自动同步 | ✅ | Gmail/通用 IMAP，5 分钟轮询 |
| 统一入库流水线 v2 | ✅ | dry-run/write 模式 |
| 飞书多维表格适配器 | ⚠️ | 代码完成，但审计出 CLI 参数错误 |
| JD 对齐评分 | ✅ | 含启承资本画像分 |
| CLI / HTTP API | ✅ | `cli.py`, `app.py` |
| 批量导入脚本 | ✅ | `scripts/batch_import_remaining.py` |
| 手机号恢复脚本 | ✅ | `scripts/recover_phones.py` |

### 2.2 ttc_daemon（AI 招聘工作流）

| 模块 | 状态 | 说明 |
|---|---|---|
| FastAPI daemon | ✅ | `main.py` |
| Mission 状态机 | ✅ | created → jd_parsed → sourcing → scored → human_pending → feedback → closed |
| 多 agent 编排 | ✅ | 当前串行推进 |
| 人才库 API 适配器 | ✅ | 已接入 TALENT_DB / SOURCE_TALENT（MySQL/API/文件） |
| ingestion 流水线 | ✅ | read_job → classify → normalize → route |
| 人工任务调度 | ✅ | `human_dispatch.py` 生成 HTML 任务页 + 飞书通知 |

### 2.3 AI Skills

| Skill | 状态 |
|---|---|
| talent-search | ✅ 已创建 |
| ttc-talent-search | ✅ 已创建 |
| ttc-crm-auth/crm/pipeline/talent/user | ✅ 已创建 |
| jobwater | ✅ 已创建 |
| linkedin-search-skill | ✅ 已创建 |

---

## 三、待修复问题

来自 [CLAUDE_AUDIT.md](CLAUDE_AUDIT.md)：

### 高优先级（阻塞 0.1 版本）

- [ ] `candidate-collector/adapters/feishu_base.py`：lark-cli 命令参数错误，飞书写入可能失败
- [ ] `candidate-collector/parsers/unified_parser.py`：姓名/公司/职位/毕业年份/城市提取误识别
- [ ] `candidate-collector/models.py`：指纹判重、无效手机号、JSON 序列化问题
- [ ] `candidate-collector/ingestion/pipeline.py`：去重逻辑错误、假成功记录

### 中优先级

- [ ] `ttc-automation/talentmatch/app/__init__.py:70`：`except` 后缺少缩进代码块
- [ ] 浏览器扩展自动发送到 `ttc_daemon` 入口（当前发送到 candidate-collector 本地）
- [ ] 人才库自然语言检索 skill 未验证

---

## 四、待实现能力

按 0.1 版本目标：

- [ ] 修复飞书多维表格写入，确保简历能真正入库
- [ ] 把浏览器插件采集目标从 candidate-collector 改为 ttc_daemon（或统一人才库）
- [ ] BOSS 公共邮箱通路端到端验证
- [ ] 有效简历 4 要素校验（完整简历、手机号、求职意向、薪资职级）
- [ ] 无手机号简历通过公域人才库撞库补全
- [ ] 批量从已接入人才库 API 拉取简历
- [ ] 简单 dashboard 查看人才库增长数据

---

## 五、Git 状态

```
未提交修改：17 个文件
未跟踪文件：50+ 个文件/目录
```

**建议提交分组**：
1. `feat: candidate-collector v2 统一入库流水线`
2. `feat: ttc_daemon AI 招聘状态机与 agent 编排`
3. `feat: TTC CRM/talent/search skills`
4. `docs: 项目文档与审计报告`
5. `chore: 环境配置与依赖更新`

---

## 六、下一步行动

1. **整理提交**：把当前代码按模块分组 commit
2. **验证通路**：跑通 candidate-collector → 飞书多维表格的简历写入
3. **修复审计问题**：优先修复阻塞 0.1 版本的 4 个问题
4. **批量拉取**：从已接入人才库 API 导入大量简历
5. **dashboard**：查看人才库增长和有效简历率

---

*本文件由 Claude Code 于 2026-07-13 创建，用于跟踪项目真实进度。*
