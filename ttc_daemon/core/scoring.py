"""评分与话术核心。"""
import json
import logging
import os
from typing import Dict, Any, List

from ..llm_utils import is_llm_ready, call_llm_json
from .talentmatch_scoring import score_with_talentmatch

logger = logging.getLogger(__name__)


def _heuristic_score_candidate(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> Dict[str, Any]:
    jd_alignment = candidate.get("jd_alignment_score", 0) or 0
    gold = candidate.get("gold_score")
    if gold in (None, "", 0, 0.0):
        overall = round(jd_alignment, 1)
    else:
        overall = round(jd_alignment * 0.6 + float(gold) * 0.4, 1)
    candidate["overall_score"] = overall
    candidate["risk_flags"] = candidate.get("risk_flags", [])
    candidate.setdefault("score_provider", "heuristic")
    return candidate


def _llm_score_candidate(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> Dict[str, Any]:
    system_prompt = (
        "你是资深猎头评分专家。请根据 JD 与候选人信息做结构化匹配评分。"
        "必须返回 JSON，不要输出解释性散文。"
    )
    user_prompt = f"""
请评估候选人与 JD 的匹配度，输出 JSON：
{{
  "overall_score": 0-100,
  "gold_score": 0-100,
  "jd_alignment_score": 0-100,
  "risk_flags": ["风险点"],
  "match_reasons": ["推荐理由"],
  "verification_questions": ["电话中需要验证的问题"]
}}

JD:
{json.dumps(jd_fields, ensure_ascii=False)[:3000]}

Candidate:
{json.dumps(candidate, ensure_ascii=False)[:5000]}
"""
    result = call_llm_json(system_prompt, user_prompt, temperature=0)
    overall = float(result.get("overall_score", 0) or 0)
    candidate["overall_score"] = round(max(0, min(100, overall)), 1)
    candidate["gold_score"] = result.get("gold_score", candidate.get("gold_score", 0))
    candidate["jd_alignment_score"] = result.get(
        "jd_alignment_score", candidate.get("jd_alignment_score", 0)
    )
    candidate["risk_flags"] = result.get("risk_flags") or candidate.get("risk_flags", [])
    candidate["match_reasons"] = result.get("match_reasons", [])
    candidate["verification_questions"] = result.get("verification_questions", [])
    candidate["score_provider"] = "llm"
    return candidate


def score_candidate(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> Dict[str, Any]:
    """综合评分：provider 优先，失败回退启发式。"""
    provider = os.getenv("TTC_SCORING_PROVIDER", "heuristic").lower()
    if provider in {"talentmatch", "goldscore", "auto"}:
        try:
            return score_with_talentmatch(candidate, jd_fields, provider=provider)
        except Exception as e:
            logger.warning("TalentMatch scoring failed; falling back: %s", e)
    if provider in {"llm", "auto"} and is_llm_ready():
        try:
            return _llm_score_candidate(candidate, jd_fields)
        except Exception as e:
            logger.warning("LLM scoring failed; falling back to heuristic: %s", e)
    return _heuristic_score_candidate(candidate, jd_fields)


def generate_talking_points(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> List[str]:
    name = candidate.get("name", "候选人")
    return [
        f"向 {name} 介绍 {jd_fields.get('company', '客户')} 的 {jd_fields.get('position', '岗位')} 机会",
        f"确认当前状态：{candidate.get('current_status', '未知')}",
        "询问对地点、薪资、技术栈的匹配度",
        "了解近期是否有换工作意向",
    ]


def build_call_script(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> str:
    name = candidate.get("name", "候选人")
    company = jd_fields.get("company", "客户") or "客户"
    position = jd_fields.get("position", "岗位") or "岗位"
    return (
        f"{name} 您好，我是 TTC 猎头顾问。我们这边有一个 {company} 的 {position} 机会，"
        f"想跟您简单聊聊是否感兴趣。您现在方便吗？"
    )
