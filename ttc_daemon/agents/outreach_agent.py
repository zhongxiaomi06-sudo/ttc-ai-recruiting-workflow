"""话术/外联 Agent：生成电话任务和客户简报。"""
import json
import logging
from typing import Any, Dict, List

from .. import db
from ..core.scoring import generate_talking_points, build_call_script

logger = logging.getLogger(__name__)


def generate_call_tasks(
    mission: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    jd_fields: Dict[str, Any],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """为高分候选人生成电话任务记录。"""
    call_items = []
    threshold = 40  # 最低评分阈值

    for cand in candidates[:top_n]:
        if cand.get("overall_score", 0) < threshold:
            continue
        item = {
            "candidate_id": cand.get("id", ""),
            "mission_id": mission.get("id", ""),
            "jd_record_id": mission.get("jd_record_id", ""),
            "priority": int(cand.get("overall_score", 0)),
            "talking_points": generate_talking_points(cand, jd_fields),
            "evidence": cand.get("evidence", []),
            "status": "pending",
        }
        lid = db.insert_call_list(item)
        item["id"] = lid
        item["call_script"] = build_call_script(cand, jd_fields)
        call_items.append(item)

    logger.info("Mission %s generated %s call tasks", mission["id"], len(call_items))
    db.insert_agent_run(
        mission_id=mission["id"],
        agent_name="outreach_agent.generate_call_tasks",
        input_data={"candidate_count": len(candidates), "top_n": top_n},
        output_data={
            "call_task_count": len(call_items),
            "call_list_ids": [i["id"] for i in call_items],
        },
        decision="calling",
    )
    return call_items


def generate_client_brief(
    mission: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    jd_fields: Dict[str, Any],
    top_n: int = 5,
) -> Dict[str, Any]:
    """生成客户简报数据（供 HTML 模板渲染）。

    简报包含：岗位概要、Top N 候选人对比表、推荐策略、下一步建议。

    Returns:
        可直接存入 human_task payload 的简报数据
    """
    # 取 top N 高分候选人
    sorted_candidates = sorted(
        candidates, key=lambda x: x.get("overall_score", 0), reverse=True
    )
    top_candidates = sorted_candidates[:top_n]

    # 统计评分分布
    level_distribution = {}
    for c in candidates:
        lv = c.get("level", "未知")
        level_distribution[lv] = level_distribution.get(lv, 0) + 1

    scoring_summary = {
        "total": len(candidates),
        "level_distribution": level_distribution,
        "scoring_method": "llm_cot" if not candidates or not candidates[0].get("_fallback") else "fallback",
    }

    # 生成推荐策略
    recommendation = _build_recommendation(top_candidates, jd_fields)

    # 生成下一步建议
    next_steps = _build_next_steps(top_candidates, jd_fields)

    brief = {
        "jd_fields": jd_fields,
        "top_candidates": top_candidates,
        "scoring_summary": scoring_summary,
        "recommendation": recommendation,
        "next_steps": next_steps,
        "generated_at": db.now_iso(),
    }

    logger.info(
        "Generated client brief for mission %s: %d top candidates",
        mission["id"], len(top_candidates),
    )

    db.insert_agent_run(
        mission_id=mission["id"],
        agent_name="outreach_agent.generate_client_brief",
        input_data={"candidate_count": len(candidates), "top_n": top_n},
        output_data={
            "top_candidate_names": [c.get("name") for c in top_candidates],
            "recommendation": recommendation,
        },
        decision="brief_generated",
    )

    return brief


def create_client_brief_task(
    mission: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    jd_fields: Dict[str, Any],
) -> str:
    """生成客户简报并创建 human_task 供顾问审阅后发送。

    Returns:
        human_task id
    """
    brief = generate_client_brief(mission, candidates, jd_fields)

    from .human_dispatch import create_problem_task

    tid = create_problem_task(
        mission["id"],
        role="client_advisor",
        task_type="client_brief",
        payload={
            "title": f"客户简报：{jd_fields.get('company', '客户')} - {jd_fields.get('position', '岗位')}",
            "content": brief.get("recommendation", ""),
            "jd_fields": jd_fields,
            "top_candidates": brief.get("top_candidates", []),
            "scoring_summary": brief.get("scoring_summary", {}),
            "recommendation": brief.get("recommendation", ""),
            "next_steps": brief.get("next_steps", []),
            "generated_at": brief.get("generated_at", ""),
        },
    )

    logger.info("Created client brief task %s for mission %s", tid, mission["id"])
    return tid


def _build_recommendation(
    top_candidates: List[Dict[str, Any]], jd_fields: Dict[str, Any]
) -> str:
    """生成推荐策略文本。"""
    position = jd_fields.get("position", "该岗位")

    if not top_candidates:
        return f"当前未找到匹配 {position} 的高分候选人，建议放宽搜索条件或扩大人才来源。"

    strong = [c for c in top_candidates if c.get("overall_score", 0) >= 70]
    medium = [c for c in top_candidates if 55 <= c.get("overall_score", 0) < 70]

    parts = [f"针对 {position}，共评估 {len(top_candidates)} 位候选人。"]

    if strong:
        names = "、".join(c.get("name", "?") for c in strong[:3])
        parts.append(
            f"推荐优先联系 {names}，综合评分扎实，"
            f"建议在本周内完成首轮电话沟通。"
        )

    if medium:
        names = "、".join(c.get("name", "?") for c in medium[:2])
        parts.append(f"备选方案：{names}，可作为补充人选在第二轮联系。")

    # 检查风险提示
    risky = [c for c in top_candidates if c.get("risk_flags")]
    if risky:
        parts.append(
            f"注意：{len(risky)} 位候选人有风险信号，建议联系前与顾问确认。"
        )

    return " ".join(parts)


def _build_next_steps(
    top_candidates: List[Dict[str, Any]], jd_fields: Dict[str, Any]
) -> List[str]:
    """生成下一步行动建议。"""
    steps = []

    if top_candidates:
        steps.append(
            f"本周内完成 Top 3 候选人的首轮电话沟通"
        )
        steps.append(
            "收集候选人反馈后（有兴趣/无兴趣/薪资期望），更新人才评分模型"
        )

    steps.append("若首轮候选人全部无响应，启动第二轮人才搜索（放宽技能/地点限制）")
    steps.append("每周五生成 Mission 周报，跟踪响应率和命中率变化")

    if not top_candidates:
        steps.insert(0, "与客户确认 JD 要求是否可调整（地点、薪资、经验年限）")
        steps.insert(1, "扩大人才搜索渠道（启用 Source 公司 MySQL、公网搜索）")

    return steps
