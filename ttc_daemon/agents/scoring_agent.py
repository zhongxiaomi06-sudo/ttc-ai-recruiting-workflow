"""评分排序 Agent：对候选人进行 LLM CoT 打分、排序，并检测合规问题。"""
import json
import logging
from typing import Dict, Any, List

from .. import db
from ..core.scoring import score_candidate, detect_compliance_issues

logger = logging.getLogger(__name__)


def score(
    mission: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    jd_fields: Dict[str, Any],
) -> Dict[str, Any]:
    """对候选人打分、持久化、排序。

    Returns:
        dict with keys: scored_candidates, compliance_candidates, summary
    """
    scored = []
    compliance_candidates = []

    for cand in candidates:
        # 使用统一的评分入口（LLM CoT 优先，否则兜底）
        cand = score_candidate(cand, jd_fields)

        # 检测合规问题
        compliance_issues = detect_compliance_issues(cand)
        if compliance_issues:
            cand["compliance_issues"] = compliance_issues
            compliance_candidates.append({
                "candidate_id": cand.get("id"),
                "name": cand.get("name", "unknown"),
                "issues": compliance_issues,
            })

        # 重新入库以保存所有评分字段
        cid = db.insert_candidate(cand)
        cand["id"] = cid
        scored.append(cand)

    # 按 overall_score 降序排列
    scored.sort(key=lambda x: x.get("overall_score", 0), reverse=True)

    # 生成评分摘要
    top_scores = [
        {"id": c.get("id"), "name": c.get("name"), "score": c.get("overall_score")}
        for c in scored[:10]
    ]
    level_distribution = {}
    for c in scored:
        lv = c.get("level", "未知")
        level_distribution[lv] = level_distribution.get(lv, 0) + 1

    summary = {
        "total": len(scored),
        "top_scores": top_scores,
        "level_distribution": level_distribution,
        "compliance_count": len(compliance_candidates),
        "scoring_method": "fallback" if (not scored or scored[0].get("_fallback")) else "llm_cot",
    }

    logger.info(
        "Mission %s scored %s candidates (top=%.1f, compliance=%d, method=%s)",
        mission["id"],
        len(scored),
        top_scores[0]["score"] if top_scores else 0,
        len(compliance_candidates),
        summary["scoring_method"],
    )

    db.insert_agent_run(
        mission_id=mission["id"],
        agent_name="scoring_agent.score",
        input_data={
            "candidate_count": len(candidates),
            "jd_position": jd_fields.get("position", ""),
        },
        output_data=summary,
        decision="scored",
    )

    return {
        "scored_candidates": scored,
        "compliance_candidates": compliance_candidates,
        "summary": summary,
    }
