"""Job requirements structured model"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class JobRequirements(BaseModel):
    """Structured job description / JD"""
    title: str = ""
    company: str = ""
    department: str = ""
    location: str = ""
    employment_type: str = ""  # 全职/兼职/实习/合同
    description: str = ""
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    min_years_experience: int = 0
    max_years_experience: Optional[int] = None
    education: str = ""
    salary_range: str = ""
    company_tier: str = ""
    industry: str = ""
    
    # Hunter-specific
    urgency: str = ""  # 紧急/一般/不急
    team_size: Optional[int] = None
    report_to: str = ""
    key_selling_points: List[str] = Field(default_factory=list)  # 给候选人说的卖点
    hidden_requirements: List[str] = Field(default_factory=list)  # 潜规则要求
    priority_level: str = ""  # P0/P1/P2
    
    raw_text: str = ""
    source: str = ""  # feishu/boss/recorder
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
