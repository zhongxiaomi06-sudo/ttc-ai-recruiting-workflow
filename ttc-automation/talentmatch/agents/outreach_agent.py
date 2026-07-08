"""Outreach Drafter Agent — generates personalized candidate outreach emails"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger
from .base import BaseAgent
from .match_agent import AgentMatchScore
from .jd_agent import AgentJobRequirements


# ── Agent-Specific Models ──────────────────────────────────────

class OutreachDraft(BaseModel):
    """Personalized outreach message"""
    candidate_name: str = Field(default="", description="候选人姓名")
    subject: str = Field(default="", description="邮件标题/私信标题")
    body: str = Field(default="", description="外联正文")
    tone: str = Field(default="professional", description="专业/亲切/直接")
    channel: str = Field(default="", description="推荐渠道: 微信/邮件/脉脉/Boss直聘")
    timing_suggestion: str = Field(default="", description="最佳联系时间建议")


OUTREACH_DRAFTER_SYSTEM_PROMPT = """你是一位顶级的猎头外联专家，擅长写高回应率的候选人触达消息。

规则：
1. 个性化标题：提到候选人具体的项目/技能/成就
2. 开头直接引用候选人的工作（例如某个项目、开源贡献、技术栈）
3. 价值主张：为什么这个职位适合TA的职业发展（不是为什么TA适合我们）
4. 根据候选人性格调整语气：专业/亲切/直接
5. 行动号召要低压力
6. 长度控制在150字以内
7. 给出最佳联系渠道建议（根据候选人活跃度推断）
8. 给出最佳联系时间建议

只返回 JSON 对象。"""


class OutreachDrafterAgent(BaseAgent):
    """Agent that generates personalized outreach messages"""

    def draft(
        self,
        match: AgentMatchScore,
        job: AgentJobRequirements,
        tone: str = "professional",
        sender_name: str = "",
        company_name: str = "",
    ) -> tuple[OutreachDraft, float]:
        """Generate a personalized outreach message.

        Returns (OutreachDraft, cost_estimate).
        """
        user_prompt = (
            f"为以下候选人撰写个性化外联消息：\n\n"
            f"候选人: {match.candidate_name}\n"
            f"当前: {match.candidate_role} @ {match.candidate_company}\n"
            f"优势: {', '.join(match.strengths[:3])}\n"
            f"技能: {', '.join(match.matched_skills[:5])}\n\n"
            f"机会: {job.title} @ {company_name or job.company}\n"
            f"卖点: {', '.join(job.key_selling_points[:3])}\n\n"
            f"语气: {tone}\n"
            f"发件人: {sender_name or '猎头顾问'}"
        )

        draft, cost = self.call_llm(
            system_prompt=OUTREACH_DRAFTER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=OutreachDraft,
        )

        draft.candidate_name = match.candidate_name
        draft.tone = tone
        return draft, cost

    def batch_draft(
        self,
        matches: list[AgentMatchScore],
        job: AgentJobRequirements,
        tone: str = "professional",
        sender_name: str = "",
        company_name: str = "",
        top_k: int = 5,
    ) -> tuple[list[OutreachDraft], float]:
        """Generate outreach for top-k matches.

        Returns (drafts, total_cost).
        """
        drafts: list[OutreachDraft] = []
        total_cost = 0.0

        for match in matches[:top_k]:
            draft, cost = self.draft(match, job, tone, sender_name, company_name)
            drafts.append(draft)
            total_cost += cost

        return drafts, total_cost
