"""Parse natural-language recruiting requests into structured SearchIntent."""
from __future__ import annotations

import json
import re
from typing import Optional

from .models import SearchIntent


def _heuristic_parse(query: str) -> SearchIntent:
    """Fallback parser when LLM is unavailable. Extracts simple signals."""
    intent = SearchIntent(query=query)

    # Years of experience
    m = re.search(r"(\d+)\s*[\-–~]\s*(\d+)\s*年", query)
    if m:
        intent.min_years = int(m.group(1))
        intent.max_years = int(m.group(2))
    else:
        m = re.search(r"(\d+)\s*年(?:以上|经验|及以上)?", query)
        if m:
            intent.min_years = int(m.group(1))

    # Count
    m = re.search(r"找\s*(\d+)\s*个", query)
    if m:
        intent.count = int(m.group(1))

    # Location
    locations = ["北京", "上海", "深圳", "广州", "杭州", "成都", "武汉", "西安", "南京", "苏州"]
    for loc in locations:
        if loc in query:
            intent.location = loc
            break

    # Simple title/skill extraction: first noun phrase after 找/招
    m = re.search(r"[找招聘].*?(.*?)(?:，|,|；|;|。|$)", query)
    if m:
        intent.title = m.group(1).strip() or ""

    # Common skills
    skill_keywords = [
        "Java", "Python", "Go", "Golang", "Rust", "C++", "C#", "JavaScript", "TypeScript",
        "Node", "React", "Vue", "Angular", "PHP", "Ruby", "Swift", "Kotlin",
        "后端", "前端", "全栈", "算法", "机器学习", "深度学习", "数据挖掘",
        "产品经理", "运营", "设计", "UI", "UX", "测试", "运维", "DevOps",
    ]
    intent.skills = [s for s in skill_keywords if s in query]

    return intent


def _llm_parse(query: str) -> Optional[SearchIntent]:
    """Use configured LLM to parse query. Returns None if LLM unavailable."""
    try:
        from daemon.llm_client import chat_completion, parse_json_safe
    except Exception:
        return None

    system_msg = (
        "You parse Chinese recruiting requests into JSON. "
        "Return only a JSON object with keys: title, skills (list), location, "
        "min_years, max_years (or null), education, salary_range, company, count, channels (list). "
        "If the request is vague, set clarification to a question string."
    )
    user_msg = f"Parse this request: {query}"
    text = chat_completion(
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        json_mode=True,
        temperature=0.2,
    )
    data = parse_json_safe(text)
    if not data:
        return None

    data["query"] = query
    # Drop unknown keys
    allowed = {f for f in SearchIntent.model_fields}
    data = {k: v for k, v in data.items() if k in allowed}
    try:
        return SearchIntent(**data)
    except Exception:
        return None


def parse_intent(query: str) -> SearchIntent:
    """Parse a natural-language query into SearchIntent.

    Tries LLM first, falls back to heuristic parser.
    """
    if not query or not query.strip():
        return SearchIntent(query=query, clarification="请提供招聘需求，例如：找 3 个 Java 后端，5 年经验，上海")

    parsed = _llm_parse(query)
    if parsed:
        return parsed

    return _heuristic_parse(query)
