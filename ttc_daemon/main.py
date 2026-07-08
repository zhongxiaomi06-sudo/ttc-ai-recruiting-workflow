import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from . import db, scheduler
from .agents import human_dispatch
from .config import API_TOKEN, DAEMON_HOST, DAEMON_PORT
from .pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def require_api_token(x_ttc_token: Optional[str] = Header(default=None)) -> None:
    """Protect server write APIs when TTC_API_TOKEN is configured."""
    if API_TOKEN and x_ttc_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing TTC API token")


# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------
class IngestPayload(BaseModel):
    source_type: str
    source_url: Optional[str] = ""
    title: Optional[str] = ""
    raw_text: str = ""
    markdown: Optional[str] = ""
    collected_at: Optional[str] = None
    model_config = {"extra": "allow"}


class ResumePayload(BaseModel):
    candidate: Dict[str, Any]
    source_type: str = "candidate_collector"


class FileIngestPayload(BaseModel):
    file_path: str
    source_type: str = "local_file"
    title: Optional[str] = ""
    source_url: Optional[str] = ""
    model_config = {"extra": "allow"}


class PipelineRunRequest(BaseModel):
    jd_record_id: Optional[str] = None


class FeedbackPayload(BaseModel):
    candidate_id: str
    call_list_id: Optional[str] = None
    outcome: str
    notes: Optional[str] = ""


class MissionStartRequest(BaseModel):
    jd_record_id: Optional[str] = None
    normalized_artifact_id: Optional[str] = None


# ---------------------------------------------------------------------------
# 后台调度器
# ---------------------------------------------------------------------------
SCHEDULER_INTERVAL = int(os.getenv("TTC_SCHEDULER_INTERVAL", "10"))


def _scheduler_loop():
    while True:
        try:
            scheduler.tick()
        except Exception:
            logger.exception("Scheduler tick error")
        time.sleep(SCHEDULER_INTERVAL)


def start_background_scheduler():
    t = threading.Thread(target=_scheduler_loop, daemon=True)
    t.start()
    logger.info("Started scheduler (interval=%ss)", SCHEDULER_INTERVAL)


# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    logger.info("TTC Daemon DB initialized at %s", db.DB_PATH)
    start_background_scheduler()
    yield


