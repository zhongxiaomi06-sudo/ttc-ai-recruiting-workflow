"""AI Orchestrator：招聘任务的中心调度器。

设计原则：
- AI 默认自动推进；遇到异常或信息缺失时，才暂停并生成 HTML 任务页调度人。
- Mission 由 mission_router 从 normalized_artifact 创建，通常已带有 jd_fields。
"""
import json
import logging
from typing import Dict, Any, List, Optional

from .. import db
from . import jd_agent, sourcing_agent, scoring_agent, outreach_agent, human_dispatch

logger = logging.getLogger(__name__)


def _json_field(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _get_jd_record(mission: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    jd_record_id = mission.get("jd_record_id")
    if jd_record_id:
        row = db.get_conn().execute(
            "SELECT * FROM ingest_records WHERE id = ?", (jd_record_id,)
        ).fetchone()
        if row:
            return dict(row)
    rows = db.get_latest_jd(limit=1)
    return rows[0] if rows else None


def _load_candidates(mission: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidate_ids = _json_field(mission.get("candidate_ids"), [])
    candidates = []
    for cid in candidate_ids:
        row = db.get_conn().execute("SELECT * FROM candidates WHERE id = ?", (cid,)).fetchone()
        if row:
            cand = dict(row)
            cand["source_types"] = _json_field(cand.get("source_types"), [])
            cand["raw_profile"] = _json_field(cand.get("raw_profile"), {})
            cand["enriched_profile"] = _json_field(cand.get("enriched_profile"), {})
            cand["risk_flags"] = _json_field(cand.get("risk_flags"), [])
            candidates.append(cand)
    return candidates


def start_mission(
    jd_record_id: Optional[str] = None,
    normalized_artifact_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """启动一个新的招聘任务 Mission。"""
    mid = db.insert_mission(jd_record_id, normalized_artifact_id, config)
    logger.info(
        "Mission started %s (artifact=%s, jd=%s)",
        mid, normalized_artifact_id, jd_record_id,
    )
    return mid


def _pause_for_human(
    mission: Dict[str, Any],
    role: str,
    task_type: str,
    problem: str,
    payload: Dict[str, Any],
    resume_state: str,
) -> None:
    """暂停 Mission，生成一个人类解决问题的任务。"""
    payload["problem"] = problem
    payload["resume_state"] = resume_state
    payload.setdefault("resume_action", task_type)
    tid = human_dispatch.create_problem_task(mission["id"], role, task_type, payload)
    db.update_mission_state(
        mission["id"],
        "problem_pending",
        {"resume_state": resume_state, "human_task_ids": [tid]},
    )
    logger.warning(
        "Mission %s paused for human (%s). Task=%s resume_state=%s problem=%s",
        mission["id"], role, tid, resume_state, problem,
    )


def process_pending_missions() -> None:
    """轮询并推进所有未完成的 Mission。"""
    missions = db.get_pending_missions()
    if missions:
        logger.info("Processing %s pending missions", len(missions))
    for mission in missions:
        try:
            step_mission(mission)
        except Exception as e:
            logger.exception("Mission step failed %s: %s", mission["id"], e)
            try:
                _pause_for_human(
                    mission,
                    role="system_operator",
                    task_type="runtime_error",
                    problem=f"Orchestrator 异常：{e}",
                    payload={"state": mission["state"], "error": str(e)},
                    resume_state=mission["state"],
                )
            except Exception:
                logger.exception("Failed to create error human task for mission %s", mission["id"])


def step_mission(mission: Dict[str, Any]) -> None:
    """根据当前状态推进 Mission 一步。"""
    mid = mission["id"]
    state = mission["state"]
    logger.info("Step mission %s state=%s", mid, state)

    if state == "created":
        jd_fields = _json_field(mission.get("jd_fields"), {})
        if not jd_fields:
            artifact = db.get_normalized_artifact(mission.get("normalized_artifact_id") or "")
            if artifact:
                jd_fields = _json_field(artifact.get("normalized_payload"), {})
        if not jd_fields:
            jd_record = _get_jd_record(mission)
            if not jd_record:
                logger.warning("Mission %s has no JD; closing", mid)
                db.update_mission_state(mid, "closed", {"outcome": "no_jd_record", "closed_at": db.now_iso()})
                return
            try:
                jd_fields = jd_agent.parse(mission, jd_record)
            except Exception as e:
                _pause_for_human(
                    mission,
                    role="client_advisor",
                    task_type="jd_clarify",
                    problem=f"JD 解析失败：{e}",
                    payload={"jd_record": dict(jd_record)},
                    resume_state="created",
                )
                return
        if not jd_fields.get("position") and not jd_fields.get("skills"):
            _pause_for_human(
                mission,
                role="client_advisor",
                task_type="jd_clarify",
                problem="JD 解析置信度低：未识别出岗位名称和关键技能，需要人工补充。",
                payload={"jd_fields": jd_fields},
                resume_state="created",
            )
            return
        db.update_mission_state(mid, "jd_parsed", {"jd_fields": jd_fields})
        return

    if state == "jd_parsed":
        jd_fields = _json_field(mission.get("jd_fields"), {})
        try:
            candidates = sourcing_agent.search(mission, jd_fields)
        except Exception as e:
            _pause_for_human(
                mission,
                role="sourcing_researcher",
                task_type="source_help",
                problem=f"人才搜索失败：{e}",
                payload={"jd_fields": jd_fields},
                resume_state="jd_parsed",
            )
            return
        if not candidates:
            _pause_for_human(
                mission,
                role="sourcing_researcher",
                task_type="source_help",
                problem="未召回任何候选人。请人工补充搜索渠道、关键词或人才库信息。",
                payload={"jd_fields": jd_fields},
                resume_state="jd_parsed",
            )
            return
        candidate_ids = [c.get("id") for c in candidates if c.get("id")]
        db.update_mission_state(mid, "sourcing", {"candidate_ids": candidate_ids})
        return

    if state == "sourcing":
        candidates = _load_candidates(mission)
        jd_fields = _json_field(mission.get("jd_fields"), {})
        try:
            scoring_agent.score(mission, candidates, jd_fields)
        except Exception as e:
            _pause_for_human(
                mission,
                role="client_advisor",
                task_type="scoring_conflict",
                problem=f"评分排序失败：{e}",
                payload={"jd_fields": jd_fields, "candidates": candidates},
                resume_state="sourcing",
            )
            return
        db.update_mission_state(mid, "scored")
        return

    if state == "scored":
        candidates = _load_candidates(mission)
        jd_fields = _json_field(mission.get("jd_fields"), {})
        try:
            call_items = outreach_agent.generate_call_tasks(mission, candidates, jd_fields)
        except Exception as e:
            _pause_for_human(
                mission,
                role="client_advisor",
                task_type="outreach_problem",
                problem=f"生成电话任务失败：{e}",
                payload={"jd_fields": jd_fields, "candidates": candidates},
                resume_state="scored",
            )
            return
        if call_items:
            task_ids = human_dispatch.create_call_tasks(mission, call_items)
            db.update_mission_state(
                mid,
                "human_pending",
                {
                    "resume_state": "feedback",
                    "call_list_ids": [i["id"] for i in call_items],
                    "human_task_ids": task_ids,
                },
            )
        else:
            _pause_for_human(
                mission,
                role="client_advisor",
                task_type="source_help",
                problem="评分后无合格候选人进入电话清单。请人工确认是否放宽条件或补充人才来源。",
                payload={"jd_fields": jd_fields, "candidates": candidates},
                resume_state="scored",
            )
        return

    if state == "problem_pending":
        return

    if state == "human_pending":
        tasks = db.get_mission_human_tasks(mid)
        if not tasks:
            db.update_mission_state(mid, "closed", {"outcome": "stalled", "closed_at": db.now_iso()})
            return
        if all(t["status"] == "completed" for t in tasks):
            resume_state = _json_field(mission.get("config"), {}).get("resume_state")
            if not resume_state:
                resume_state = mission.get("resume_state") or _json_field(tasks[0].get("payload"), {}).get("resume_state", "scored")
            db.update_mission_state(mid, resume_state, {"resume_state": None})
        return

    if state == "feedback":
        db.update_mission_state(mid, "closed", {"outcome": "completed", "closed_at": db.now_iso()})
        return
