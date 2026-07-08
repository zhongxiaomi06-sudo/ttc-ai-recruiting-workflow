"""Base rule class — all match rules inherit from this"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class MatchRule(ABC):
    """A single dimension of candidate-job matching.

    Each rule:
    - Takes a candidate dict and a job dict
    - Returns a score in [0.0, 1.0]
    - Can return supporting info (matched items, reasons)
    """

    name: str = ""        # Rule identifier
    weight: float = 1.0   # Default weight, overridden by config

    @abstractmethod
    def score(self, candidate: dict, job: dict) -> float:
        ...

    def detail(self, candidate: dict, job: dict) -> dict:
        """Optional extra info — matched skills, missing skills, etc."""
        return {}


class RuleResult:
    """Aggregated result from all rules"""
    def __init__(self):
        self.scores: Dict[str, float] = {}
        self.details: Dict[str, dict] = {}
        self.total_weight: float = 0.0
        self.final_score: float = 0.0
        self.recommendation: str = ""

    def compute(self, rules: List[MatchRule], candidate: dict, job: dict,
                weight_overrides: Dict[str, float] = None):
        weight_overrides = weight_overrides or {}
        weighted_sum = 0.0
        total_weight = 0.0

        for rule in rules:
            w = weight_overrides.get(rule.name, rule.weight)
            try:
                s = rule.score(candidate, job)
            except Exception:
                s = 0.5  # safe fallback
            self.scores[rule.name] = s
            self.details[rule.name] = rule.detail(candidate, job)
            weighted_sum += s * w
            total_weight += w

        self.total_weight = total_weight
        self.final_score = weighted_sum / total_weight if total_weight > 0 else 0.5
        self.final_score = max(0.0, min(1.0, self.final_score))

        if self.final_score >= 0.85:
            self.recommendation = "强推"
        elif self.final_score >= 0.70:
            self.recommendation = "推荐"
        elif self.final_score >= 0.50:
            self.recommendation = "可考虑"
        else:
            self.recommendation = "不推荐"

        return self
