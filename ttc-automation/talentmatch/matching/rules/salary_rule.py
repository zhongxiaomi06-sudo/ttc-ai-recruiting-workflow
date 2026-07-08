"""Salary signal rule — detect red flags and green flags"""
from __future__ import annotations
from .base import MatchRule


class SalaryRule(MatchRule):
    name = "salary"
    weight = 0.10

    def score(self, candidate: dict, job: dict) -> float:
        salary_range = job.get("salary_range", "") or ""
        c_salary_current = candidate.get("salary_current", "") or ""
        c_salary_expected = candidate.get("salary_expected", "") or ""

        # Extract numbers
        c_val = self._extract_salary(c_salary_expected) or self._extract_salary(c_salary_current)
        j_val = self._extract_salary(salary_range)

        if not c_val or not j_val:
            return 0.6  # can't tell

        ratio = c_val / j_val if j_val > 0 else 1.0

        if 0.8 <= ratio <= 1.2:
            return 1.0  # in range
        elif ratio > 1.5:
            return 0.3  # significantly above range
        elif ratio < 0.5:
            return 0.5  # significantly below — could be ok
        elif ratio > 1.2:
            return 0.7  # slightly above
        elif ratio < 0.8:
            return 0.8  # slightly below
        return 0.6

    def _extract_salary(self, text: str) -> float:
        """Extract numeric monthly salary in K from text like '40-70K·16薪'"""
        if not text:
            return 0.0
        import re
        nums = re.findall(r'(\d+\.?\d*)', text.replace("万", "000").replace("k", "K"))
        if not nums:
            return 0.0
        vals = [float(n) for n in nums if float(n) > 0]
        if not vals:
            return 0.0
        avg = sum(vals) / len(vals)
        # Normalize to monthly K
        if "万" in text or "万" in text:
            avg = avg / 12  # annual in 万 → monthly K
        if avg > 500:
            avg = avg / 12  # likely annual
        return avg if avg > 0 else 0.0

    def detail(self, candidate: dict, job: dict) -> dict:
        return {
            "candidate_expected": candidate.get("salary_expected", ""),
            "candidate_current": candidate.get("salary_current", ""),
            "job_range": job.get("salary_range", ""),
        }
