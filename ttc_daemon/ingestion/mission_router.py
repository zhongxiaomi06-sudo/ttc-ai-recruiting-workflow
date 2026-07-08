"""Mission Router：根据 normalized artifact 决定下一步动作。"""
import logging
from typing import Dict, Any

from .. import db

logger = logging.getLogger(__name__)

JD_CONFIDENCE_THRESHOLD = 0.6


def route(artifact: Dict[str, Any]) -> Dict[str, Any]:
    """对 normalized artifact 进行路由。"""
    aid = artifact["id"]
    artifact_type = artifact.get("artifact_type", "unknown")
    confidence = artifact.get("confidence", 0.0)
    payload = db.parse_json_field(artifact.get("normalized_payload"), {})

    if artifact_type == "jd" and confidence >= JD_CONFIDENCE_THRESHOLD:
        mid = db.insert_mission(normalized_artifact_id=aid)
        db.update_mission_state(mid, "created", {"jd_fields": payload})
        db.update_normalized_artifact(aid, {"status": "mission_created", "mission_id": mid})
        logger.info("Routed artifact %s to mission %s", aid, mid)
        return {"action": "mission_created", "mission_id": mid}

    if artifact_type == "candidate":
        candidate = {
            "name": payload.get("name", ""),
            "phone": payload.get("phone", ""),
            "email": payload.get("email", ""),
            "source_types": ["normalized_candidate"],
            "raw_profile": payload,
            "overall_score": 0,
        }
        cid = db.insert_candidate(candidate)
        db.update_normalized_artifact(aid, {"status": "routed"})
        logger.info("Routed artifact %s to candidate %s", aid, cid)
        return {"action": "candidate_created", "candidate_id": cid}

    if artifact_type == "evidence":
        db.update_normalized_artifact(aid, {"status": "routed"})
        return {"action": "stored_evidence"}

    # 未知或置信度不足，进入待审状态（由调度器统一生成 problem_task）
    db.update_normalized_artifact(aid, {"status": "needs_review"})
    return {"action": "needs_review"}
