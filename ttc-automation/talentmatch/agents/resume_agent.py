"""Resume Screener Agent — extracts structured candidate profiles from resume text"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger
from .base import BaseAgent


# ── Agent-Specific Models ──────────────────────────────────────

class AgentEducation(BaseModel):
    degree: str = Field(default="", description="学位")
    institution: str = Field(default="", description="院校")
    major: str = Field(default="", description="专业")
    start_date: str = Field(default="", description="开始时间")
    end_date: str = Field(default="", description="结束时间")
    is_985: bool = Field(default=False)
    is_211: bool = Field(default=False)
    is_qs50: bool = Field(default=False)


class AgentWorkExperience(BaseModel):
    position: str = Field(default="", description="职位")
    company: str = Field(default="", description="公司")
    start_date: str = Field(default="", description="开始时间")
    end_date: str = Field(default="", description="结束时间")
    is_current: bool = Field(default=False)
    description: str = Field(default="", description="工作描述")
    company_tier: str = Field(default="", description="FAANG/大厂/独角兽/上市公司/中小型")
    level: str = Field(default="", description="职级如P6/P7/L5")
    team_size: Optional[int] = Field(default=None, description="团队规模")


class AgentProject(BaseModel):
    name: str = Field(default="", description="项目名称")
    role: str = Field(default="", description="主导/负责/参与")
    description: str = Field(default="", description="项目描述")
    tech_stack: list[str] = Field(default_factory=list, description="技术栈")
    impact: str = Field(default="", description="项目影响/成果")
    scale: str = Field(default="", description="规模如用户量/营收")


class AgentCandidateProfile(BaseModel):
    """Extracted candidate information from a resume (agent version)"""
    candidate_name: str = Field(default="", description="候选人姓名")
    email: str = Field(default="", description="邮箱")
    phone: str = Field(default="", description="电话")
    current_role: str = Field(default="", description="当前职位")
    current_company: str = Field(default="", description="当前公司")
    years_experience: int = Field(default=0, description="总工作年限")
    skills: list[str] = Field(default_factory=list, description="技术技能")
    education: list[AgentEducation] = Field(default_factory=list, description="教育背景")
    work_experience: list[AgentWorkExperience] = Field(default_factory=list, description="工作经历")
    projects: list[AgentProject] = Field(default_factory=list, description="项目经历")
    certifications: list[str] = Field(default_factory=list, description="证书")
    highlights: list[str] = Field(default_factory=list, description="亮点(3-5个最亮眼卖点)")
    summary: str = Field(default="", description="核心价值概括(50字以内)")
    career_stability: str = Field(default="", description="稳定/一般/频繁跳槽")
    tech_depth: str = Field(default="", description="浅/中/深")
    industry_tags: list[str] = Field(default_factory=list, description="行业标签")
    role_level: str = Field(default="", description="junior/mid/senior/staff/principal")
    signals: list[str] = Field(default_factory=list, description="开源贡献/技术社区等信号")
    source_file: str = Field(default="", description="简历来源文件")
    raw_text: str = Field(default="", description="原始简历文本")


RESUME_SCREENER_SYSTEM_PROMPT = """你是一位资深猎头简历分析师。从简历文本中提取结构化候选人画像。

精确提取以下内容：
1. 姓名、邮箱、电话、当前职位、当前公司
2. 工作年限（精确数字，总年限）
3. 技术技能（语言、框架、工具、平台等，分清楚）
4. 教育背景（院校、学位、专业、985/211/QS50判断）
5. 工作经历（最近2-3段，含公司档次、职级）
6. 项目经历（含技术栈、影响、规模）
7. 亮点（3-5个最亮眼的卖点，如：主导千万DAU产品、顶级会议论文等）
8. 核心价值概括（50字以内）
9. 职业稳定性: 稳定/一般/频繁跳槽
10. 技术深度: 浅/中/深
11. 行业标签（如：AI/SaaS/电商/金融/企服等）
12. 职级: junior/mid/senior/staff/principal
13. 开源贡献或技术社区信号（如果有）

只返回 JSON 对象，不包含其他文字。"""


class ResumeScreenerAgent(BaseAgent):
    """Agent that extracts structured profiles from resumes — wraps v5 ResumeParser concepts"""

    def screen(self, resume_text: str, source_file: str = "") -> tuple[AgentCandidateProfile, float]:
        """Extract structured profile from resume text.

        Returns (AgentCandidateProfile, cost_estimate).
        """
        if not resume_text or len(resume_text.strip()) < 20:
            logger.warning("Resume text too short")
            return AgentCandidateProfile(source_file=source_file, raw_text=resume_text), 0.0

        profile, cost = self.call_llm(
            system_prompt=RESUME_SCREENER_SYSTEM_PROMPT,
            user_prompt=f"分析以下简历，提取候选人画像：\n\n{resume_text[:12000]}",
            response_model=AgentCandidateProfile,
        )

        profile.source_file = source_file
        profile.raw_text = resume_text
        return profile, cost

    def screen_to_v5_dict(self, resume_text: str, source_file: str = "") -> dict:
        """Extract and return v5-format dict"""
        profile, _ = self.screen(resume_text, source_file)
        return self._to_v5_dict(profile)

    def _to_v5_dict(self, profile: AgentCandidateProfile) -> dict:
        return {
            "name": profile.candidate_name,
            "email": profile.email,
            "phone": profile.phone,
            "current_role": profile.current_role,
            "current_company": profile.current_company,
            "years_experience": profile.years_experience,
            "skills": profile.skills,
            "education": [e.model_dump() for e in profile.education],
            "work_experience": [w.model_dump() for w in profile.work_experience],
            "projects": [p.model_dump() for p in profile.projects],
            "summary": profile.summary,
            "highlights": profile.highlights,
            "career_stability": profile.career_stability,
            "tech_depth": profile.tech_depth,
            "industry_tags": profile.industry_tags,
            "role_level": profile.role_level,
            "source_file": profile.source_file,
            "raw_text": profile.raw_text[:2000],
        }
