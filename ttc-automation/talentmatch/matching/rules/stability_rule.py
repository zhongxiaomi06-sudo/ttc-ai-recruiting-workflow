"""Stability rule — job-hopping frequency penalty"""
from __future__ import annotations
from .base import MatchRule
from ..config.loader import load_config


class StabilityRule(MatchRule):
    name = "stability"
    weight = 0.20  # 三好标准: 稳定性权重提升至20%

    def __init__(self):
        cfg = load_config("stability_rules.json") or {}
        self.rules = cfg.get("rules", [])

    def score(self, candidate: dict, job: dict) -> float:
        # Use career_stability field if available
        stability = candidate.get("career_stability", "") or ""
        if stability == "稳定":
            return 0.85
        elif stability == "一般":
            return 0.60
        elif stability == "频繁跳槽":
            return 0.30

        # Auto-calculate from work_experience
        work = candidate.get("work_experience", [])
        if isinstance(work, str):
            import json
            try:
                work = json.loads(work)
            except Exception:
                work = []

        if not work or not isinstance(work, list):
            return 0.65  # no data → neutral

        return self._score_from_work_history(work)

    def _score_from_work_history(self, work: list) -> float:
        import re
        # Count jobs and estimate duration
        job_count = len(work)
        if job_count <= 1:
            return 0.80  # single job → stable or junior

        # Simple heuristic: more jobs in recent years = less stable
        if job_count >= 5:
            return 0.30
        elif job_count >= 4:
            return 0.45
        elif job_count >= 3:
            return 0.60
        elif job_count == 2:
            return 0.75
        return 0.65

    def detail(self, candidate: dict, job: dict) -> dict:
        work = candidate.get("work_experience", [])
        if isinstance(work, str):
            import json
            try:
                work = json.loads(work)
            except Exception:
                work = []
        return {
            "job_count": len(work) if isinstance(work, list) else 0,
            "career_stability": candidate.get("career_stability", ""),
        }
