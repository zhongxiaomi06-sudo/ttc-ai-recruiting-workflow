"""Match score model"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional


class MatchScore(BaseModel):
    """Candidate-Job match result"""
    candidate_id: str = ""
    candidate_name: str = ""
    job_id: str = ""
    job_title: str = ""
    overall_score: float = 0.0
    skill_score: float = 0.0
    experience_score: float = 0.0
    education_score: float = 0.0
    project_score: float = 0.0
    signal_score: float = 0.0
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    reasoning: str = ""
    recommendation: str = ""  # 强推/推荐/可考虑/不推荐
