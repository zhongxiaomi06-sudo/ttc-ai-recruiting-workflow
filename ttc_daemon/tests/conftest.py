"""共享测试 fixtures：临时 SQLite 数据库 + 测试数据。"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def temp_db(monkeypatch):
    """用临时 SQLite 替换真实数据库，避免污染开发数据。"""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="ttc_test_")
    os.close(fd)

    # 覆盖 DB_PATH
    import ttc_daemon.db as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", Path(path))
    db_mod.init_db()

    yield path

    # 清理
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def sample_jd_text():
    """一份典型的 JD 文本。"""
    return """
岗位：高级后端工程师（AI 方向）
公司：某头部 AI 公司
地点：北京·望京
薪资：60-100K × 15薪

职位描述：
负责公司核心 AI 推理平台的后端架构设计与开发，包括：
- 设计并实现高并发推理服务网关
- 优化模型推理性能，支持 vLLM/SGLang 等框架
- 建设分布式任务调度系统
- 参与技术选型和架构评审

任职要求：
1. 5 年以上后端开发经验，精通 Python/Go
2. 熟悉 Kubernetes/Docker 容器化部署
3. 有分布式系统设计经验
4. 了解 LLM 推理框架（vLLM、SGLang、CUDA）优先
5. 有高并发系统设计经验，熟悉 Redis/Kafka/MySQL
6. 本科及以上学历，计算机相关专业
"""


@pytest.fixture
def sample_candidate_profile():
    """一份典型候选人简历。"""
    return {
        "name": "张三",
        "phone": "13800138000",
        "email": "zhangsan@example.com",
        "source_types": ["talent_db"],
        "raw_profile": {
            "summary": "8 年后端开发经验，目前在某 AI 独角兽任高级工程师，主导推理平台网关设计，"
                       "日均处理 100M+ 推理请求。精通 Python/Go，熟悉 Kubernetes 和分布式系统。",
            "source_url": "https://github.com/zhangsan",
        },
        "jd_alignment_score": 75,
        "gold_score": 80,
    }


@pytest.fixture
def sample_candidate_profile_with_risks():
    """带有风险信号的候选人。"""
    return {
        "name": "李四",
        "phone": "13900139000",
        "email": "lisi@example.com",
        "source_types": ["talent_db"],
        "raw_profile": {
            "summary": "3 年工作经验，最近一份工作仅 8 个月。在某小公司做全栈开发。",
        },
        "jd_alignment_score": 45,
        "gold_score": 40,
        "risk_flags": [
            {"flag": "上一份工作不满1年", "severity": "yellow", "detail": "最近一份工作仅 8 个月"},
            {"flag": "频繁跳槽（1年内3次以上）", "severity": "red", "detail": "过去 2 年换了 4 家公司"},
        ],
    }
