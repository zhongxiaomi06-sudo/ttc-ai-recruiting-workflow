"""Match Scorer Agent — multi-dimensional candidate-job matching with hunter rules"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger
from .base import BaseAgent
from .resume_agent import AgentCandidateProfile
from .jd_agent import AgentJobRequirements


# ── Agent-Specific Models ──────────────────────────────────────

class AgentMatchScore(BaseModel):
    """Multi-dimensional match score for a candidate-job pair"""
    candidate_name: str = ""
    candidate_role: str = ""
    candidate_company: str = ""
    job_title: str = ""
    job_company: str = ""

    overall_score: float = Field(default=0.0, ge=0.0, le=100.0, description="综合匹配分(0-100)")
    skill_score: float = Field(default=0.0, description="技能匹配分")
    experience_score: float = Field(default=0.0, description="经验匹配分")
    education_score: float = Field(default=0.0, description="教育匹配分")
    project_score: float = Field(default=0.0, description="项目匹配分")
    signal_score: float = Field(default=0.0, description="信号/亮点分")
    hunter_bonus: float = Field(default=0.0, description="猎头潜规则调整分")

    matched_skills: list[str] = Field(default_factory=list, description="匹配的技能")
    missing_skills: list[str] = Field(default_factory=list, description="缺失的必要技能")

    strengths: list[str] = Field(default_factory=list, description="核心优势(3-5条)")
    gaps: list[str] = Field(default_factory=list, description="潜在风险(2-3条)")
    reasoning: str = Field(default="", description="匹配分析")
    recommendation: str = Field(default="", description="强推/推荐/可考虑/不推荐")

    @property
    def score_bar(self) -> str:
        filled = int(self.overall_score / 5)
        empty = 20 - filled
        return "█" * filled + "░" * empty


MATCH_ANALYSIS_PROMPT = """你是一位资深猎头招聘分析师。评估候选人与岗位的匹配度，输出结构化JSON。

分析维度：
1. 技能匹配 (40%) — 候选人技能与必要/加分技能的对齐度
2. 经验匹配 (25%) — 工作年限、职级是否在目标范围内
3. 教育匹配 (10%) — 学历背景是否满足要求
4. 项目/背景匹配 (15%) — 项目经历与岗位职责的关联度
5. 信号/亮点匹配 (10%) — 行业影响、亮点卖点与岗位的契合度
6. 猎头潜规则 (bonus) — 公司档次、职业稳定性、985/211等

猎头潜规则：
- 985/211/Q50 → +3~5分
- FAANG/大厂背景 → +5~10分
- 频繁跳槽(3年内>2家) → -5~10分
- 名校但经验不足 → 酌情
- 行业垂直经验 → +5分

推荐标准：
- ≥85: 强推 (🔥)
- 70-84: 推荐 (✅)
- 50-69: 可考虑 (🤔)
- <50: 不推荐 (❌)

