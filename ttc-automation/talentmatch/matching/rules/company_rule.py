"""Company background rule — applies huntou industry knowledge"""
from __future__ import annotations
from .base import MatchRule
from ..config.loader import load_config


class CompanyRule(MatchRule):
    name = "company"
    weight = 0.15

    def __init__(self):
        cfg = load_config("company_weights.json") or {}
        self.weights = cfg.get("weights", {})
        self.tier_map = cfg.get("company_tier_map", {})

    def score(self, candidate: dict, job: dict) -> float:
        company = (candidate.get("current_company") or "").strip()
        if not company:
            return 0.5

        # Direct match
        for name, w in self.weights.items():
            if name in company or company in name:
                return min(1.0, w)

        # Tier match
        for tier, companies in self.tier_map.items():
            for c in companies:
                if c in company or company in c:
                    tier_weight = self.weights.get(tier.replace("_", ""), 1.0)
                    return min(1.0, tier_weight)

        return 0.9  # unknown company → slight penalty

    def detail(self, candidate: dict, job: dict) -> dict:
        company = candidate.get("current_company", "") or ""
        for name, w in self.weights.items():
            if name in company or company in name:
                return {"company": company, "weight": w, "note": f"{name} 背景加成 {w}"}
        return {"company": company, "weight": 0.9, "note": "未知名公司"}
