"""AI Orchestrator：招聘任务的中心调度器。

状态机（完整版）：
  created → jd_parsed → sourcing → scored
     → human_review（有 risk_flags 或 needs_human_review）
     → calling（生成电话任务 + human_tasks）
     → human_pending（等待人类完成通话）
     → feedback（复盘 + 权重校准）
     → closed

  任意状态均可跳入 problem_pending（人工解决后 resume）

设计原则：
- AI 默认自动推进；遇到异常或信息缺失时，才暂停并生成 HTML 任务页调度人。
- Mission 由 mission_router 从 normalized_artifact 创建，通常已带有 jd_fields。
"""
import json
import logging
from typing import Any, Dict, List, Optional

from .. import db
from . import jd_agent, sourcing_agent, scoring_agent, outreach_agent, human_dispatch, feedback_agent, position_allocator

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
            cand["dimension_scores"] = _json_field(cand.get("dimension_scores"), {})
            cand["evidence_binding"] = _json_field(cand.get("evidence_binding"), [])
            cand["verification_questions"] = _json_field(cand.get("verification_questions"), [])
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


# ---------------------------------------------------------------------------
# 核心状态机
# ---------------------------------------------------------------------------

def step_mission(mission: Dict[str, Any]) -> None:
    """根据当前状态推进 Mission 一步。"""
    mid = mission["id"]
    state = mission["state"]
    logger.info("Step mission %s state=%s", mid, state)

    # ── created ──────────────────────────────────────────────────────────
    if state == "created":
        _step_created(mission)
        return

    # ── jd_parsed ────────────────────────────────────────────────────────
    if state == "jd_parsed":
        _step_jd_parsed(mission)
        return

    # ── sourcing ─────────────────────────────────────────────────────────
    if state == "sourcing":
        _step_sourcing(mission)
        return

    # ── scored ───────────────────────────────────────────────────────────
    if state == "scored":
        _step_scored(mission)
        return

    # ── human_review ─────────────────────────────────────────────────────
    if state == "human_review":
        _step_human_review(mission)
        return

    # ── calling ──────────────────────────────────────────────────────────
    if state == "calling":
        _step_calling(mission)
        return

    # ── human_pending ────────────────────────────────────────────────────
    if state == "human_pending":
        _step_human_pending(mission)
        return

    # ── problem_pending ──────────────────────────────────────────────────
    if state == "problem_pending":
        # 等待人类解决后 resume，调度器不做任何操作
        return

    # ── feedback ─────────────────────────────────────────────────────────
    if state == "feedback":
        _step_feedback(mission)
        return


# ---------------------------------------------------------------------------
# 各状态处理函数
# ---------------------------------------------------------------------------

def _step_created(mission: Dict[str, Any]) -> None:
    """created → jd_parsed 或 problem_pending"""
    mid = mission["id"]
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
    # 初始化仓位
    position_allocator.init_mission_allocation(db.get_mission(mid))


def _step_jd_parsed(mission: Dict[str, Any]) -> None:
    """jd_parsed → sourcing 或 problem_pending"""
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
    db.update_mission_state(mission["id"], "sourcing", {"candidate_ids": candidate_ids})


def _step_sourcing(mission: Dict[str, Any]) -> None:
    """sourcing → scored 或 problem_pending"""
    candidates = _load_candidates(mission)
    jd_fields = _json_field(mission.get("jd_fields"), {})
    try:
        score_result = scoring_agent.score(mission, candidates, jd_fields)
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

    # 处理合规问题：为每个有合规问题的候选人创建合规仲裁任务
    compliance_candidates = score_result.get("compliance_candidates", [])
    compliance_task_ids = []
    for cc in compliance_candidates:
        cid = cc.get("candidate_id", "")
        candidate = next((c for c in candidates if c.get("id") == cid), {})
        tid = human_dispatch.create_problem_task(
            mission["id"],
            role="compliance_officer",
            task_type="compliance",
            payload={
                "title": f"合规仲裁：{cc.get('name', '候选人')}",
                "content": json.dumps(cc.get("issues", []), ensure_ascii=False, indent=2),
                "candidate_id": cid,
                "candidate": candidate,
                "issues": cc.get("issues", []),
                "resume_state": "calling",
            },
        )
        compliance_task_ids.append(tid)

    db.update_mission_state(
        mission["id"],
        "scored",
        {
            "compliance_task_ids": compliance_task_ids,
            "scoring_summary": score_result.get("summary", {}),
        },
    )


