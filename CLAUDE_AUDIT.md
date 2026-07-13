# Claude 代码审计结果

更新时间：2026-07-12 20:43（Asia/Shanghai）

## 语法错误

1. `ttc-automation/talentmatch/app/__init__.py:70`：`except` 后缺少缩进代码块，触发 `IndentationError`。

## 逻辑错误

1. `candidate-collector/adapters/feishu_base.py:166`：`+record-upload-attachment` 缺少 `--table-id`、`--record-id` 和 `--field-id`，命令无法执行。
2. `candidate-collector/adapters/feishu_base.py:169`：附件上传传入绝对路径，但 `lark-cli` 文件参数只接受当前工作目录内的相对路径。
3. `candidate-collector/adapters/feishu_base.py:190`：代码在创建记录前上传附件；附件上传依赖已经存在的 `record_id`，执行顺序错误。
4. `candidate-collector/adapters/feishu_base.py:202`：`+record-batch-create` 使用不存在的 `--records` 参数；当前命令要求 `--json`，内容为 `fields` 和 `rows`。
5. `candidate-collector/adapters/feishu_base.py:219`：`+record-search` 使用不存在的 `--field-name` 和 `--query` 参数；当前命令要求 `--keyword` 和 `--search-field`。
6. `candidate-collector/adapters/feishu_base.py:234`：第二次 `+record-search` 同样使用不存在的 `--query` 参数。
7. `candidate-collector/adapters/feishu_base.py:153`：`_run_cli()`把 `record-search` 默认的 Markdown 输出交给 `json.loads()`，成功查询也会解析失败。
8. `candidate-collector/adapters/feishu_base.py:228,242`：去重查询吞掉所有异常，把参数、认证或网络错误解释为“未重复”，可能产生重复记录。
9. `candidate-collector/config/feishu_field_mapping.json`：`work_location.fallback` 为“无匹配类别”，但该值不在同字段 `options` 数组中。
10. `candidate-collector/config/feishu_field_mapping.json`：`resume_attachment` 和 `name` 被标记为必填，会阻断无附件的授权页面采集和姓名待识别材料进入待处理区。
11. `candidate-collector/models.py`：姓名、公司和职位均为空时，所有候选人生成相同指纹 `name_company_title|||`，造成错误判重。
12. `candidate-collector/models.py`：少于7位的无效电话号码仍返回原字符串，不符合无效号码置空或进入人工复核的逻辑。
13. `candidate-collector/models.py`：`to_db_dict()`中的 `experiences_json`、`education_json` 和 `keywords_json` 返回对象或列表，而现有 SQLite 写入链路要求 JSON 字符串。
14. `candidate-collector/parsers/unified_parser.py:128-141`：`_extract_experiences()`没有要求存在任职时间或公司特征，几乎每两个相邻短行都会被当成公司和职位，随后第一条误识别结果会覆盖 `current_company` 和 `current_title`。
15. `candidate-collector/parsers/unified_parser.py:119`：姓名回退正则中的 `\d{0,2}`允许零个数字，导致任何以2至4个汉字开头的普通正文都可能被识别为姓名。
16. `candidate-collector/parsers/unified_parser.py:42-50,168-171`：就业状态按字典插入顺序匹配，“在职”排在“在职-考虑机会”和“在职-暂不考虑”之前，具体状态会被提前归类成泛化的“在职”。
17. `candidate-collector/parsers/unified_parser.py:269,330`：`expected_location`直接复用全文第一个城市，与 `current_location`完全相同，未限定“期望/意向”上下文，会把当前城市错误写成期望城市。
18. `candidate-collector/parsers/unified_parser.py:34,149-158`：毕业年份正则把“毕业/届”设为可选；教育行中出现的任意20xx年份都可能被当成本科毕业年份。
19. `candidate-collector/parsers/unified_parser.py:277-278`：图片文件被声明为支持格式，但解析函数固定返回空文本，仍生成可入库记录；这会把尚未OCR的图片误当成已解析候选人。
20. `candidate-collector/parsers/unified_parser.py:262-264`：扫描型PDF提取不到文字时没有切换OCR或标记 `needs_review`，而是以 `pending` 状态继续，导致空PDF绕过人工复核。
21. `candidate-collector/parsers/unified_parser.py:282`：图片附件的 `attachment_mime_type`固定为 `None`，后续文件类型校验和上传无法依赖该字段。
23. `candidate-collector/ingestion/pipeline.py:89-96`：本地去重把 `dry_run`、`failed` 等所有日志状态都视为已完成重复；执行过 dry-run 后真实入库会被跳过，失败任务也无法重试。
24. `candidate-collector/ingestion/pipeline.py:196-233`：`ingest_text()`既不查询本地重复，也不写入 `ingestion_log`；相同浏览器文本重复执行会反复创建飞书记录，且没有可追踪状态。
25. `candidate-collector/ingestion/pipeline.py:146-177`：即使飞书响应中没有提取到 `record_id`，代码仍把写入状态记录为 `success`，产生无法定位和更新的假成功记录。
26. `candidate-collector/ingestion/pipeline.py:238-246`：批量创建响应通常包含记录集合；当前 `_extract_record_id()`只检查 `data.record_id` 或把 `data`当列表，未处理 `data.records`，会把成功创建误解析成空 `record_id`。
28. `candidate-collector/parsers/unified_parser.py:253-270`：修复尝试第1次失败。替换中文标点只消除了 `Java`后的边界问题，“使用Java”中的中文“用”和字母`J`仍都属于正则单词字符，前边界仍不存在；`Java`继续漏识别，测试失败。
