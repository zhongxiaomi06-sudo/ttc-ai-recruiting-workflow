"""LLM utility — get client with fallback providers. Keys load from env only."""
import os

def get_llm_client():
    """Get LLM client with fallback providers. Returns (client, model) or (None, '')"""
    from openai import OpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or ""
    if not api_key:
        return None, ""

    providers = [
        {
            "api_key": api_key,
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "name": "DeepSeek"
        },
        {
            "api_key": api_key,
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus",
            "name": "DashScope-Qwen"
        },
    ]

    for provider in providers:
        try:
            client = OpenAI(
                api_key=provider["api_key"],
                base_url=provider["base_url"],
                timeout=30.0,
            )
            return client, provider["model"]
        except Exception:
            continue
    return None, ""


# Aliases for backward compatibility
_client_cache = {"client": None, "model": ""}

def get_llm():
    global _client_cache
    if _client_cache["client"] is None:
        _client_cache["client"], _client_cache["model"] = get_llm_client()
    return _client_cache["client"], _client_cache["model"]

def reset_llm():
    global _client_cache
    _client_cache = {"client": None, "model": ""}
