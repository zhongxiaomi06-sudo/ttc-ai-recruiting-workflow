"""Skill matching rule — keyword + normalization + bonus combos"""
from __future__ import annotations
import json
import os
from typing import List
from .base import MatchRule
from ..skill_normalizer import normalize_skills
from ..config.loader import load_config


class SkillRule(MatchRule):
    name = "skill"
    weight = 0.35

    def __init__(self):
        self.bonus_config = load_config("skill_bonus.json") or {}

    def score(self, candidate: dict, job: dict) -> float:
        c_skills = normalize_skills(candidate.get("skills", []))
        r_skills = normalize_skills(job.get("required_skills", []))
        p_skills = normalize_skills(job.get("preferred_skills", []))

        if not r_skills and not p_skills:
            return 0.7  # no skill requirement → neutral

        matched_req = [s for s in c_skills if s.lower() in [x.lower() for x in r_skills]]
        matched_pref = [s for s in c_skills if s.lower() in [x.lower() for x in p_skills]]

        req_score = len(matched_req) / len(r_skills) if r_skills else 1.0
        pref_score = len(matched_pref) / len(p_skills) if p_skills else 0.5

        base = 0.7 * req_score + 0.3 * pref_score

        # Bonus for high-value skill combos
        bonus = self._compute_bonus(c_skills)
        return min(1.0, base + bonus)

    def _compute_bonus(self, skills: List[str]) -> float:
        bonus = 0.0
        skill_bonus = self.bonus_config.get("skill_bonus", {})
        for s in skills:
            multiplier = skill_bonus.get(s, 1.0)
            if multiplier > 1.0:
                bonus += (multiplier - 1.0) * 0.05

        # High-value combos
        high_combos = self.bonus_config.get("high_value_combos", [])
        skill_set = set(s.lower() for s in skills)
        for combo in high_combos:
            if all(c.lower() in skill_set for c in combo):
                bonus += 0.08
        return min(bonus, 0.3)

    def detail(self, candidate: dict, job: dict) -> dict:
        c_skills = normalize_skills(candidate.get("skills", []))
        r_skills = normalize_skills(job.get("required_skills", []))
        p_skills = normalize_skills(job.get("preferred_skills", []))
        matched_req = [s for s in c_skills if s.lower() in [x.lower() for x in r_skills]]
        matched_pref = [s for s in c_skills if s.lower() in [x.lower() for x in p_skills]]
        missing = [s for s in r_skills if s.lower() not in [x.lower() for x in c_skills]]
        return {
            "matched_skills": matched_req + matched_pref,
            "missing_skills": missing,
        }
