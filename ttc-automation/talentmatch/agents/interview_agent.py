"""Interview Generator Agent — generates personalized interview plans based on candidate profiles and JD gaps"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger
from .base import BaseAgent
from .resume_agent import AgentCandidateProfile
from .jd_agent import AgentJobRequirements
from .match_agent import AgentMatchScore


# ── Agent-Specific Models ──────────────────────────────────────

class InterviewQuestion(BaseModel):
    """A single interview question"""
    question: str = Field(default="", description="面试问题")
    category: str = Field(default="", description="技术/业务/项目/软技能/系统设计")
    target_skill: str = Field(default="", description="考察的技能/能力")
    difficulty: str = Field(default="medium", description="junior/medium/senior/expert")
    expected_answer_signal: str = Field(default="", description="期望的答案信号")
    time_allocation_minutes: int = Field(default=5, description="建议用时(分钟)")


class InterviewPlan(BaseModel):
    """Complete interview plan for a candidate"""
    candidate_name: str = ""
    job_title: str = ""
    job_company: str = ""
    overall_recommendation: str = Field(default="", description="面试建议")
    focus_areas: list[str] = Field(default_factory=list, description="重点考察方向")
    questions: list[InterviewQuestion] = Field(default_factory=list, description="面试题列表")
    total_duration_minutes: int = Field(default=45, description="建议总时长")
    interview_difficulty: str = Field(default="medium", description="建议面试难度")


INTERVIEW_SYSTEM_PROMPT = """你是一位顶级科技公司的首席工程师兼面试官。为特定候选人设计60分钟的个性化技术面试。

要求：
1. 聚焦验证"匹配技能"的真实深度
2. 深入探测"缺失技能"的真正原因
3. 避免泛泛的八股文问题
4. 问题要能区分真才实学和浅尝辄止
5. 覆盖类别：技术/业务/项目/软技能
6. 给出每个问题的难度等级和期望答案信号
7. 难度根据候选人简历判断：junior/medium/senior/expert

规则：
- 编程问题：要求具体的技术深度和实现思路
- 项目问题：深挖候选人在项目中具体角色和贡献
- 业务问题：考察对行业的理解和商业敏感度
- 系统设计：候选人职级senior以上需要

只返回 JSON 对象。"""


class InterviewGeneratorAgent(BaseAgent):
    """Agent that generates personalized interview plans"""

    def generate_plan(
        self,
        candidate: AgentCandidateProfile,
        job: AgentJobRequirements,
        match_score: Optional[AgentMatchScore] = None,
    ) -> tuple[InterviewPlan, float]:
        """Generate a personalized interview plan.

        Returns (InterviewPlan, cost_estimate).
        """
        strengths_text = ", ".join(match_score.strengths[:3]) if match_score else candidate.highlights[:3]
        gaps_text = ", ".join(match_score.gaps[:3]) if match_score else "待验证"

        user_prompt = (
            f"## 候选人\n"
            f"姓名: {candidate.candidate_name}\n"
            f"当前: {candidate.current_role} @ {candidate.current_company}\n"
            f"年限: {candidate.years_experience}年\n"
            f"技能: {', '.join(candidate.skills[:15])}\n"
            f"项目: {'; '.join(f'{p.name}({p.role})' for p in candidate.projects[:3])}\n"
            f"优势: {strengths_text}\n"
            f"待验证: {gaps_text}\n"
            f"教育: {'; '.join(f'{e.degree}@{e.institution}' for e in candidate.education)}\n"
            f"技术深度: {candidate.tech_depth}\n"
            f"职级: {candidate.role_level}\n\n"
            f"## 岗位\n"
            f"职位: {job.title} @ {job.company}\n"
            f"必要技能: {', '.join(job.required_skills[:8])}\n"
            f"加分技能: {', '.join(job.preferred_skills[:5])}\n"
            f"潜规则: {', '.join(job.hidden_requirements[:3])}\n\n"
            f"请设计面试计划。"
        )

        plan, cost = self.call_llm(
            system_prompt=INTERVIEW_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=InterviewPlan,
            max_tokens=4000,
        )

        plan.candidate_name = candidate.candidate_name
        plan.job_title = job.title
        plan.job_company = job.company
        return plan, cost

    def generate_evaluation(
        self,
        plan: InterviewPlan,
        answers: list[str],
    ) -> tuple[dict, float]:
        """Evaluate candidate answers against interview plan.

        Returns (evaluation_dict, cost_estimate).
        """
        questions_summary = "\n".join(
            f"Q{i+1}. [{q.category}/{q.difficulty}] {q.question}"
            for i, q in enumerate(plan.questions)
        )
        answers_summary = "\n".join(
            f"A{i+1}. {a[:200]}" for i, a in enumerate(answers)
        )

        eval_prompt = (
            f"评估以下面试回答的质量：\n\n"
            f"面试计划:\n{questions_summary}\n\n"
            f"候选人回答:\n{answers_summary}\n\n"
            f"对每个回答从以下维度评分(1-10)：\n"
            f"- 技术准确性\n"
            f"- 逻辑清晰度\n"
            f"- 深度/洞察\n"
            f"- 行为表现\n"
            f"输出JSON: {{\"evaluations\": [{{\"question_index\": 0, \"technical_score\": 0, "
            f"\"clarity_score\": 0, \"depth_score\": 0, \"behavior_score\": 0, "
            f"\"feedback\": \"\"}}], \"overall_score\": 0, \"summary\": \"\"}}"
        )

        result, cost = self.call_llm(
            system_prompt="你是一位资深面试评估专家。评估面试回答，严格按JSON格式输出。",
            user_prompt=eval_prompt,
            max_tokens=3000,
        )

        if isinstance(result, str):
            import json
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                result = {"evaluations": [], "overall_score": 0, "summary": result[:200]}

        return result, cost
