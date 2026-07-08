"""JD Parser Agent — extracts structured job requirements from unstructured JD text"""
from __future__ import annotations
import logging
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger
from .base import BaseAgent

# ── Agent-Specific Models ──────────────────────────────────────

class AgentJobRequirements(BaseModel):
    """Structured job description — extended with hunter-specific fields"""
    title: str = Field(default="", description="职位名称")
    company: str = Field(default="", description="公司名称")
    team: str = Field(default="", description="具体团队或部门")
    department: str = Field(default="", description="所属部门")
    location: str = Field(default="", description="工作地点")
    employment_type: str = Field(default="", description="全职/兼职/实习/合同")
    description: str = Field(default="", description="职位概述")
    required_skills: list[str] = Field(default_factory=list, description="必要技能")
    preferred_skills: list[str] = Field(default_factory=list, description="加分技能")
    min_years_experience: int = Field(default=0, description="最低工作年限")
    max_years_experience: Optional[int] = Field(default=None, description="最高目标年限")
    education: str = Field(default="", description="学历要求")
    salary_range: str = Field(default="", description="薪资范围")
    company_tier: str = Field(default="", description="FAANG/大厂/独角兽/上市公司/中小型")
    industry: str = Field(default="", description="行业")
    urgency: str = Field(default="", description="紧急/一般/不急")
    priority_level: str = Field(default="", description="P0=紧急核心岗/P1=重要岗/P2=普通岗")
    key_selling_points: list[str] = Field(default_factory=list, description="候选人卖点")
    hidden_requirements: list[str] = Field(default_factory=list, description="潜规则要求")
    responsibilities: list[str] = Field(default_factory=list, description="岗位职责")
    raw_text: str = Field(default="", description="原始JD文本")

    def summary(self) -> str:
        parts = [f"Title: {self.title}"]
        if self.company:
            parts.append(f"Company: {self.company}")
        parts.append(f"Required: {', '.join(self.required_skills[:8])}")
        if self.preferred_skills:
            parts.append(f"Preferred: {', '.join(self.preferred_skills[:5])}")
        parts.append(f"Experience: {self.min_years_experience}+ years")
        return "\n".join(parts)


JD_PARSER_SYSTEM_PROMPT = """你是一位资深猎头JD分析师。从岗位需求文本中提取结构化信息。

精确提取以下内容：
1. 职位名称、公司、部门、工作地点、用工形式
2. 必要技能 vs 加分技能 (严格区分)
3. 工作年限要求（提取具体数字，如果是范围取最小值）
4. 学历要求
5. 薪资范围（如果有）
6. 公司档次: FAANG/大厂/独角兽/上市公司/中小型
7. 紧急程度: 紧急/一般/不急
8. 优先级: P0=紧急核心岗/P1=重要岗/P2=普通岗
9. key_selling_points: 可以用来吸引候选人的卖点
10. hidden_requirements: JD中没明说但实际很重要的要求（猎头潜规则）
11. 岗位职责

只返回 JSON 对象，不包含其他文字。"""


class JDParserAgent(BaseAgent):
    """Agent that handles job description parsing — wraps v5 JobParser"""

    def parse(self, jd_text: str, source: str = "") -> tuple[AgentJobRequirements, float]:
        """Parse JD text into structured requirements.

        Returns (AgentJobRequirements, cost_estimate).
        """
        if not jd_text or len(jd_text.strip()) < 10:
            logger.warning("JD text too short")
            return AgentJobRequirements(raw_text=jd_text, description="JD文本过短"), 0.0

        requirements, cost = self.call_llm(
            system_prompt=JD_PARSER_SYSTEM_PROMPT,
            user_prompt=f"分析以下岗位需求，提取结构化信息：\n\n{jd_text[:8000]}",
            response_model=AgentJobRequirements,
        )

        requirements.raw_text = jd_text
        return requirements, cost

    def parse_sync_to_v5(self, jd_text: str, source: str = "") -> dict:
        """Parse JD and return v5-format dict (compatible with storage.db.save_job)"""
        req, _ = self.parse(jd_text, source)
        return self._to_v5_dict(req, source)

    def _to_v5_dict(self, req: AgentJobRequirements, source: str = "") -> dict:
        return {
            "title": req.title,
            "company": req.company,
            "department": req.department or req.team,
            "location": req.location,
            "employment_type": req.employment_type,
            "description": req.description,
            "required_skills": req.required_skills,
            "preferred_skills": req.preferred_skills,
            "min_years_experience": req.min_years_experience,
            "max_years_experience": req.max_years_experience,
            "education": req.education,
            "salary_range": req.salary_range,
            "company_tier": req.company_tier,
            "industry": req.industry,
            "urgency": req.urgency,
            "priority_level": req.priority_level,
            "key_selling_points": req.key_selling_points,
            "hidden_requirements": req.hidden_requirements,
            "raw_text": req.raw_text[:2000],
            "source": source,
        }
