"""Experience matching rule — years + depth + role relevance"""
from __future__ import annotations
from .base import MatchRule


class ExperienceRule(MatchRule):
    name = "experience"
    weight = 0.20

    def score(self, candidate: dict, job: dict) -> float:
        c_exp = candidate.get("years_experience", 0) or 0
        min_req = job.get("min_years_experience", 0) or 0
        max_req = job.get("max_years_experience")  # optional

        if min_req == 0:
            return 0.7  # no requirement

        if c_exp >= min_req:
            if max_req and c_exp > max_req:
                # overqualified
                return max(0.5, 1.0 - (c_exp - max_req) / max_req * 0.2)
            return 1.0

        # underqualified — progressive penalty
        gap = (min_req - c_exp) / min_req
        return max(0.0, 1.0 - gap * 1.5)

    def detail(self, candidate: dict, job: dict) -> dict:
        return {
            "candidate_years": candidate.get("years_experience", 0),
            "required_min": job.get("min_years_experience", 0),
            "required_max": job.get("max_years_experience"),
        }
