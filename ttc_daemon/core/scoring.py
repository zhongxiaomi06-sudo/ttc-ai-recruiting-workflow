"""评分与话术核心。"""
from typing import Dict, Any, List


def score_candidate(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> Dict[str, Any]:
    """综合评分占位：后续接入 GoldScoreEngine / TalentMatch。"""
    jd_alignment = candidate.get("jd_alignment_score", 0) or 0
    gold = candidate.get("gold_score")
    if gold in (None, "", 0, 0.0):
        overall = round(jd_alignment, 1)
    else:
        overall = round(jd_alignment * 0.6 + float(gold) * 0.4, 1)
    candidate["overall_score"] = overall
    candidate["risk_flags"] = candidate.get("risk_flags", [])
    return candidate


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
