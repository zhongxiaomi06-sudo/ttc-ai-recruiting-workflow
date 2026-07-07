"""LLM 通用调用层：给分类、解析、话术生成提供统一入口。"""
import json
import logging
from typing import Any, Dict, Optional

from .config import LLM_CONFIG

logger = logging.getLogger(__name__)


def is_llm_ready() -> bool:
    return bool(LLM_CONFIG.get("api_key"))


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    response_format: Optional[Dict[str, Any]] = None,
) -> str:
    """使用 OpenAI 兼容接口调用 LLM。"""
    if not is_llm_ready():
        raise RuntimeError("LLM not configured")

    import openai

    client = openai.OpenAI(
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG.get("base_url") or None,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs = {
        "model": LLM_CONFIG.get("model", "gpt-4o-mini"),
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format

    try:
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
        raise


def call_llm_json(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> Dict[str, Any]:
    """调用 LLM 并解析返回的 JSON。"""
    content = call_llm(
        system_prompt,
        user_prompt,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].strip()
    return json.loads(content)
