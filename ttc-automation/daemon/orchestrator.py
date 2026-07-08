"""Orchestrator background loop: advance Mission state machines.

Runs inside the FastAPI process as an asyncio task. Polls missions every N
seconds, calls the appropriate agent for the current state, and applies state
updates / human tasks.
"""

import asyncio
import json
from typing import Any

from agents import (
    calling_agent,
    classify_artifact,
    feedback_agent,
    human_review_agent,
    jd_parse_agent,
    record_agent_run,
    scoring_agent,
    sourcing_agent,
)
from db import (
    get_artifact,
    get_mission,
    insert_artifact,
    insert_human_task,
    insert_mission,
    insert_read_job,
    list_human_tasks,
    list_missions,
    update_artifact,
    update_mission,
    update_read_job,
)
import notifier

POLL_INTERVAL_SECONDS = 5


def _json_load(s: Any) -> Any:
    return json.loads(s) if isinstance(s, str) else (s or {})


async def process_read_job(rid: str) -> None:
    row = insert_read_job  # placeholder to keep import; actual below
    job = {"id": rid}  # type: ignore  # filled below


async def advance_mission(mid: str) -> None:
    mission = get_mission(mid)
    if not mission:
        return

    status = mission["status"]
    artifact = get_artifact(mission["artifact_id"]) or {}

    if status == "created":
        result = jd_parse_agent(mission)
        record_agent_run(mid, "jd_parse_agent", mission.get("jd_struct"), result,
                         "success" if result["status"] != "problem_pending" else "problem")
        if result["status"] == "problem_pending":
            update_mission(mid, {
                "status": "problem_pending",
                "problem_reason": result.get("problem_reason"),
                "jd_struct": json.dumps(result.get("jd_struct"), ensure_ascii=False),
            })
            await create_human_task(mid, "problem_solve", {
                "problem_reason": result.get("problem_reason"),
                "context": {"artifact_id": mission["artifact_id"]},
            })
        else:
            update_mission(mid, {
                "status": "jd_parsed",
                "jd_struct": json.dumps(result["jd_struct"], ensure_ascii=False),
            })

    elif status == "jd_parsed":
        result = sourcing_agent(mission)
        record_agent_run(mid, "sourcing_agent", mission.get("jd_struct"), result,
                         "success" if result["status"] != "problem_pending" else "problem")
        if result["status"] == "problem_pending":
            update_mission(mid, {
                "status": "problem_pending",
                "problem_reason": result.get("problem_reason"),
            })
            await create_human_task(mid, "problem_solve", {
                "problem_reason": result.get("problem_reason"),
                "context": {"jd_struct": _json_load(mission.get("jd_struct"))},
            })
        else:
            update_mission(mid, {
                "status": "sourcing",
                "candidates_json": json.dumps(result["candidates"], ensure_ascii=False),
            })

    elif status == "sourcing":
        candidates = _json_load(mission.get("candidates_json"))
        result = scoring_agent(mission, candidates)
        record_agent_run(mid, "scoring_agent", mission.get("candidates_json"), result,
                         "success")
        update_mission(mid, {
            "status": "scored",
            "scores_json": json.dumps(result["scores"], ensure_ascii=False),
        })

    elif status == "scored":
        scores = _json_load(mission.get("scores_json"))
        result = human_review_agent(mission, scores)
        record_agent_run(mid, "human_review_agent", mission.get("scores_json"), result,
                         "success")
        if result["status"] == "human_review":
            update_mission(mid, {"status": "human_review"})
            await create_human_task(mid, result["task_type"], result["task_payload"])
        else:
            update_mission(mid, {"status": "calling"})

    elif status == "calling":
        scores = _json_load(mission.get("scores_json"))
        result = calling_agent(mission, scores)
        record_agent_run(mid, "calling_agent", mission.get("scores_json"), result,
                         "success")
        update_mission(mid, {
            "status": "human_pending",
            "call_list_json": json.dumps(result["call_list"], ensure_ascii=False),
        })
        for item in result["call_list"]:
            await create_human_task(mid, "phone_call", item)

    elif status == "human_pending":
        tasks = list_human_tasks(mission_id=mid, status=None)
        pending = [t for t in tasks if t["status"] != "completed" and t["status"] != "processed"]
        if not pending:
            update_mission(mid, {"status": "feedback"})

    elif status == "feedback":
        tasks = list_human_tasks(mission_id=mid)
        result = feedback_agent(mission, tasks)
        record_agent_run(mid, "feedback_agent", {}, result, "success")
        update_mission(mid, {
            "status": "closed",
            "feedback_json": json.dumps(result["feedback"], ensure_ascii=False),
        })


async def create_human_task(mid: str, task_type: str, payload: dict) -> None:
    html_url = f"/human/task/{mid}_{task_type}"
    tid = insert_human_task(mid, task_type, payload, assignee=None, html_url=html_url)
    mission = get_mission(mid) or {}
    try:
        await asyncio.to_thread(notifier.notify_new_task,
                                {"id": tid, "task_type": task_type, "payload": payload},
                                mission)
    except Exception as exc:
        print(f"[notifier] failed to notify new task: {exc}")


async def ingest_and_route(data: dict[str, Any]) -> dict[str, Any]:
    """Entry point used by FastAPI ingest endpoints.

    1. Create read_job
    2. Classify + normalize into artifact
    3. If high-confidence JD, create Mission and let orchestrator advance it
    """
    rid = insert_read_job({
        "source_type": data.get("source_type", "unknown"),
        "source_url": data.get("source_url"),
        "title": data.get("title"),
        "content": data.get("content"),
        "markdown": data.get("markdown"),
        "read_method": data.get("read_method", "userscript"),
        "read_status": "succeeded",
    })

    content = data.get("markdown") or (data.get("content") if isinstance(data.get("content"), str) else "")
    classification = classify_artifact(content, data.get("title"))

    update_read_job(rid, {
        "content_type_guess": classification.get("artifact_type"),
        "confidence": classification.get("confidence", "中"),
        "extracted_fields": json.dumps(classification.get("extracted_fields") or {}, ensure_ascii=False),
    })

    aid = insert_artifact({
        "read_job_id": rid,
        "artifact_type": classification.get("artifact_type", "unknown"),
        "title": data.get("title"),
        "content": data.get("content"),
        "markdown": data.get("markdown"),
        "confidence": classification.get("confidence", "中"),
        "extracted_fields": classification.get("extracted_fields"),
        "normalized_data": classification.get("extracted_fields"),
        "status": "normalized",
    })

    result = {"read_job_id": rid, "artifact_id": aid, "artifact_type": classification.get("artifact_type")}

    if classification.get("artifact_type") == "jd" and classification.get("confidence") in ("高", "中"):
        mid = insert_mission(aid, jd_struct=classification.get("extracted_fields"))
        result["mission_id"] = mid
        result["message"] = "JD detected, Mission created. Orchestrator will auto-advance."
    else:
        result["message"] = "Content classified and stored; not high-confidence JD, no Mission created."

    return result


async def orchestrator_loop() -> None:
    while True:
        try:
            missions = list_missions(limit=500)
            active_statuses = {
                "created", "jd_parsed", "sourcing", "scored", "calling",
                "human_pending", "feedback",
            }
            for m in missions:
                if m["status"] in active_statuses:
                    try:
                        await advance_mission(m["id"])
                    except Exception as exc:
                        print(f"[orchestrator] error advancing {m['id']}: {exc}")
        except Exception as exc:
            print(f"[orchestrator] loop error: {exc}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start_orchestrator() -> None:
    asyncio.create_task(orchestrator_loop())
