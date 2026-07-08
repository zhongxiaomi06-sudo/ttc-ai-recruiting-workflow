"""Bias Mitigator Agent — audits matches for fairness and DEI compliance"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger
from .base import BaseAgent
from .resume_agent import AgentCandidateProfile
from .match_agent import AgentMatchScore


# ── Agent-Specific Models ──────────────────────────────────────

class BiasAuditResult(BaseModel):
    """Result of a bias audit on a match evaluation"""
    is_biased: bool = Field(default=False, description="是否存在偏见")
    flagged_signals: list[str] = Field(default_factory=list, description="标记的偏见信号")
    bias_categories: list[str] = Field(default_factory=list, description="偏见类别: 学历/性别/年龄/公司/地域")
    reasoning: str = Field(default="", description="审计分析")
    mitigation_suggestion: str = Field(default="", description="改进建议")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="审计置信度")


BIAS_AUDIT_SYSTEM_PROMPT = """你是一位DEI（多元化、公平、包容）审计专家。分析候选人评估中是否存在潜在偏见。

需要标记的偏见类型：
1. 学历偏见 — 过度依赖"名校"、"QS排名"等标签，忽视实际能力
2. 公司偏见 — 唯"大厂"、"FAANG"论，忽视中小公司的高质量经验
3. 年龄偏见 — 对年轻/年长候选人的不公平判断
4. 性别偏见 — 描述中的性别化语言
5. 地域偏见 — 对特定地区的预设判断
6. 稳定性偏见 — 将合理职业变动错误判断为"频繁跳槽"

输出要求：
- 只评估推理过程，不改变匹配分数
- 给出具体的改进建议
- 输出JSON格式"""


class BiasMitigatorAgent(BaseAgent):
    """Agent that audits matches for potential bias"""

    def audit_match(
        self,
        candidate: AgentCandidateProfile,
        score: AgentMatchScore,
    ) -> tuple[BiasAuditResult, float]:
        """Audit a match evaluation for bias.

        Returns (BiasAuditResult, cost_estimate).
        """
        user_prompt = (
            f"审计以下候选人评估：\n\n"
            f"候选人: {candidate.candidate_name}\n"
            f"教育: {'; '.join(f'{e.degree}@{e.institution}(985={e.is_985},211={e.is_211},QS50={e.is_qs50})' for e in candidate.education)}\n"
            f"公司: {candidate.current_company} (档次: {candidate.current_role})\n"
            f"年限: {candidate.years_experience}年\n"
            f"稳定性: {candidate.career_stability}\n\n"
            f"匹配评分:\n"
            f"- 综合分: {score.overall_score}/100\n"
            f"- 推荐: {score.recommendation}\n"
            f"- 推理: {score.reasoning}\n"
            f"- 优势: {', '.join(score.strengths)}\n"
            f"- 风险: {', '.join(score.gaps)}\n\n"
            f"请审计是否存在偏见。"
        )

        result, cost = self.call_llm(
            system_prompt=BIAS_AUDIT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=BiasAuditResult,
        )

        return result, cost

    def mask_pii(self, profile: AgentCandidateProfile) -> AgentCandidateProfile:
        """Create a blinded version of the profile to reduce unconscious bias"""
        blinded = profile.model_copy(deep=True)
        blinded.candidate_name = "候选人 [已脱敏]"
        blinded.email = ""
        blinded.phone = ""
        return blinded

    def audit_batch(
        self,
        matches: list[tuple[AgentCandidateProfile, AgentMatchScore]],
    ) -> tuple[list[BiasAuditResult], float]:
        """Audit multiple matches.

        Returns (audit_results, total_cost).
        """
        results: list[BiasAuditResult] = []
        total_cost = 0.0

        for candidate, score in matches:
            audit, cost = self.audit_match(candidate, score)
            results.append(audit)
            total_cost += cost

        return results, total_cost
