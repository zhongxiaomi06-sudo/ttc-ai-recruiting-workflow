"""Auto role classification — infer role_type from skills + current_role.
Writes to candidates.role_type field.

Categories: 产品 / 前端 / 后端 / 算法 / 数据 / AI / 运维 / 测试 / 管理 / 其他
"""
from __future__ import annotations
import json
import re
from typing import List, Optional

ROLE_RULES = [
    # (pattern, role_type, priority)
    # Higher priority wins when multiple match
    (r"产品经理|产品总监|产品负责人|产品运营|产品设计|product manager|pm", "产品", 5),
    (r"前端|web前端|h5|react|vue|angular|前端架构", "前端", 5),
    (r"后端|java|go|rust|c\+\+|spring boot|后端架构|微服务|middleware", "后端", 5),
    (r"算法|推荐系统|搜广推|nlp|计算机视觉|cv|自然语言|语音识别|推荐算法|搜索算法", "算法", 5),
    (r"数据工程师|数据开发|数据仓库|etl|spark|flink|hadoop|大数据|数据分析师|bi", "数据", 4),
    (r"ai|人工智能|机器学习|深度学习|大模型|llm|aigc|pytorch|tensorflow|强化学习", "AI", 5),
    (r"运维|devops|sre|基础设施|k8s|docker|云原生|运维开发|运维工程师|系统运维", "运维", 4),
    (r"测试|qa|测试开发|自动化测试|性能测试|质量保障|软件测试", "测试", 4),
    (r"技术经理|技术总监|cto|技术负责人|架构师|技术leader|engineering manager", "管理", 4),
    (r"全栈|full.?stack", "全栈", 3),
    (r"安全|网络安全|信息安全|安全工程师|渗透", "安全", 4),
]


def classify_role(current_role: str = "", skills: Optional[List[str]] = None) -> str:
    """Infer role type from role title and skills.
    Returns one of: 产品 / 前端 / 后端 / 算法 / 数据 / AI / 运维 / 测试 / 管理 / 全栈 / 安全 / 其他
    """
    skills = skills or []
    text = f"{current_role or ''} {' '.join(skills)}".lower()
    
    best_role = "其他"
    best_priority = 0
    
    for pattern, role_type, priority in ROLE_RULES:
        if re.search(pattern, text):
            if priority > best_priority:
                best_role = role_type
                best_priority = priority
    
    return best_role


def batch_classify(candidates: List[dict]) -> List[dict]:
    """Batch classify and return updated candidates with role_type set."""
    updated = []
    for c in candidates:
        skills_raw = c.get("skills", "[]")
        if isinstance(skills_raw, str):
            try:
                skills = json.loads(skills_raw) if skills_raw.startswith("[") else []
            except (json.JSONDecodeError, TypeError):
                skills = []
        else:
            skills = skills_raw or []
        
        role_type = classify_role(
            current_role=c.get("current_role", ""),
            skills=skills,
        )
        
        if role_type != c.get("role_type"):
            c["role_type"] = role_type
            updated.append(c)
    
    return updated


if __name__ == "__main__":
    # Test
    tests = [
        ("高级后端工程师", ["Java", "Spring Boot", "MySQL"], "后端"),
        ("产品经理", ["Axure", "PRD"], "产品"),
        ("AI算法工程师", ["PyTorch", "NLP", "LLM"], "AI"),
        ("前端开发工程师", ["React", "TypeScript"], "前端"),
        ("", [], "其他"),
        ("CTO", ["Java", "Python", "管理"], "管理"),
    ]
    for role, skills, expected in tests:
        result = classify_role(role, skills)
        status = "✅" if result == expected else "❌"
        print(f"{status} classify_role({role!r}, {skills!r}) = {result!r} (expected {expected!r})")
