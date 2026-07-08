"""TTC Daemon — AI 猎头工作流核心包。

子包：
- agents/  — Agent 编排、人机调度、反馈学习、仓位管理
- core/    — 评分引擎、JD 解析、候选人补全
- ingestion/ — 读取 → 分类 → 归一化 → 路由
- notifications/ — 飞书 Bot 通知
- templates/ — Jinja2 HTML 任务页面
- tests/   — 集成测试
"""
from . import db  # noqa: F401 — 所有模块通过 from .. import db 引用
