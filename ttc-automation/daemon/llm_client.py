"""Thin LLM client wrapper. Supports OpenAI-compatible APIs (Kimi, GPT-4o, etc.).

If no API key is configured, returns None and callers must fall back to heuristics.
"""

import json
import os
from typing import Any, Optional


def _get_client():
    api_key = os.getenv("TTC_LLM_API_KEY")
    base_url = os.getenv("TTC_LLM_BASE_URL")
    if not api_key:
        return None
    try:
        import openai
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return openai.OpenAI(**kwargs)
    except Exception:
        return None


def chat_completion(messages: list[dict[str, str]],
                    model: Optional[str] = None,
                    temperature: float = 0.3,
                    json_mode: bool = False) -> Optional[str]:
    client = _get_client()
    if not client:
        return None
    model = model or os.getenv("TTC_LLM_MODEL", "gpt-4o-mini")
    try:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content
    except Exception as exc:
        print(f"[LLM] error: {exc}")
        return None


def complete(prompt: str, model: Optional[str] = None, json_mode: bool = False) -> Optional[str]:
    return chat_completion(
        messages=[{"role": "system", "content": "You are a helpful assistant."},
                  {"role": "user", "content": prompt}],
        model=model,
        json_mode=json_mode,
    )


def parse_json_safe(text: Optional[str]) -> Optional[dict[str, Any]]:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None
