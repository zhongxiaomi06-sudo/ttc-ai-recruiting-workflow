"""Skill normalization - maps aliases to canonical forms"""
from __future__ import annotations
import re

# Canonical skill mapping
SKILL_ALIASES = {
    # Python ecosystem
    "python3": "python", "python3.x": "python", "python 3": "python",
    "django rest framework": "drf", "django-rest": "drf",
    "fastapi": "fastapi", "flask": "flask",
    
    # AI/ML
    "machine learning": "ml", "machinelearning": "ml",
    "deep learning": "dl", "deeplearning": "dl",
    "nlp": "nlp", "自然语言处理": "nlp",
    "computer vision": "cv", "computervision": "cv",
    "计算机视觉": "cv",
    "大模型": "llm", "大语言模型": "llm", "chatgpt": "llm",
    "gpt": "llm", "langchain": "langchain",
    "pytorch": "pytorch", "tensorflow": "tensorflow", "tf": "tensorflow",
    "huggingface": "huggingface", "transformers": "transformers",
    "stable diffusion": "stable-diffusion", "aigc": "aigc",
    "reinforcement learning": "rl", "强化学习": "rl",
    "推荐系统": "recommendation-system", "recsys": "recommendation-system",
    
    # Cloud/DevOps
    "k8s": "kubernetes", "kubernetes": "kubernetes",
    "aws": "aws", "amazon web services": "aws",
    "gcp": "gcp", "google cloud": "gcp",
    "azure": "azure", "microsoft azure": "azure",
    "ci/cd": "cicd", "cicd": "cicd",
    "docker": "docker", "containerization": "docker",
    "terraform": "terraform", "ansible": "ansible",
    
    # Databases
    "postgresql": "postgres", "postgres": "postgres", "mysql": "mysql",
    "mongodb": "mongodb", "mongo": "mongodb",
    "redis": "redis", "elasticsearch": "elasticsearch", "es": "elasticsearch",
    "clickhouse": "clickhouse",
    
    # Frontend
    "react.js": "react", "reactjs": "react", "react js": "react",
    "vue.js": "vue", "vuejs": "vue", "vue js": "vue",
    "typescript": "typescript", "ts": "typescript",
    "next.js": "nextjs", "nextjs": "nextjs",
    
    # Mobile
    "flutter": "flutter", "react native": "react-native",
    "ios": "ios", "android": "android", "swift": "swift", "kotlin": "kotlin",
    
    # Data
    "spark": "spark", "apache spark": "spark",
    "flink": "flink", "apache flink": "flink",
    "kafka": "kafka", "apache kafka": "kafka",
    "hive": "hive", "apache hive": "hive",
    "etl": "etl", "数据仓库": "data-warehouse",
    
    # General
    "微服务": "microservices", "microservice": "microservices",
    "分布式": "distributed-systems", "高并发": "high-concurrency",
    "系统设计": "system-design",
    "agile": "agile", "scrum": "scrum",
    "产品经理": "product-manager", "pm": "product-manager",
    "项目管理": "project-management",
}

# Reverse mapping for display
CANONICAL_DISPLAY = {
    "ml": "Machine Learning", "dl": "Deep Learning", "nlp": "NLP",
    "cv": "Computer Vision", "llm": "LLM", "aigc": "AIGC",
    "rl": "Reinforcement Learning", "recommendation-system": "Recommendation System",
    "cicd": "CI/CD", "postgres": "PostgreSQL",
}


def normalize_skill(skill: str) -> str:
    """Normalize a skill string to canonical form"""
    s = skill.strip().lower()
    # Remove version numbers
    s = re.sub(r'\s*v?\d+(\.\d+)*$', '', s)
    s = s.strip()
    return SKILL_ALIASES.get(s, s)


def normalize_skills(skills: list[str]) -> list[str]:
    """Normalize a list of skills, deduplicate"""
    seen = set()
    result = []
    for s in skills:
        norm = normalize_skill(s)
        if norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


def display_skill(canonical: str) -> str:
    """Get display name for canonical skill"""
    return CANONICAL_DISPLAY.get(canonical, canonical.title())