app = FastAPI(title="TTC Daemon", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 接收输入：统一创建 read_job
# ---------------------------------------------------------------------------
def _create_read_job_from_payload(payload: IngestPayload, source_type: Optional[str] = None) -> str:
    job = {
        "source_type": source_type or payload.source_type,
        "source_url": payload.source_url or "",
        "title": payload.title or "",
        "raw_text": payload.raw_text or "",
        "markdown": payload.markdown or payload.raw_text or "",
        "status": "pending",
        "capture_meta": {
            "collected_at": payload.collected_at,
        },
    }
    return db.insert_read_job(job)


@app.post("/ingest/feishu", dependencies=[Depends(require_api_token)])
def ingest_feishu(payload: IngestPayload):
    jid = _create_read_job_from_payload(payload)
    logger.info("Ingest feishu queued as read job %s from %s", jid, payload.source_url)
    return {"ok": True, "read_job_id": jid}


@app.post("/ingest/link", dependencies=[Depends(require_api_token)])
def ingest_link(payload: IngestPayload):
    jid = _create_read_job_from_payload(payload)
    logger.info("Ingest link queued as read job %s from %s", jid, payload.source_url)
    return {"ok": True, "read_job_id": jid}


@app.get("/ingest/read-link", dependencies=[Depends(require_api_token)])
def read_and_ingest_link(url: str = Query(..., description="URL to read automatically")):
    """提交一个 URL 读取任务，由调度器异步完成读取、分类、归一化、路由。"""
    job = {
        "source_type": "web_page",
        "source_url": url,
        "status": "pending",
    }
    if "chatgpt.com/share" in url or "chat.openai.com/share" in url:
        job["source_type"] = "chatgpt_share"
    jid = db.insert_read_job(job)
    logger.info("URL read queued as job %s: %s", jid, url)
    return {"ok": True, "read_job_id": jid, "url": url}


@app.post("/ingest/resume", dependencies=[Depends(require_api_token)])
def ingest_resume(payload: ResumePayload):
    cand = payload.candidate
    cand.setdefault("source_types", []).append(payload.source_type)
    job = {
        "source_type": "candidate_resume",
        "source_url": cand.get("source_url", ""),
        "title": cand.get("name", "Candidate"),
        "raw_text": json.dumps(cand, ensure_ascii=False),
        "markdown": "",
        "status": "pending",
    }
    jid = db.insert_read_job(job)
    logger.info("Resume queued as read job %s", jid)
    return {"ok": True, "read_job_id": jid}


@app.post("/ingest/file", dependencies=[Depends(require_api_token)])
def ingest_file(payload: FileIngestPayload):
    job = {
        "source_type": payload.source_type,
        "source_url": payload.source_url or payload.file_path,
        "title": payload.title or "",
        "status": "pending",
        "payload": {"file_path": payload.file_path},
        "capture_meta": {"input": "local_file"},
    }
    jid = db.insert_read_job(job)
    logger.info("File queued as read job %s: %s", jid, payload.file_path)
    return {"ok": True, "read_job_id": jid, "file_path": payload.file_path}


@app.get("/ingest/job/{jid}")
def get_read_job_status(jid: str):
    job = db.get_read_job(jid)
    if not job:
        return {"ok": False, "error": "Read job not found"}
    return {"ok": True, "job": job}


# ---------------------------------------------------------------------------
# Mission / Agent 编排
# ---------------------------------------------------------------------------
@app.post("/mission/start", dependencies=[Depends(require_api_token)])
def mission_start(req: MissionStartRequest):
    """手动启动 Mission（通常由 mission_router 自动完成）。"""
    from .agents.orchestrator import start_mission
    from .ingestion import artifact_classifier, normalizer

    if req.normalized_artifact_id:
        artifact = db.get_normalized_artifact(req.normalized_artifact_id)
        if not artifact:
            return {"ok": False, "error": "Normalized artifact not found"}
        if artifact.get("artifact_type") != "jd" or float(artifact.get("confidence") or 0) < 0.6:
            return {"ok": False, "error": "Only high-confidence JD artifacts can start a Mission"}
        mid = start_mission(normalized_artifact_id=req.normalized_artifact_id)
        db.update_mission_state(mid, "created", {"jd_fields": json.loads(artifact.get("normalized_payload") or "{}")})
        db.update_normalized_artifact(req.normalized_artifact_id, {"status": "mission_created", "mission_id": mid})
        return {"ok": True, "mission_id": mid, "normalized_artifact_id": req.normalized_artifact_id}

    if req.jd_record_id:
        record = db.get_ingest(req.jd_record_id)
        if not record:
            return {"ok": False, "error": "JD record not found"}
        artifact_type, confidence, reason = artifact_classifier.classify(record)
        if artifact_type != "jd" or confidence < 0.6:
            return {
                "ok": False,
                "error": "Record is not a high-confidence JD",
                "artifact_type": artifact_type,
                "confidence": confidence,
                "reason": reason,
            }
        payload = normalizer.normalize("jd", record)
        aid = db.insert_normalized_artifact(
            {
                "raw_ingest_id": req.jd_record_id,
                "artifact_type": "jd",
                "confidence": confidence,
                "reason": reason,
                "normalized_payload": payload,
                "status": "pending",
            }
        )
        mid = start_mission(jd_record_id=req.jd_record_id, normalized_artifact_id=aid)
        db.update_mission_state(mid, "created", {"jd_fields": payload})
        db.update_normalized_artifact(aid, {"status": "mission_created", "mission_id": mid})
        return {"ok": True, "mission_id": mid, "jd_record_id": req.jd_record_id, "normalized_artifact_id": aid}

    artifacts = db.get_unrouted_jd_artifacts(limit=1)
    if not artifacts:
        return {"ok": False, "error": "No unrouted high-confidence JD artifact found"}
    artifact = artifacts[0]
    mid = start_mission(normalized_artifact_id=artifact["id"])
    db.update_mission_state(mid, "created", {"jd_fields": json.loads(artifact.get("normalized_payload") or "{}")})
    db.update_normalized_artifact(artifact["id"], {"status": "mission_created", "mission_id": mid})
    return {"ok": True, "mission_id": mid, "normalized_artifact_id": artifact["id"]}


@app.get("/mission/{mid}")
def mission_status(mid: str):
    mission = db.get_mission(mid)
    if not mission:
        return {"ok": False, "error": "Mission not found"}
    return {
        "ok": True,
        "mission": mission,
        "human_tasks": db.get_mission_human_tasks(mid),
        "agent_runs": db.get_mission_agent_runs(mid),
    }


@app.post("/mission/{mid}/step", dependencies=[Depends(require_api_token)])
def mission_step(mid: str):
    """手动推进 Mission 一步（主要用于调试）。"""
    from .agents.orchestrator import step_mission
    mission = db.get_mission(mid)
    if not mission:
        return {"ok": False, "error": "Mission not found"}
    step_mission(mission)
    return {"ok": True, "mission_id": mid, "state": db.get_mission(mid)["state"]}


# ---------------------------------------------------------------------------
# 工作流与输出（兼容旧版 pipeline）
# ---------------------------------------------------------------------------
@app.post("/pipeline/run", dependencies=[Depends(require_api_token)])
def pipeline_run(req: PipelineRunRequest):
    result = run_pipeline(req.jd_record_id)
    return result


@app.get("/api/call-list")
def get_call_list(status: Optional[str] = None, limit: int = 100):
    rows = db.get_call_list(status=status, limit=limit)
    for r in rows:
        for k in ["talking_points", "evidence"]:
            if r.get(k):
                try:
                    r[k] = json.loads(r[k])
                except Exception:
                    pass
    return {"ok": True, "count": len(rows), "items": rows}


@app.post("/feedback", dependencies=[Depends(require_api_token)])
def feedback(payload: FeedbackPayload):
    fb = payload.model_dump()
    fid = db.insert_feedback(fb)
    logger.info("Feedback recorded %s for candidate %s", fid, payload.candidate_id)
    return {"ok": True, "id": fid}


# ---------------------------------------------------------------------------
# 人类工具：HTML 任务页面
# ---------------------------------------------------------------------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """AI 猎头工作台：展示 Mission 和待办人类任务。"""
    missions = db.get_pending_missions()
    with db.get_conn() as conn:
        closed = conn.execute(
            "SELECT * FROM missions WHERE state = 'closed' ORDER BY updated_at DESC LIMIT 10"
        ).fetchall()
    missions += [dict(r) for r in closed]
    pending_tasks = db.list_pending_human_tasks(limit=100)
    html = human_dispatch.render_dashboard(missions, pending_tasks, api_token=API_TOKEN)
    return HTMLResponse(html)


@app.get("/human/tasks")
def list_human_tasks(status: Optional[str] = None, limit: int = 100):
    if status:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM human_tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return {"ok": True, "items": [dict(r) for r in rows]}
    return {"ok": True, "items": db.list_pending_human_tasks(limit=limit)}


@app.get("/human/task/{tid}", response_class=HTMLResponse)
def human_task_page(tid: str):
    html = human_dispatch.get_task_html(tid)
    return HTMLResponse(html)


@app.post("/human/task/{tid}/complete")
async def complete_human_task(tid: str, request: Request):
    form = await request.form()
    result = {k: str(v) for k, v in form.items()}
    human_dispatch.complete_task(tid, result)
    return RedirectResponse(url="/dashboard", status_code=303)


# ---------------------------------------------------------------------------
# 测试控制台
# ---------------------------------------------------------------------------
@app.get("/console", response_class=HTMLResponse)
def test_console():
    """提供一个可视化测试页面，方便本地或云端部署后快速验证工作流。"""
    html = human_dispatch._jinja_env.get_template("console.html").render()
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Admin / 运维接口
# ---------------------------------------------------------------------------
@app.get("/admin/source-talent")
def admin_source_talent_info():
    """查看 Source 公司人才库配置与当前可读取数量。"""
    from .talent_db_adapter import SOURCE_TALENT_CONFIG, query_source_company_db
    enabled = SOURCE_TALENT_CONFIG.get("enabled", False)
    file_path = SOURCE_TALENT_CONFIG.get("file_path", "")
    mysql_enabled = bool(
        SOURCE_TALENT_CONFIG.get("mysql_host")
        and SOURCE_TALENT_CONFIG.get("mysql_database")
        and SOURCE_TALENT_CONFIG.get("mysql_user")
    )
    count = 0
    if enabled and file_path:
        try:
            from pathlib import Path
            import json
            data = json.loads(Path(file_path).expanduser().read_text(encoding="utf-8"))
            rows = data.get("candidates", data) if isinstance(data, dict) else data
            count = len(rows) if isinstance(rows, list) else 0
        except Exception as e:
            return {"ok": False, "enabled": enabled, "file_path": file_path, "mysql_enabled": mysql_enabled, "error": str(e)}
    mysql_sample_count = 0
    if enabled and mysql_enabled:
        mysql_sample_count = len(query_source_company_db({"skills": ["AI", "Python", "Redis"]}, limit=5))
    return {
        "ok": True,
        "enabled": enabled,
        "file_path": file_path,
        "candidate_count": count,
        "mysql_enabled": mysql_enabled,
        "mysql_host": SOURCE_TALENT_CONFIG.get("mysql_host", ""),
        "mysql_database": SOURCE_TALENT_CONFIG.get("mysql_database", ""),
        "mysql_sample_count": mysql_sample_count,
    }


@app.post("/admin/reload-source-talent", dependencies=[Depends(require_api_token)])
def admin_reload_source_talent():
    """Source 人才库文件由 adapter 每次读取，不需要重启。
    此接口用于验证文件格式并返回当前数量。"""
    return admin_source_talent_info()


@app.post("/admin/read-job/{jid}/retry", dependencies=[Depends(require_api_token)])
def admin_retry_read_job(jid: str):
    """人工解决读取问题后，把 read_job 重置为 pending 让调度器重试。"""
    job = db.get_read_job(jid)
    if not job:
        return {"ok": False, "error": "Read job not found"}
    db.update_read_job(jid, {"status": "pending", "error": "", "error_reason": ""})
    return {"ok": True, "read_job_id": jid, "status": "pending"}


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True, "service": "ttc-daemon", "version": "0.3.0"}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    import uvicorn
    uvicorn.run("ttc_daemon.main:app", host=DAEMON_HOST, port=DAEMON_PORT, reload=False)


if __name__ == "__main__":
    main()
