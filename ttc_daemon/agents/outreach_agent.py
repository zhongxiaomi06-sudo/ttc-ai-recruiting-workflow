"""话术/外联 Agent：生成电话任务和客户简报。"""
import json
import logging
from typing import Dict, Any, List

from .. import db
from ..core.scoring import generate_talking_points, build_call_script

logger = logging.getLogger(__name__)


def generate_call_tasks(
    mission: Dict[str, Any], candidates: List[Dict[str, Any]], jd_fields: Dict[str, Any], top_n: int = 10
) -> List[Dict[str, Any]]:
    """为高分候选人生成电话任务记录。"""
    call_items = []
    threshold = 40  # 可配置
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
        output_data={"call_task_count": len(call_items), "call_list_ids": [i["id"] for i in call_items]},
        decision="calling",
    )
    return call_items
