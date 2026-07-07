"""Problem Task Manager：读取/分类失败或不确定时生成异常任务，带 resume_action。"""
import logging
from typing import Dict, Any, Optional

from . import db

logger = logging.getLogger(__name__)


def _create(
    role: str,
    task_type: str,
    problem: str,
    payload: Dict[str, Any],
    resume_action: str,
    mission_id: Optional[str] = None,
) -> str:
    payload["problem"] = problem
    payload["resume_action"] = resume_action
    tid = db.insert_human_task(mission_id, role, task_type, payload)
    logger.info(
        "Created problem task %s (type=%s, resume_action=%s, mission=%s)",
        tid, task_type, resume_action, mission_id,
    )
    return tid


def from_read_job(job: Dict[str, Any]) -> str:
    """读取失败 / 登录受限 / 内容为空 时生成任务。"""
    error = job.get("error", "")
    error_reason = job.get("error_reason", "")
    read_status = job.get("read_status", "")
    source_url = job.get("source_url", "")
    source_type = job.get("source_type", "unknown")

    if error_reason == "empty_content" or read_status == "empty" or (not error and not job.get("raw_text")):
        problem = f"{source_type} 内容为空，无法解析。"
        resume_action = "re_capture"
        task_type = "empty_content"
    elif error_reason in {"login_required", "captcha"} or "login" in error.lower() or "auth" in error.lower() or "captcha" in error.lower():
        problem = f"{source_type} 需要登录或验证码：{error}"
        resume_action = "provide_access"
        task_type = "login_required"
    else:
        problem = f"读取 {source_type} 失败：{error}"
        resume_action = "retry_read"
        task_type = "read_failed"

    db.update_read_job(job["id"], {"status": "needs_human"})
    return _create(
        role="system_operator",
        task_type=task_type,
        problem=problem,
        payload={
            "read_job_id": job.get("id"),
            "read_job": job,
            "source_url": source_url,
            "read_status": read_status,
            "error_reason": error_reason,
            "resume_state": "read_jobs",
        },
        resume_action=resume_action,
    )


def from_artifact(artifact: Dict[str, Any], raw_ingest: Optional[Dict[str, Any]] = None) -> str:
    """分类不确定或无法路由时生成任务。"""
    artifact_type = artifact.get("artifact_type", "unknown")
    confidence = artifact.get("confidence", 0.0)
    reason = artifact.get("reason", "")
    problem = f"内容分类不确定：{artifact_type}（置信度 {confidence:.2f}）。{reason}"

    return _create(
        role="client_advisor",
        task_type="classify_uncertain",
        problem=problem,
        payload={
            "artifact_id": artifact.get("id"),
            "artifact": artifact,
            "raw_ingest_id": artifact.get("raw_ingest_id"),
            "raw_ingest": raw_ingest or {},
            "resume_state": "artifact_classifier",
            "classification_reason": reason,
        },
        resume_action="manual_classify",
    )
