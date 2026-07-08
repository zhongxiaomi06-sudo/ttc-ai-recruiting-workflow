"""Human Dispatch Agent：把需要人做的事情封装成 HTML 任务页面。"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import db
from ..notifications import feishu_bot

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_jinja_env: Environment = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def create_call_tasks(mission: Dict[str, Any], call_items: List[Dict[str, Any]]) -> List[str]:
    """为每个电话任务创建 human_task 记录。"""
    task_ids = []
    for item in call_items:
        candidate = db.get_conn().execute(
            "SELECT * FROM candidates WHERE id = ?", (item["candidate_id"],)
        ).fetchone()
        payload = {
            "call_list_id": item["id"],
            "candidate_id": item["candidate_id"],
            "candidate": dict(candidate) if candidate else {},
            "jd_record_id": item.get("jd_record_id", ""),
            "priority": item.get("priority", 0),
            "talking_points": item.get("talking_points", []),
            "evidence": item.get("evidence", []),
            "call_script": item.get("call_script", ""),
        }
        tid = db.insert_human_task(mission["id"], "phone_caller", "call", payload)
        task_ids.append(tid)
        task = db.get_human_task(tid)
        if task:
            feishu_bot.notify_new_task(dict(task))
    logger.info("Mission %s created %s human call tasks", mission["id"], len(task_ids))
    return task_ids


def create_problem_task(
    mission_id: Optional[str], role: str, task_type: str, payload: Dict[str, Any]
) -> str:
    """创建一个"AI 遇到问题时需要人解决"的任务。"""
    tid = db.insert_human_task(mission_id, role, task_type, payload)
    logger.info(
        "Created problem task %s (type=%s, role=%s, mission=%s)",
        tid, task_type, role, mission_id,
    )
    task = db.get_human_task(tid)
    if task:
        feishu_bot.notify_problem(dict(task), payload.get("problem", ""))
    return tid


# ── 渲染 ────────────────────────────────────────────────────────────────────


def get_task_html(tid: str) -> str:
    task = db.get_human_task(tid)
    if not task:
        return _jinja_env.get_template("404.html").render(message="任务不存在")

    payload = db.parse_json_field(task.get("payload"), {})
    template_name = _template_for_task(task, payload)

    # 补充候选人和 JD 信息用于渲染
    candidate_id = payload.get("candidate_id")
    if candidate_id:
        row = db.get_conn().execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if row:
            cand = dict(row)
            cand["source_types"] = db.parse_json_field(cand.get("source_types"), [])
            cand["raw_profile"] = db.parse_json_field(cand.get("raw_profile"), {})
            cand["enriched_profile"] = db.parse_json_field(cand.get("enriched_profile"), {})
            cand["risk_flags"] = db.parse_json_field(cand.get("risk_flags"), [])
            cand["dimension_scores"] = db.parse_json_field(cand.get("dimension_scores"), {})
            cand["evidence_binding"] = db.parse_json_field(cand.get("evidence_binding"), [])
            cand["verification_questions"] = db.parse_json_field(cand.get("verification_questions"), [])
            payload["candidate"] = cand

    jd_record_id = payload.get("jd_record_id") or payload.get("jd_record", {}).get("id")
    if jd_record_id:
        row = db.get_conn().execute("SELECT * FROM ingest_records WHERE id = ?", (jd_record_id,)).fetchone()
        payload["jd_record"] = dict(row) if row else payload.get("jd_record", {})

    # 补充 JD fields
    if task.get("mission_id"):
        mission = db.get_mission(task["mission_id"])
        if mission:
            payload["jd_fields"] = db.parse_json_field(mission.get("jd_fields"), {})

    db.update_human_task_status(tid, "opened")
    return _jinja_env.get_template(template_name).render(task=task, payload=payload)


def _template_for_task(task: Dict[str, Any], payload: Dict[str, Any]) -> str:
    """根据任务类型选择模板。"""
    task_type = task.get("task_type", "")

    template_map = {
        "call": "call_task.html",
        "review": "review_task.html",
        "compliance": "compliance_task.html",
        "client_brief": "client_brief.html",
        "jd_clarify": "problem_task.html",
        "source_help": "problem_task.html",
        "scoring_conflict": "problem_task.html",
        "outreach_problem": "problem_task.html",
        "runtime_error": "problem_task.html",
        "empty_content": "problem_task.html",
        "login_required": "problem_task.html",
        "read_failed": "problem_task.html",
        "classify_uncertain": "problem_task.html",
    }
    return template_map.get(task_type, "generic_task.html")


def render_dashboard(missions: List[Dict[str, Any]], pending_tasks: List[Dict[str, Any]], api_token: str = "") -> str:
    """渲染 Mission 仪表盘。"""
    from collections import Counter

    for m in missions:
        m["candidate_count"] = len(db.parse_json_field(m.get("candidate_ids"), []))
        m["call_task_count"] = len(db.parse_json_field(m.get("call_list_ids"), []))
        m.setdefault("allocation_state", "DISCOVERED")
        m.setdefault("priority_score", 0.0)

    # 仓位分布摘要
    allocation_summary = dict(
        Counter(m.get("allocation_state", "DISCOVERED") for m in missions)
    )

    return _jinja_env.get_template("dashboard.html").render(
        missions=missions,
        pending_tasks=pending_tasks,
        allocation_summary=allocation_summary,
        api_token=api_token,
    )


# ── 完成任务 ────────────────────────────────────────────────────────────────


def complete_task(tid: str, result: Dict[str, Any]) -> None:
    """人类完成任务后更新状态，并同步 call_list / feedback / Mission。"""
    task = db.get_human_task(tid)
    if not task:
        raise ValueError(f"Task {tid} not found")

    db.complete_human_task(tid, result)

    payload = db.parse_json_field(task.get("payload"), {})

    if task["task_type"] == "call":
        _complete_call_task(task, payload, result)
    elif task["task_type"] in ("review", "compliance"):
        _complete_review_or_compliance_task(task, payload, result)
    else:
        _complete_problem_task(task, payload, result)

    # 检查是否需要 resume mission
    if task.get("mission_id"):
        _resume_mission_if_tasks_done(task["mission_id"])

    logger.info("Human task %s completed with outcome %s", tid, result.get("outcome"))


def _complete_call_task(task: Dict[str, Any], payload: Dict[str, Any], result: Dict[str, Any]) -> None:
    """完成打电话任务：同步 call_list 状态和 feedback 记录。"""
    call_list_id = payload.get("call_list_id")
    if call_list_id and result.get("outcome"):
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE call_list SET status = ? WHERE id = ?",
                (result["outcome"], call_list_id),
            )
    candidate_id = payload.get("candidate_id")
    if candidate_id:
        db.insert_feedback({
            "candidate_id": candidate_id,
            "call_list_id": call_list_id or "",
            "outcome": result.get("outcome", ""),
            "notes": result.get("notes", ""),
        })


def _complete_review_or_compliance_task(
    task: Dict[str, Any], payload: Dict[str, Any], result: Dict[str, Any]
) -> None:
    """完成审核/合规任务。

    审核结果：
    - approved：审核通过，待 resume_mission 推进 Mission
    - rejected：驳回，关闭 Mission
    - need_more_info：需要补充信息，转为 problem_pending
    """
    outcome = result.get("outcome", "")
    mission_id = task.get("mission_id")

    if outcome == "rejected" and mission_id:
        db.update_mission_state(
            mission_id, "closed",
            {"outcome": f"{task['task_type']}_rejected", "closed_at": db.now_iso()},
        )
        logger.info("Mission %s closed: %s rejected", mission_id, task["task_type"])
    elif outcome == "need_more_info" and mission_id:
        db.update_mission_state(
            mission_id, "problem_pending",
            {"resume_state": payload.get("resume_state", "calling")},
        )
        logger.info("Mission %s → problem_pending: need more info from review", mission_id)
    # "approved" 不做额外操作，由 _resume_mission_if_tasks_done 推进


def _complete_problem_task(
    task: Dict[str, Any], payload: Dict[str, Any], result: Dict[str, Any]
) -> None:
    """完成异常处理任务。"""
    mission_id = task.get("mission_id")

    if result.get("outcome") == "cannot_resolve":
        if mission_id:
            db.update_mission_state(
                mission_id, "closed",
                {"outcome": "human_cannot_resolve", "closed_at": db.now_iso()},
            )
        return

    if result.get("outcome") != "resolved":
        return

    resume_action = payload.get("resume_action") or task.get("task_type")

    if resume_action in {"retry_read", "provide_access"}:
        _resume_read_job(payload, result, retry=True)
    elif resume_action == "re_capture":
        _resume_read_job(payload, result, retry=True, use_manual_text=True)
    elif resume_action == "manual_classify":
        _resume_manual_classify(payload, result)
    elif resume_action == "jd_clarify" or task.get("task_type") == "jd_clarify":
        _resume_jd_clarify(mission_id, payload, result)
    elif mission_id:
        resume_state = payload.get("resume_state") or "created"
        db.update_mission_state(mission_id, resume_state, {"resume_state": None})


def _resume_read_job(payload: Dict[str, Any], result: Dict[str, Any], retry: bool, use_manual_text: bool = False) -> None:
    jid = payload.get("read_job_id") or db.parse_json_field(payload.get("read_job"), {}).get("id")
    if not jid:
        return
    updates: Dict[str, Any] = {
        "status": "pending" if retry else "needs_human",
        "error": "",
        "read_status": "",
        "error_reason": "",
    }
    replacement_url = result.get("replacement_url", "").strip()
    if replacement_url:
        updates["source_url"] = replacement_url
    manual_text = result.get("manual_text", "").strip() or result.get("notes", "").strip()
    if use_manual_text and manual_text:
        updates["raw_text"] = manual_text
        updates["markdown"] = manual_text
        updates["method"] = "human_provided"
    db.update_read_job(jid, updates)


def _resume_manual_classify(payload: Dict[str, Any], result: Dict[str, Any]) -> None:
    aid = payload.get("artifact_id") or db.parse_json_field(payload.get("artifact"), {}).get("id")
    artifact_type = result.get("artifact_type", "").strip()
    if not aid or artifact_type not in {"jd", "candidate", "evidence", "chat", "unknown"}:
        return

    raw_ingest = payload.get("raw_ingest") or {}
    if not raw_ingest and payload.get("raw_ingest_id"):
        raw_ingest = db.get_ingest(payload["raw_ingest_id"]) or {}

    from ..ingestion import normalizer, mission_router

    normalized_payload = normalizer.normalize(artifact_type, raw_ingest) if raw_ingest else {}
    db.update_normalized_artifact(
        aid,
        {
            "artifact_type": artifact_type,
            "confidence": float(result.get("confidence") or 1.0),
            "reason": result.get("notes", "人工分类"),
            "normalized_payload": normalized_payload,
            "status": "pending",
        },
    )
    artifact = db.get_normalized_artifact(aid)
    if artifact:
        mission_router.route(artifact)


def _resume_jd_clarify(mission_id: Optional[str], payload: Dict[str, Any], result: Dict[str, Any]) -> None:
    if not mission_id:
        return
    mission = db.get_mission(mission_id)
    if not mission:
        return
    current = db.parse_json_field(mission.get("jd_fields"), {}) or payload.get("jd_fields") or {}
    additions = {
        "position": result.get("position", "").strip(),
        "location": result.get("location", "").strip(),
        "salary": result.get("salary", "").strip(),
        "target_companies": _split_field(result.get("target_companies", "")),
        "skills": _merge_list(current.get("skills", []), _split_field(result.get("skills", ""))),
        "human_notes": result.get("notes", "").strip(),
    }
    merged = {**current}
    for k, v in additions.items():
        if v:
            merged[k] = v
    resume_state = payload.get("resume_state") or mission.get("resume_state") or "created"
    db.update_mission_state(mission_id, resume_state, {"jd_fields": merged, "resume_state": None})


def _resume_mission_if_tasks_done(mission_id: str) -> None:
    """当所有 human_tasks 完成时，推进 Mission 到 resume_state。

    优先级：
    1. 先检查是否有 active 的审核/合规任务（需要先完成）
    2. 检查所有任务是否全部完成
    3. 如果全部完成，resume 到对应状态
    """
    mission = db.get_mission(mission_id)
    if not mission:
        return
    tasks = db.get_mission_human_tasks(mission_id)
    active = [t for t in tasks if t["status"] in {"pending", "notified", "opened"}]
    if active:
        return

    # 所有任务完成，确定 resume 目标
    current_state = mission.get("state", "")

    if current_state == "human_review":
        # 审核完成 → 检查是否有被驳回的
        review_tasks = [t for t in tasks if t.get("task_type") == "review"]
        any_rejected = any(
            db.parse_json_field(t.get("result"), {}).get("outcome") == "rejected"
            for t in review_tasks
        )
        if any_rejected:
            # 已在 _complete_review_or_compliance_task 中关闭
            return
        # 审核通过 → calling
        db.update_mission_state(mission_id, "calling", {"resume_state": None})
        return

    if current_state == "problem_pending":
        # 问题解决 → 回到 resume_state
        resume_state = mission.get("resume_state") or "created"
        db.update_mission_state(mission_id, resume_state, {"resume_state": None})
        return

    # 默认：human_pending → feedback
    resume_state = mission.get("resume_state") or "feedback"
    db.update_mission_state(mission_id, resume_state, {"resume_state": None})


# ── 辅助函数 ────────────────────────────────────────────────────────────────


def _split_field(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").replace("，", ",").split(",") if v.strip()]


def _merge_list(existing: Any, additions: List[str]) -> List[str]:
    values = _split_field(existing)
    seen = {v.lower() for v in values}
    for item in additions:
        if item.lower() not in seen:
            values.append(item)
            seen.add(item.lower())
    return values
