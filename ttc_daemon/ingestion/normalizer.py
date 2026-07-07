"""Normalizer：把分类后的原始内容转成统一结构。"""
import re
from typing import Dict, Any

from ..core.jd_parser import extract_jd


def _extract_name(text: str) -> str:
    # 简单启发：找“姓名：xxx”或直接按行首人名
    m = re.search(r"(?:姓名|名字)[：:]\s*([^\n]{1,20})", text)
    if m:
        return m.group(1).strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[0][:20] if lines else ""


def _extract_email(text: str) -> str:
    m = re.search(r"[\w.-]+@[\w.-]+\.\w+", text)
    return m.group(0) if m else ""


def _extract_phone(text: str) -> str:
    m = re.search(r"1[3-9]\d{9}", text.replace(" ", "").replace("-", ""))
    return m.group(0) if m else ""


def _extract_skills(text: str) -> list:
    skill_keywords = [
        "python", "go", "java", "rust", "c++", "javascript", "typescript",
        "react", "vue", "node", "kubernetes", "docker", "redis", "kafka",
        "mysql", "postgresql", "mongodb", "elasticsearch", "aws", "阿里云",
        "tensorflow", "pytorch", "llm", "ai", "算法", "后端", "前端", "全栈",
        "运维", "sre", "产品", "设计", "数据", "vllm", "sglang", "cuda",
    ]
    found = []
    lower = text.lower()
    for kw in skill_keywords:
        if kw in lower:
            found.append(kw)
    return found


def normalize(artifact_type: str, record: Dict[str, Any]) -> Dict[str, Any]:
    text = record.get("raw_text", "")

    if artifact_type == "jd":
        return extract_jd(text)

    if artifact_type == "candidate":
        return {
            "name": _extract_name(text),
            "email": _extract_email(text),
            "phone": _extract_phone(text),
            "skills": _extract_skills(text),
            "raw_text": text[:2000],
        }

    if artifact_type == "chat":
        return {
            "conversation": text,
            "turns": text.count("\n\n"),
        }

    if artifact_type == "evidence":
        return {
            "summary": text[:1000],
            "source_url": record.get("source_url", ""),
        }

    return {"raw_text": text[:1000]}
