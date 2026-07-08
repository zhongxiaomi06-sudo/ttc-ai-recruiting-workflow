"""Scheduler tick：把读取 → 分类 → 归一化 → 路由 → Mission 推进串成一条流水线。

优先级策略：
- 按 priority_score 降序处理 Mission（高优先级先推进）
- SCALE_UP / ACTIVE 仓位优先
- 新 JD 优先分配资源
- 长期无响应的 JD 自动降级
"""
import logging
from collections import Counter
from typing import Dict

from . import db
from .ingestion import read_job_runner, artifact_classifier, normalizer, mission_router
from .problem_task_manager import from_read_job, from_artifact
from .agents import orchestrator, position_allocator

logger = logging.getLogger(__name__)


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


def _update_mission_priorities() -> None:
    """更新所有活跃 Mission 的优先级评分和仓位状态。"""
    missions = db.get_pending_missions(limit=200)
    for mission in missions:
        try:
            new_state, reason = position_allocator.evaluate_allocation(mission)
            current = mission.get("allocation_state") or "DISCOVERED"
            if new_state != current:
                priority = position_allocator.compute_priority_score(mission)
                db.update_mission_state(
                    mission["id"], mission["state"],
                    {"allocation_state": new_state, "priority_score": priority},
                )
                logger.info(
                    "Mission %s auto-rebalance: %s → %s (reason: %s)",
                    mission["id"], current, new_state, reason,
                )
        except Exception:
            logger.exception("Priority update failed for mission %s", mission["id"])


def _log_allocation_summary() -> None:
    """每 10 个 tick 输出一次仓位分布摘要。"""
    missions = db.get_pending_missions(limit=200)
    if not missions:
        return
    states = Counter(m.get("allocation_state") or "DISCOVERED" for m in missions)
    summary = " | ".join(f"{k}:{v}" for k, v in sorted(states.items()))
    logger.info("Allocation summary [%d missions]: %s", len(missions), summary)


_tick_counter = 0


def tick() -> None:
    """一次调度心跳：先跑摄入流水线，再按优先级推进 Mission。"""
    global _tick_counter
    _tick_counter += 1

    try:
        _process_ingestion()
    except Exception:
        logger.exception("Ingestion pipeline error")

    # 每 10 个 tick 输出仓位摘要并更新优先级
    if _tick_counter % 10 == 0:
        try:
            _log_allocation_summary()
        except Exception:
            logger.exception("Allocation summary error")

    # 每 30 个 tick 做一次全局仓位评估
    if _tick_counter % 30 == 0:
        try:
            _update_mission_priorities()
        except Exception:
            logger.exception("Priority update error")

    try:
        orchestrator.process_pending_missions()
    except Exception:
        logger.exception("Mission orchestration error")
