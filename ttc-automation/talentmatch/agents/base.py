"""Base agent class — adapted from agent-recruiter (MIT), uses v5 llm_utils"""
from __future__ import annotations
import json
import time
import hashlib
from typing import Optional, Type, TypeVar, Any
from loguru import logger

T = TypeVar("T")

# ── Agent Cache ──────────────────────────────────────

class AgentCache:
    """Simple in-memory cache for agent invocations — reduces redundant LLM calls"""

    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict = {}
        self._ttl = ttl_seconds

    def _key(self, text: str, prefix: str = "") -> str:
        return hashlib.md5(f"{prefix}:{text}".encode()).hexdigest()

    def get(self, text: str, prefix: str = "") -> Optional[dict]:
        key = self._key(text, prefix)
        entry = self._store.get(key)
        if entry and time.time() < entry["expires"]:
            return entry["data"]
        if entry:
            del self._store[key]
        return None

    def set(self, text: str, prefix: str, data: dict):
        key = self._key(text, prefix)
        self._store[key] = {"data": data, "expires": time.time() + self._ttl}

    def clear(self):
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


class BaseAgent:
    """Foundational agent — wraps v5 llm_utils.get_llm() with retry, JSON mode, and cache"""

    def __init__(self, model: str = "", temperature: float = 0.1, use_cache: bool = True):
        self.model = model
        self.temperature = temperature
        self.cache = AgentCache() if use_cache else None
        self._stats = {"calls": 0, "cache_hits": 0, "errors": 0}

    # ── Properties ──────────────────────────────────────

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    # ── Core LLM Call ──────────────────────────────────────

    def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Optional[Type[T]] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 3000,
    ) -> tuple[Any, float]:
        """Call LLM via v5 llm_utils and optionally parse into a model.

        Returns (parsed_model_or_raw_text, cost_estimate).
        Cost estimate is rough: $0.15/M tokens input, $0.60/M tokens output.
        """
        from resume_parser.llm_utils import get_llm

        # Cache check
        cache_key = f"{system_prompt[:50]}:{user_prompt[:200]}"
        if self.cache:
            cached = self.cache.get(cache_key, "llm")
            if cached:
                self._stats["cache_hits"] += 1
                if response_model and isinstance(cached, dict):
                    return response_model(**cached), 0.0
                return cached, 0.0

        client, model = get_llm()
        if not client:
            logger.error("No LLM client available")
            self._stats["errors"] += 1
            return (response_model() if response_model else "", 0.0)

        use_model = self.model or model
        temp = temperature if temperature is not None else self.temperature

        try:
            kwargs = {"model": use_model, "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ], "temperature": temp, "max_tokens": max_tokens}

            # Use JSON mode if response_model is provided
            if response_model:
                kwargs["response_format"] = {"type": "json_object"}

            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""

            # Estimate cost
            prompt_tokens = resp.usage.prompt_tokens if resp.usage else 0
            completion_tokens = resp.usage.completion_tokens if resp.usage else 0
            cost = (prompt_tokens * 0.15 + completion_tokens * 0.60) / 1_000_000

            self._stats["calls"] += 1

            if response_model:
                try:
                    # Clean markdown fences if present
                    clean = content.strip()
                    if clean.startswith("```"):
                        clean = clean.split("\n", 1)[-1]
                        clean = clean.rsplit("```", 1)[0].strip()
                    result = response_model.model_validate_json(clean)
                    if self.cache:
                        self.cache.set(cache_key, "llm", result.model_dump())
                    return result, cost
                except Exception as e:
                    logger.error(f"Failed to parse LLM response into {response_model.__name__}: {e}")
                    logger.debug(f"Raw content (first 500): {content[:500]}")
                    self._stats["errors"] += 1
                    return (response_model() if response_model else content), cost

            # Raw text response
            if self.cache:
                self.cache.set(cache_key, "llm", {"_text": content})
            return content, cost

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            self._stats["errors"] += 1
            from resume_parser.llm_utils import reset_llm
            reset_llm()
            return (response_model() if response_model else "", 0.0)

    def reset_stats(self):
        self._stats = {"calls": 0, "cache_hits": 0, "errors": 0}
