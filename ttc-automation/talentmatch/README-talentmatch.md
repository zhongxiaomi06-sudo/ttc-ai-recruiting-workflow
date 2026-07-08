# TalentMatch · 猎头智能匹配系统

猎头简历智能解析与 JD-候选人匹配系统。基于 **FastAPI + React + XGBoost** 的企业级招聘辅助工具。

## 系统架构

```
飞书Bot ←→ FastAPI Webhook (:8878) → Agent Pipeline
    → JD Parser Agent    → 职位库 (SQLite + RDS MySQL)
    → Resume Agent       → 人才库 (SQLite + RDS MySQL)
    → Match Agent        → 规则+LLM+ML 混合匹配
    → Outreach Agent     → 外联草稿
    → Interview Agent    → 面试题生成
    → Pipeline Result    → 飞书卡片 / React SPA
```

## 核心功能

- **人才库管理** — 简历解析、技能提取、画像构建
- **职位库管理** — JD 解析、技能需求提取
- **智能匹配** — 规则引擎(0.6) + XGBoost(0.4) 混合评分
- **飞书 Bot 交互** — 文件上传、对话匹配、主动推送
- **训练流水线** — RDS 59,566 条训练数据 → XGBoost 模型
- **知识库** — 20,298 条 JD 语料、1,919 个技能词条、中英文映射

## 使用技术

| 层 | 技术 |
|------|------|
| 后端 | Python 3.14, FastAPI, Pydantic |
| 前端 | React 19, Ant Design 5, Vite |
| 数据库 | SQLite (业务), RDS MySQL (训练数据) |
| ML | XGBoost 3.2, scikit-learn, Lightweight Predictor |
| 向量 | ChromaDB |
| LLM | DashScope qwen-plus / DeepSeek-chat |
| 部署 | nginx, systemd, 阿里云 ECS |

## 快速开始

```bash
git clone https://github.com/zhongxiaomi06-sudo/talentmatch.git
cd talentmatch
pip install -r requirements.txt
python3 main.py
```

## 训练流水线

```bash
# 知识库构建（JD 导入 + 技能词库）
python3 training/build_knowledge_base.py

# RDS 训练
python3 training/rds_train.py

# 传统训练
python3 training/train.py --load data.jsonl --model xgboost
```

## 部署

系统已部署在阿里云 ECS `47.110.93.137`，通过 nginx + systemd 管理。
