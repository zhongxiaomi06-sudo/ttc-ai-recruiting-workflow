"""Pipeline：兼容旧版 /pipeline/run 端点，委托给 ingestion + orchestrator。

不再重复 JD 解析、人才召回、评分逻辑 —— 统一通过 read_job → classify →
normalize → route → mission → orchestrator 进行。
"""
import json
import logging
from typing import Dict, Any, Optional

from . import db
from .ingestion import artifact_classifier, normalizer, mission_router
from .agents import orchestrator

logger = logging.getLogger(__name__)


def run_pipeline(jd_record_id: Optional[str] = None) -> Dict[str, Any]:
    """主链路：通过 ingestion pipeline + orchestrator 状态机推进 Mission。

    兼容旧版 API，返回包含 mission 状态的结果。
    """
    # 1. 获取 JD 记录
    jd_records = db.get_latest_jd(limit=5)
    if not jd_records:
        return {"ok": False, "error": "No JD record found"}

    jd_record = None
    if jd_record_id:
        jd_record = next((r for r in jd_records if r["id"] == jd_record_id), None)
    jd_record = jd_record or jd_records[0]

    # 2. 分类 + 归一化
    artifact_type, confidence, reason = artifact_classifier.classify(jd_record)
    if artifact_type != "jd" or confidence < 0.6:
        return {
            "ok": False,
            "error": "Record is not a high-confidence JD",
            "artifact_type": artifact_type,
            "confidence": confidence,
            "reason": reason,
        }

    jd_fields = normalizer.normalize("jd", jd_record)
    aid = db.insert_normalized_artifact({
        "raw_ingest_id": jd_record.get("id", ""),
        "artifact_type": artifact_type,
        "confidence": confidence,
        "reason": reason,
        "normalized_payload": jd_fields,
        "status": "pending",
    })

    # 3. 路由 → 创建 Mission
    artifact = db.get_normalized_artifact(aid)
    result = mission_router.route(artifact)

    if result.get("action") != "mission_created":
        return {"ok": False, "error": f"Route action: {result.get('action')}", "detail": result}

    mid = result["mission_id"]

    # 4. 推进 Mission（created → jd_parsed → sourcing → scored）
    mission = db.get_mission(mid)
    for _ in range(4):  # 最多推进 4 步
        if not mission or mission["state"] in ("closed", "problem_pending", "human_pending"):
            break
        orchestrator.step_mission(mission)
        mission = db.get_mission(mid)

    # 5. 返回结果
    call_list = db.get_call_list(limit=100)
    candidates_count = len(db.parse_json_field(mission.get("candidate_ids"), [])) if mission else 0

    return {
        "ok": True,
        "mission_id": mid,
        "mission_state": mission["state"] if mission else "unknown",
        "jd_record_id": jd_record.get("id", ""),
        "jd_fields": jd_fields,
        "candidates_count": candidates_count,
        "call_list_count": len(call_list),
        "call_list": call_list,
    }