def _step_scored(mission: Dict[str, Any]) -> None:
    """scored → human_review（有风险）或 calling（无风险）

    检查条件：
    1. 候选人有 risk_flags（红灯/黄灯）
    2. needs_human_review 标记（评分一致性差）
    3. confidence 低于阈值
    """
    mid = mission["id"]
    candidates = _load_candidates(mission)
    jd_fields = _json_field(mission.get("jd_fields"), {})

    # 检查是否有合规任务待处理
    config = _json_field(mission.get("config"), {})
    compliance_task_ids = config.get("compliance_task_ids", [])
    if compliance_task_ids:
        pending_compliance = []
        for tid in compliance_task_ids:
            task = db.get_human_task(tid)
            if task and task.get("status") not in ("completed",):
                pending_compliance.append(tid)
        if pending_compliance:
            # 合规任务未全部完成，不继续推进
            logger.info("Mission %s waiting for %d compliance tasks", mid, len(pending_compliance))
            return

    # 筛选需要人工审核的候选人
    review_candidates = []
    safe_candidates = []
    for cand in candidates:
        risk_flags = cand.get("risk_flags", []) or []
        needs_review = cand.get("needs_human_review", False)
        confidence = cand.get("confidence", "medium")
        has_red_flag = any(
            rf.get("severity") == "red" for rf in risk_flags
            if isinstance(rf, dict)
        )

        if has_red_flag or needs_review or confidence == "low":
            review_candidates.append(cand)
        else:
            safe_candidates.append(cand)

    if review_candidates:
        # 有需要审核的候选人 → 生成 review_task
        review_payload = {
            "title": f"顾问审核：{len(review_candidates)} 位候选人需要人工判断",
            "content": _format_review_content(review_candidates, jd_fields),
            "review_candidates": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "overall_score": c.get("overall_score"),
                    "level": c.get("level"),
                    "risk_flags": c.get("risk_flags"),
                    "confidence": c.get("confidence"),
                }
                for c in review_candidates
            ],
            "jd_fields": jd_fields,
            "resume_state": "calling",
        }
        tid = human_dispatch.create_problem_task(
            mission["id"],
            role="client_advisor",
            task_type="review",
            payload=review_payload,
        )
        db.update_mission_state(
            mid,
            "human_review",
            {
                "resume_state": "calling",
                "human_task_ids": [tid],
                "review_candidate_ids": [c.get("id") for c in review_candidates],
            },
        )
        logger.info(
            "Mission %s → human_review: %d candidates flagged for review (of %d total)",
            mid, len(review_candidates), len(candidates),
        )
        return

    # 无风险 → 直接进入 calling
    db.update_mission_state(mid, "calling")
    logger.info("Mission %s → calling (no risk flags, skipping human_review)", mid)


def _step_human_review(mission: Dict[str, Any]) -> None:
    """human_review → calling（审核通过）或 closed（驳回）

    等待 human_task 完成后，由 human_dispatch.complete_task 触发 resume。
    调度器轮询时检查任务状态。
    """
    mid = mission["id"]
    tasks = db.get_mission_human_tasks(mid)
    review_tasks = [t for t in tasks if t.get("task_type") == "review"]

    if not review_tasks:
        # 无审核任务，直接推进
        db.update_mission_state(mid, "calling")
        return

    # 检查是否有审核任务已完成
    completed_reviews = [t for t in review_tasks if t.get("status") == "completed"]
    if not completed_reviews:
        # 还在等待审核
        return

    # 审核已完成 → 检查结果
    all_approved = True
    any_rejected = False
    for t in completed_reviews:
        result = _json_field(t.get("result"), {})
        outcome = result.get("outcome", "")
        if outcome == "rejected":
            any_rejected = True
            all_approved = False
        elif outcome == "need_more_info":
            all_approved = False

    if all_approved:
        logger.info("Mission %s review approved, advancing to calling", mid)
        db.update_mission_state(mid, "calling", {"resume_state": None})
    elif any_rejected:
        logger.info("Mission %s review rejected, closing", mid)
        db.update_mission_state(
            mid, "closed",
            {"outcome": "review_rejected", "closed_at": db.now_iso()},
        )
    else:
        # need_more_info → 转为 problem_pending
        _pause_for_human(
            mission,
            role="client_advisor",
            task_type="review",
            problem="审核结果为需要补充信息，请进一步处理。",
            payload={"resume_state": "calling"},
            resume_state="calling",
        )