输出JSON格式（严格遵循）：
{
  "overall_score": 0-100,
  "skill_score": 0-100,
  "experience_score": 0-100,
  "education_score": 0-100,
  "project_score": 0-100,
  "signal_score": 0-100,
  "hunter_bonus": -10 to 15,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3"],
  "strengths": ["优势1", "优势2"],
  "gaps": ["风险1", "风险2"],
  "reasoning": "综合分析（100字以内）",
  "recommendation": "强推/推荐/可考虑/不推荐"
}"""


class MatchScorerAgent(BaseAgent):
    """Agent that evaluates candidate-job match scores with hunter domain knowledge"""

    def __init__(self, model: str = "", temperature: float = 0.1, use_llm_analysis: bool = True, use_cache: bool = True):
        super().__init__(model=model, temperature=temperature, use_cache=use_cache)
        self.use_llm_analysis = use_llm_analysis

    def score(
        self,
        candidate: AgentCandidateProfile,
        job: AgentJobRequirements,
    ) -> tuple[AgentMatchScore, float]:
        """Score a candidate against a job, with both fast rule-based and deep LLM analysis.

        Returns (AgentMatchScore, cost_estimate).
        """
        # Step 1: Fast rule-based score (from v5 MatchEngine)
        base_score = self._fast_rule_score(candidate, job)

        # Step 2: Deep LLM analysis (if enabled)
        if self.use_llm_analysis:
            llm_score, cost = self._llm_deep_score(candidate, job)
            # Blend: 60% rule + 40% LLM, but use LLM for strengths/gaps
            blended = AgentMatchScore(
                candidate_name=candidate.candidate_name,
                candidate_role=candidate.current_role,
                candidate_company=candidate.current_company,
                job_title=job.title,
                job_company=job.company,
                overall_score=round(base_score.overall_score * 0.6 + llm_score.overall_score * 0.4, 1),
                skill_score=round(base_score.skill_score * 0.5 + llm_score.skill_score * 0.5, 1),
                experience_score=round(base_score.experience_score * 0.7 + llm_score.experience_score * 0.3, 1),
                education_score=round(base_score.education_score * 0.8 + llm_score.education_score * 0.2, 1),
                project_score=round(base_score.project_score * 0.6 + llm_score.project_score * 0.4, 1),
                signal_score=max(base_score.signal_score, llm_score.signal_score),
                hunter_bonus=llm_score.hunter_bonus,
                matched_skills=llm_score.matched_skills or base_score.matched_skills,
                missing_skills=llm_score.missing_skills or base_score.missing_skills,
                strengths=llm_score.strengths or base_score.strengths,
                gaps=llm_score.gaps or base_score.gaps,
                reasoning=llm_score.reasoning or base_score.reasoning,
                recommendation=llm_score.recommendation or base_score.recommendation,
            )
            return blended, cost

        return base_score, 0.0

    def _fast_rule_score(self, candidate: AgentCandidateProfile, job: AgentJobRequirements) -> AgentMatchScore:
        """Fast rule-based scoring — ported from v5 MatchEngine.compute_match()"""
        from matching.unified_engine import UnifiedMatchEngine, candidate_from_storage, job_from_storage
        engine = UnifiedMatchEngine()
        cand_dict = candidate.model_dump()
        job_dict = {
            "title": job.title,
            "company": job.company,
            "required_skills": job.required_skills,
            "preferred_skills": job.preferred_skills,
            "min_years_experience": job.min_years_experience,
            "max_years_experience": job.max_years_experience,
            "education": job.education,
        }
        cv = candidate_from_storage(dict(cand_dict, id=cand_dict.get("name", "unknown")))
        jv = job_from_storage(job_dict)
        result = engine.compute_match(cv, jv)

        # Map 0-1 range to 0-100
        dim_map = {d.name: d.score for d in result.dimensions}
        return AgentMatchScore(
            candidate_name=candidate.candidate_name,
            candidate_role=candidate.current_role,
            candidate_company=candidate.current_company,
            job_title=job.title,
            job_company=job.company,
            overall_score=round(result.overall_score * 100, 1),
            skill_score=round(dim_map.get("skill_match", 0.5) * 100, 1),
            experience_score=round(dim_map.get("experience", 0.5) * 100, 1),
            education_score=round(dim_map.get("education", 0.5) * 100, 1),
            project_score=round(dim_map.get("stability", 0.5) * 100, 1),
            signal_score=round(dim_map.get("company_tier", 0.5) * 100, 1),
            matched_skills=result.matched_skills,
            missing_skills=result.missing_skills,
            strengths=result.matched_skills,
            gaps=result.missing_skills,
            reasoning=result.explanation,
            recommendation=result.recommendation,
        )

    def _llm_deep_score(self, candidate: AgentCandidateProfile, job: AgentJobRequirements) -> tuple[AgentMatchScore, float]:
        """Deep LLM-powered match analysis"""
        user_prompt = (
            f"## 候选人\n"
            f"姓名: {candidate.candidate_name}\n"
            f"当前职位: {candidate.current_role} @ {candidate.current_company}\n"
            f"工作年限: {candidate.years_experience}年\n"
            f"技能: {', '.join(candidate.skills[:15])}\n"
            f"教育: {'; '.join(f'{e.degree}@{e.institution}' for e in candidate.education)}\n"
            f"亮点: {', '.join(candidate.highlights[:5])}\n"
            f"稳定性: {candidate.career_stability}\n"
            f"技术深度: {candidate.tech_depth}\n\n"
            f"## 岗位\n"
            f"职位: {job.title} @ {job.company}\n"
            f"必要技能: {', '.join(job.required_skills[:10])}\n"
            f"加分技能: {', '.join(job.preferred_skills[:5])}\n"
            f"经验要求: {job.min_years_experience}-{job.max_years_experience or '不限'}年\n"
            f"学历要求: {job.education}\n"
            f"潜规则: {', '.join(job.hidden_requirements[:3])}\n\n"
            f"请评估匹配度，严格按JSON格式返回。"
        )

        result, cost = self.call_llm(
            system_prompt=MATCH_ANALYSIS_PROMPT,
            user_prompt=user_prompt,
            response_model=AgentMatchScore,
        )

        result.candidate_name = candidate.candidate_name
        result.candidate_role = candidate.current_role
        result.candidate_company = candidate.current_company
        result.job_title = job.title
        result.job_company = job.company

        return result, cost

    def batch_score(
        self,
        candidates: list[AgentCandidateProfile],
        job: AgentJobRequirements,
        top_k: int = 10,
    ) -> tuple[list[AgentMatchScore], float]:
        """Score multiple candidates against one job.

        Returns (sorted_scores, total_cost).
        """
        results: list[AgentMatchScore] = []
        total_cost = 0.0

        for c in candidates:
            score, cost = self.score(c, job)
            results.append(score)
            total_cost += cost

        results.sort(key=lambda s: s.overall_score, reverse=True)
        return results[:top_k], total_cost
