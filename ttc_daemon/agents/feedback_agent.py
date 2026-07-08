"""反馈学习 Agent：消费猎头反馈数据，校准评分权重，生成复盘报告。

职责：
1. 评分校准：猎头反馈"无兴趣"的高分候选 → 降低对应维度的权重
2. 复盘报告生成：每周自动生成 Mission 复盘（命中率、响应率、推荐精度）
3. Mission 进入 feedback 状态后自动调用
"""
import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .. import db

logger = logging.getLogger(__name__)

# 默认维度权重（与 scoring.py 中 SCORING_DIMENSIONS 保持一致）
DEFAULT_WEIGHTS = {
    "tech_depth": 0.25,
    "project_ownership": 0.20,
    "complexity": 0.20,
    "impact": 0.15,
    "engineering_integrity": 0.10,
    "company_prestige": 0.10,
}


def _load_json(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def analyze_mission_feedback(mission_id: str) -> Dict[str, Any]:
    """分析单个 Mission 的反馈数据，生成复盘报告。

    Returns:
        复盘 JSON，包含命中率、响应率、推荐精度等
    """
    mission = db.get_mission(mission_id)
    if not mission:
        return {"error": "Mission not found", "mission_id": mission_id}

    tasks = db.get_mission_human_tasks(mission_id)
    agent_runs = db.get_mission_agent_runs(mission_id)

    # 收集反馈数据
    call_tasks = [t for t in tasks if t.get("task_type") == "call"]
    completed_calls = [t for t in call_tasks if t.get("status") == "completed"]

    feedback_entries = []
    for t in completed_calls:
        result = _load_json(t.get("result"), {})
        if result:
            feedback_entries.append({
                "task_id": t.get("id"),
                "outcome": result.get("outcome", "unknown"),
                "notes": result.get("notes", ""),
                "payload": _load_json(t.get("payload"), {}),
            })

    # 统计各 outcome
    outcome_counts = defaultdict(int)
    for fb in feedback_entries:
        outcome_counts[fb["outcome"]] += 1

    total_calls = len(completed_calls)
    interested = outcome_counts.get("interested", 0)
    not_interested = outcome_counts.get("not_interested", 0)
    no_answer = outcome_counts.get("no_answer", 0)
    wrong_info = outcome_counts.get("wrong_info", 0)

    # 计算关键指标
    contact_rate = (interested + not_interested) / max(total_calls, 1)
    interest_rate = interested / max(interested + not_interested, 1)
    hit_rate = interested / max(total_calls, 1)

    # 精度分析：高分但无兴趣的候选
    high_score_rejections = []
    for fb in feedback_entries:
        if fb["outcome"] == "not_interested":
            payload = fb.get("payload", {})
            candidate = payload.get("candidate", {})
            score = candidate.get("overall_score", 0)
            if float(score) >= 60:
                high_score_rejections.append({
                    "candidate_name": candidate.get("name", "unknown"),
                    "score": score,
                    "notes": fb.get("notes", ""),
                })

    # 生成复盘报告
    report = {
        "mission_id": mission_id,
        "generated_at": db.now_iso(),
        "summary": {
            "total_call_tasks": len(call_tasks),
            "completed_calls": total_calls,
            "outcomes": dict(outcome_counts),
            "contact_rate": round(contact_rate, 3),
            "interest_rate": round(interest_rate, 3),
            "hit_rate": round(hit_rate, 3),
        },
        "precision_analysis": {
            "high_score_rejections": high_score_rejections,
            "count": len(high_score_rejections),
            "precision_warning": len(high_score_rejections) > total_calls * 0.3,
        },
        "weight_calibration": _calibrate_weights(feedback_entries),
        "recommendations": _generate_recommendations(
            contact_rate, interest_rate, hit_rate, high_score_rejections
        ),
    }

    logger.info(
        "Feedback report for mission %s: hit_rate=%.1f%% (%d/%d), interest=%.1f%%",
        mission_id,
        hit_rate * 100,
        interested,
        total_calls,
        interest_rate * 100,
    )

    return report


def _calibrate_weights(feedback_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """根据反馈调整各维度权重。

    规则：如果高分候选人因为某项能力不足被拒，降低该维度权重；
          如果被拒候选人在某维度上频繁出现问题，提高该维度权重。
    """
    weights = dict(DEFAULT_WEIGHTS)

    # 分析被拒原因中的关键词与维度关联
    dimension_keywords = {
        "tech_depth": ["技术", "技能", "编程", "开发", "算法", "架构", "系统"],
        "project_ownership": ["项目", "负责", "主导", "owner", "端到端"],
        "complexity": ["复杂度", "规模", "并发", "高并发", "分布式", "系统设计"],
        "impact": ["影响", "结果", "业绩", "增长", "收入", "用户", "效率"],
        "engineering_integrity": ["代码质量", "测试", "文档", "CI", "工程"],
        "company_prestige": ["公司", "背景", "团队", "行业"],
    }

    # 统计拒绝反馈中提到的维度
    rejection_notes = [
        fb.get("notes", "") for fb in feedback_entries
        if fb.get("outcome") in ("not_interested", "wrong_info")
    ]

    if not rejection_notes:
        return {"weights": weights, "adjustments": [], "reason": "无足够反馈数据，保持默认权重"}

    dimension_hits = defaultdict(int)
    for dim, keywords in dimension_keywords.items():
        for note in rejection_notes:
            if any(kw in note for kw in keywords):
                dimension_hits[dim] += 1

    total_hits = sum(dimension_hits.values()) or 1
    adjustments = []
    for dim, hits in dimension_hits.items():
        if hits > 0:
            # 该维度被提及的比例越高，权重调整越大
            factor = hits / total_hits
            adjustment = round(factor * 0.05, 3)  # 每次最多调整 5%
            weights[dim] = round(weights[dim] + adjustment, 3)
            adjustments.append({
                "dimension": dim,
                "old_weight": DEFAULT_WEIGHTS[dim],
                "new_weight": weights[dim],
                "hits": hits,
                "factor": round(factor, 3),
            })

    # 归一化
    total = sum(weights.values())
    if total > 0:
        weights = {k: round(v / total, 3) for k, v in weights.items()}

    return {
        "weights": weights,
        "adjustments": adjustments,
        "reason": f"基于 {len(rejection_notes)} 条拒绝反馈调整",
    }


def _generate_recommendations(
    contact_rate: float,
    interest_rate: float,
    hit_rate: float,
    high_score_rejections: List[Dict[str, Any]],
) -> List[str]:
    """根据指标生成改进建议。"""
    recommendations = []

    if contact_rate < 0.5:
        recommendations.append("接通率偏低，建议优化打电话时段、增加备用联系方式")
    if interest_rate < 0.5:
        recommendations.append(
            "意向率偏低，建议重新审视 JD 匹配度，或调整候选人画像门槛"
        )
    if high_score_rejections:
        recommendations.append(
            f"{len(high_score_rejections)} 位高分候选人被拒，"
            "建议复核评分维度权重和简历解析质量"
        )
    if hit_rate < 0.2 and contact_rate >= 0.5:
        recommendations.append(
            "命中率偏低但接通率正常，说明评分模型对 JD 匹配的排序能力需要优化"
        )

    if not recommendations:
        recommendations.append("各项指标正常，当前评分模型表现良好。")

    return recommendations


def process_feedback_state(mission: Dict[str, Any]) -> Dict[str, Any]:
    """Mission 进入 feedback 状态后的处理入口。

    Returns:
        复盘报告
    """
    mission_id = mission["id"]
    logger.info("Processing feedback state for mission %s", mission_id)

    report = analyze_mission_feedback(mission_id)

    # 记录 Agent 运行日志
    db.insert_agent_run(
        mission_id=mission_id,
        agent_name="feedback_agent.process_feedback_state",
        input_data={"mission_state": mission.get("state")},
        output_data=report,
        decision="feedback_analyzed",
    )

    return report


def get_calibrated_weights() -> Dict[str, float]:
    """获取经过历史反馈校准的维度权重。

    分析所有已完成 Mission 的反馈数据，返回调整后的权重。
    """
    conn = db.get_conn()
    # 查找所有已关闭且有反馈的 Mission
    rows = conn.execute(
        """
        SELECT m.id as mission_id
        FROM missions m
        JOIN human_tasks ht ON ht.mission_id = m.id
        WHERE m.state = 'closed'
          AND ht.task_type = 'call'
          AND ht.status = 'completed'
        GROUP BY m.id
        """
    ).fetchall()

    if not rows:
        logger.info("No historical feedback data, using default weights")
        return dict(DEFAULT_WEIGHTS)

    # 汇总所有拒绝反馈
    all_rejection_notes = []
    for row in rows:
        mid = row["mission_id"]
        tasks = db.get_mission_human_tasks(mid)
        for t in tasks:
            if t.get("task_type") == "call" and t.get("status") == "completed":
                result = _load_json(t.get("result"), {})
                if result.get("outcome") in ("not_interested", "wrong_info"):
                    all_rejection_notes.append({
                        "notes": result.get("notes", ""),
                        "outcome": result.get("outcome", ""),
                    })

    if not all_rejection_notes:
        return dict(DEFAULT_WEIGHTS)

    calibration = _calibrate_weights(all_rejection_notes)
    return calibration.get("weights", dict(DEFAULT_WEIGHTS))
