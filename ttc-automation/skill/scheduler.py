"""Skill search scheduler: dispatch executors, merge, dedupe, score, rank."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from .executors.base import BaseExecutor
from .executors.internal_db import InternalDBExecutor
from .executors.mock import MockExecutor
from .models import Candidate, SearchIntent


class SkillScheduler:
    """Run multiple executors in parallel and merge their results."""

    def __init__(self, executors: List[BaseExecutor] | None = None):
        self.executors = executors or [InternalDBExecutor(), MockExecutor()]

    async def search(
        self,
        intent: SearchIntent,
        max_results: int = 10,
        include_mock: bool = False,
    ) -> tuple[List[Candidate], Dict[str, Any]]:
        """Return ranked candidates plus raw per-executor results."""

        async def _run_one(exe: BaseExecutor) -> tuple[str, List[Candidate], str]:
            try:
                results = await asyncio.wait_for(
                    exe.search(intent, limit=max_results * 2),
                    timeout=15.0,
                )
                return (exe.name, results, "")
            except Exception as exc:
                return (exe.name, [], str(exc))

        raw_results: Dict[str, Any] = {}
        tasks = [_run_one(exe) for exe in self.executors]
        for name, results, error in await asyncio.gather(*tasks):
            raw_results[name] = {"count": len(results), "error": error}
            if error:
                raw_results[name]["results"] = []
            else:
                raw_results[name]["results"] = [c.model_dump() for c in results]

        # Collect real results first
        all_candidates: List[Candidate] = []
        for exe in self.executors:
            if exe.name == "mock" and not include_mock:
                continue
            name = exe.name
            if name in raw_results and not raw_results[name].get("error"):
                all_candidates.extend(raw_results[name].get("results", []))

        # If no real results and mock allowed, use mock
        if not all_candidates and include_mock:
            for exe in self.executors:
                if exe.name == "mock":
                    all_candidates.extend(raw_results.get(exe.name, {}).get("results", []))

        # Deduplicate by (name, current_company)
        seen = set()
        deduped = []
        for c in all_candidates:
            if not isinstance(c, Candidate):
                # Rehydrate from dict if coming from raw_results
                c = Candidate(**c)
            key = (c.name, c.current_company)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)

        # Sort by overall_score desc
        deduped.sort(key=lambda x: x.overall_score, reverse=True)

        return deduped[:max_results], raw_results


def get_default_scheduler() -> SkillScheduler:
    """Return scheduler with default executors."""
    return SkillScheduler()
