"""Pydantic models for resume parsing - industry-grade with full validation"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class ContactInfo(BaseModel):
    email: str = ""
    phone: str = ""
    wechat: str = ""
    linkedin: str = ""
    location: str = ""


class Education(BaseModel):
    degree: str = ""
    institution: str = ""
    major: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: Optional[str] = None
    is_985: bool = False
    is_211: bool = False
    is_qs50: bool = False


class WorkExperience(BaseModel):
    position: str = ""
    company: str = ""
    start_date: str = ""
    end_date: str = ""
    is_current: bool = False
    description: str = ""
    company_tier: str = ""  # FAANG/大厂/独角兽/上市公司/中小型
    level: str = ""  # P6/P7/L5 etc.
    team_size: Optional[int] = None
    report_to: str = ""


class Project(BaseModel):
    name: str = ""
    role: str = ""  # 主导/负责/参与
    description: str = ""
    tech_stack: List[str] = Field(default_factory=list)
    impact: str = ""
    scale: str = ""  # 用户量/营收等


class SkillGroup(BaseModel):
    ai_ml: List[str] = Field(default_factory=list)
    backend: List[str] = Field(default_factory=list)
    frontend: List[str] = Field(default_factory=list)
    cloud_devops: List[str] = Field(default_factory=list)
    data: List[str] = Field(default_factory=list)
    mobile: List[str] = Field(default_factory=list)
    product: List[str] = Field(default_factory=list)
    management: List[str] = Field(default_factory=list)
    other: List[str] = Field(default_factory=list)


class SalarySignal(BaseModel):
    current: Optional[str] = None
    expected: Optional[str] = None
    currency: str = "CNY"


class ResumeOutput(BaseModel):
    """Complete structured candidate profile"""
    candidate_name: str = ""
    @property
    def name(self) -> str:
        return self.candidate_name
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    current_role: str = ""
    current_company: str = ""
    years_experience: int = 0
    education: List[Education] = Field(default_factory=list)
    work_experience: List[WorkExperience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    skills_classified: SkillGroup = Field(default_factory=SkillGroup)
    certifications: List[str] = Field(default_factory=list)
    salary_signal: SalarySignal = Field(default_factory=SalarySignal)
    summary: str = ""
    highlights: List[str] = Field(default_factory=list)
    raw_text: str = ""
    source_file: str = ""
    ats_score: float = 0.0
    parsed_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Hunter-specific fields
    career_stability: str = ""  # 稳定/一般/频繁跳槽
    tech_depth: str = ""  # 浅/中/深
    industry_tags: List[str] = Field(default_factory=list)
    role_level: str = ""  # junior/mid/senior/staff/principal
