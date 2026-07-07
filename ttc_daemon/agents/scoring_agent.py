"""评分排序 Agent：对候选人进行打分并排序。"""
import json
import logging
from typing import Dict, Any, List

from .. import db
from ..pipeline import score_candidate

logger = logging.getLogger(__name__)


def score(mission: Dict[str, Any], candidates: List[Dict[str, Any]], jd_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    """对候选人打分并持久化。"""
    scored = []
    for cand in candidates:
        cand = score_candidate(cand, jd_fields)
        # 重新入库以保存 overall_score
        cid = db.insert_candidate(cand)
        cand["id"] = cid
        scored.append(cand)

    scored.sort(key=lambda x: x.get("overall_score", 0), reverse=True)

    logger.info("Mission %s scored %s candidates", mission["id"], len(scored))
    db.insert_agent_run(
        mission_id=mission["id"],
        agent_name="scoring_agent.score",
        input_data={"candidate_count": len(candidates)},
        output_data={
            "top_candidates": [
                {"id": c.get("id"), "name": c.get("name"), "score": c.get("overall_score")}
                for c in scored[:10]
            ]
        },
        decision="scored",
    )
    return scored
