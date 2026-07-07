"""Scheduler tick：把读取 → 分类 → 归一化 → 路由 → Mission 推进串成一条流水线。"""
import logging
from typing import Dict, Any

from . import db
from .ingestion import read_job_runner, artifact_classifier, normalizer, mission_router
from .problem_task_manager import from_read_job, from_artifact
from .agents import orchestrator

logger = logging.getLogger(__name__)


def _json_field(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        import json
        return json.loads(value)
    except Exception:
        return default


def _process_ingestion() -> None:
    """处理所有 pending/failed 的 read_job。"""
    jobs = db.get_pending_read_jobs(limit=50)
    if jobs:
        logger.info("Processing %s read jobs", len(jobs))

    for job in jobs:
        jid = job["id"]
        try:
            record = read_job_runner.run_read_job(job)
        except Exception:
            # run_read_job 已经把状态设为 failed
            from_read_job(db.get_read_job(jid) or job)
            continue

        if not record.get("raw_text", "").strip():
            from_read_job(db.get_read_job(jid) or job)
            continue

        artifact_type, confidence, reason = artifact_classifier.classify(record)
        normalized_payload = normalizer.normalize(artifact_type, record)
        aid = db.insert_normalized_artifact(
            {
                "raw_ingest_id": record.get("id", ""),
                "artifact_type": artifact_type,
                "confidence": confidence,
                "reason": reason,
                "normalized_payload": normalized_payload,
                "status": "pending",
            }
        )
        artifact = db.get_normalized_artifact(aid)
        result = mission_router.route(artifact)

        if result["action"] == "needs_review":
            from_artifact(artifact, record)


def tick() -> None:
    """一次调度心跳：先跑摄入流水线，再推进 Mission。"""
    try:
        _process_ingestion()
    except Exception:
        logger.exception("Ingestion pipeline error")

    try:
        orchestrator.process_pending_missions()
    except Exception:
        logger.exception("Mission orchestration error")