def _step_calling(mission: Dict[str, Any]) -> None:
    """calling → human_pending（生成电话任务 + human_tasks）"""
    mid = mission["id"]
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
            resume_state="calling",
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
        logger.info("Mission %s → human_pending (%d call tasks)", mid, len(task_ids))
    else:
        _pause_for_human(
            mission,
            role="client_advisor",
            task_type="source_help",
            problem="评分后无合格候选人进入电话清单。请人工确认是否放宽条件或补充人才来源。",
            payload={"jd_fields": jd_fields, "candidates": candidates},
            resume_state="calling",
        )


def _step_human_pending(mission: Dict[str, Any]) -> None:
    """human_pending → feedback（所有人类任务完成）或 closed（停滞）"""
    mid = mission["id"]
    tasks = db.get_mission_human_tasks(mid)
    if not tasks:
        db.update_mission_state(mid, "closed", {"outcome": "stalled", "closed_at": db.now_iso()})
        return
    if all(t["status"] == "completed" for t in tasks):
        resume_state = _json_field(mission.get("config"), {}).get("resume_state")
        if not resume_state:
            resume_state = mission.get("resume_state") or "feedback"
        db.update_mission_state(mid, resume_state, {"resume_state": None})


def _step_feedback(mission: Dict[str, Any]) -> None:
    """feedback → closed：生成复盘报告、校准权重、更新仓位，然后关闭 Mission。"""
    mid = mission["id"]
    try:
        report = feedback_agent.process_feedback_state(mission)
        logger.info("Mission %s feedback processed: hit_rate=%.1f%%",
                    mid, report.get("summary", {}).get("hit_rate", 0) * 100)
    except Exception as e:
        logger.exception("Feedback processing failed for mission %s: %s", mid, e)
        report = {"error": str(e)}

    # 更新仓位状态（基于反馈信号）
    try:
        new_alloc, alloc_reason = position_allocator.update_allocation(mid)
        logger.info("Mission %s allocation updated: %s (reason: %s)", mid, new_alloc, alloc_reason)
    except Exception as e:
        logger.exception("Allocation update failed for mission %s: %s", mid, e)

    db.update_mission_state(
        mid,
        "closed",
        {
            "outcome": "completed",
            "closed_at": db.now_iso(),
            "feedback_report": report,
        },
    )
    logger.info("Mission %s → closed (completed with feedback)", mid)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _format_review_content(
    review_candidates: List[Dict[str, Any]], jd_fields: Dict[str, Any]
) -> str:
    """格式化审核内容为可读文本。"""
    lines = [
        f"岗位：{jd_fields.get('company', '未知公司')} - {jd_fields.get('position', '未知岗位')}",
        f"地点：{jd_fields.get('location', '未指定')}",
        f"需要审核 {len(review_candidates)} 位候选人：",
        "",
    ]
    for i, c in enumerate(review_candidates, 1):
        risk_flags = c.get("risk_flags", []) or []
        flags_str = "; ".join(
            rf.get("flag", str(rf)) if isinstance(rf, dict) else str(rf)
            for rf in risk_flags
        )
        lines.append(
            f"{i}. {c.get('name', '未知')} — "
            f"评分 {c.get('overall_score', '?')}（{c.get('level', '?')}）"
        )
        if flags_str:
            lines.append(f"   风险信号：{flags_str}")
        verification = c.get("verification_questions", [])
        if verification:
            lines.append(f"   建议追问：{verification[0][:80]}...")
        lines.append("")
    return "\n".join(lines)
