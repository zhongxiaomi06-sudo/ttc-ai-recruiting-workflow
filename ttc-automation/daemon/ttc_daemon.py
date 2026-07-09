"""TTC Local Daemon: FastAPI app + Orchestrator integration.

Run:
    python ttc_daemon.py

Default: http://127.0.0.1:8766
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Make embedded talentmatch modules and the new skill package importable.
# The daemon directory must stay at sys.path[0] so local modules shadow talentmatch modules.
_DAEMON_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _DAEMON_DIR.parent
_TALENTMATCH_DIR = _PROJECT_DIR / "talentmatch"

for _dir in (_TALENTMATCH_DIR, _PROJECT_DIR, _DAEMON_DIR):
    _s = str(_dir)
    if _s in sys.path:
        sys.path.remove(_s)
    sys.path.insert(0, _s)

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

# Load .env from project root (ttc-automation/.env)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

import db
from agents import record_agent_run
from html_render import render_dashboard, render_human_task, render_mission
from link_reader import read_link
from orchestrator import advance_mission, ingest_and_route, start_orchestrator
from source_talent import status as source_talent_status

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="TTC Daemon", version="0.2.0")

# Mount TTC Skill interface (AI tool plugin / scheduling middleware)
try:
    import skill
    app.include_router(skill.router)
except Exception as exc:
    print(f"[WARN] Failed to load skill router: {exc}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_TOKEN = os.getenv("TTC_API_TOKEN")
PUBLIC_PATHS = {"/dashboard", "/status", "/records", "/api/call-list", "/skill/health"}
PUBLIC_PREFIXES = ("/mission/", "/human/task/")


@app.middleware("http")
async def api_token_check(request: Request, call_next):
    if API_TOKEN and request.method != "OPTIONS":
        path = request.url.path
        if not (
            path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES)
        ):
            if request.headers.get("X-TTC-Token") != API_TOKEN:
                return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    return await call_next(request)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
def startup():
    db.init_db()
    start_orchestrator()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class FeishuIngest(BaseModel):
    source_type: str = "feishu_web"
    source_url: Optional[str] = None
    title: Optional[str] = None
    content: Any
    markdown: Optional[str] = None
    selected: bool = False
    captured_at: Optional[str] = None


class LinkIngest(BaseModel):
    source_type: str
    source_url: str
    title: Optional[str] = None
    content: Any
    markdown: Optional[str] = None
    captured_at: Optional[str] = None
    access_basis: Optional[str] = "public"


class ResumeIngest(BaseModel):
    candidate_name: str
    source_url: Optional[str] = None
    resume_text: str
    file_path: Optional[str] = None
    captured_at: Optional[str] = None


class PipelineRun(BaseModel):
    record_id: Optional[str] = None
    jd_text: Optional[str] = None
    min_score: int = Field(default=50, ge=0, le=100)


# ---------------------------------------------------------------------------
# Ingest endpoints
# ---------------------------------------------------------------------------
@app.post("/ingest/feishu")
async def ingest_feishu(payload: FeishuIngest):
    data = payload.dict()
    data["markdown"] = data.get("markdown") or (data.get("content") if isinstance(data.get("content"), str) else None)
    result = await ingest_and_route(data)
    return {"ok": True, **result}


@app.post("/ingest/link")
async def ingest_link(payload: LinkIngest):
    data = payload.dict()
    data["markdown"] = data.get("markdown") or (data.get("content") if isinstance(data.get("content"), str) else None)
    result = await ingest_and_route(data)
    return {"ok": True, **result}


@app.post("/ingest/resume")
async def ingest_resume(payload: ResumeIngest):
    data = {
        "source_type": "resume",
        "source_url": payload.source_url,
        "title": f"Resume: {payload.candidate_name}",
        "content": payload.resume_text,
        "markdown": payload.resume_text,
        "captured_at": payload.captured_at,
        "access_basis": "user_authorized",
    }
    result = await ingest_and_route(data)
    return {"ok": True, **result}


@app.post("/link/read")
async def read_link_endpoint(url: str, use_playwright: bool = False):
    result = await read_link(url, use_playwright=use_playwright)
    result["source_url"] = url
    route_result = await ingest_and_route(result)
    return {"ok": True, "link_result": result, "route": route_result}


@app.get("/ingest/read-link")
async def ingest_read_link(url: str, use_playwright: bool = False):
    """GET alias for /link/read, used by browser extension and testing console."""
    return await read_link_endpoint(url, use_playwright=use_playwright)


@app.get("/admin/source-talent")
def admin_source_talent():
    return {"ok": True, "source_talent": source_talent_status()}


# ---------------------------------------------------------------------------
# Dashboard / Mission / Human Task HTML pages
# ---------------------------------------------------------------------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    missions = db.list_missions(limit=100)
    tasks = db.list_human_tasks(limit=100)
    return HTMLResponse(render_dashboard(missions, tasks))


@app.get("/mission/{mission_id}", response_class=HTMLResponse)
def mission_page(mission_id: str):
    mission = db.get_mission(mission_id)
    if not mission:
        return HTMLResponse("Mission not found", status_code=404)
    artifact = db.get_artifact(mission["artifact_id"]) or {}
    tasks = db.list_human_tasks(mission_id=mission_id)
    runs = db.list_agent_runs(mission_id=mission_id)
    return HTMLResponse(render_mission(mission, artifact, tasks, runs))


@app.get("/human/task/{task_id}", response_class=HTMLResponse)
def human_task_page(task_id: str):
    task = db.get_human_task(task_id)
    if not task:
        return HTMLResponse("Task not found", status_code=404)
    mission = db.get_mission(task["mission_id"]) or {}
    return HTMLResponse(render_human_task(task, mission))


@app.post("/human/task/{task_id}/complete")
async def complete_human_task(task_id: str, request: Request):
    body = await request.body()
    try:
        data = json.loads(body)
    except Exception:
        data = dict(await request.form())
    return await _process_task_completion(task_id, data)


async def _process_task_completion(task_id: str, result: dict):
    task = db.get_human_task(task_id)
    if not task:
        return JSONResponse({"ok": False, "error": "Task not found"}, status_code=404)

    db.update_human_task(task_id, {
        "status": "completed",
        "result_json": json.dumps(result, ensure_ascii=False),
        "completed_at": db.now_iso(),
    })

    mission = db.get_mission(task["mission_id"])
    if not mission:
        return JSONResponse({"ok": True, "message": "Task completed, mission gone"})

    if task["task_type"] == "problem_solve":
        resolution = result.get("resolution")
        if resolution == "fixed":
            resume_state = mission.get("resume_state") or "created"
            db.update_mission(mission["id"], {"status": resume_state, "problem_reason": None})
            await advance_mission(mission["id"])
        elif resolution == "skip":
            next_states = {
                "created": "jd_parsed",
                "jd_parsed": "sourcing",
                "sourcing": "scored",
                "scored": "calling",
            }
            db.update_mission(mission["id"], {"status": next_states.get(mission["status"], "closed")})
            await advance_mission(mission["id"])
        else:
            db.update_mission(mission["id"], {"status": "closed"})
    elif task["task_type"] == "client_review":
        decision = result.get("decision")
        if decision == "proceed":
            db.update_mission(mission["id"], {"status": "calling"})
            await advance_mission(mission["id"])
        elif decision == "need_more":
            db.update_mission(mission["id"], {"status": "problem_pending", "problem_reason": "need_more_info"})
        else:
            db.update_mission(mission["id"], {"status": "closed"})

    return JSONResponse({"ok": True, "message": "Task completed", "task_id": task_id})


@app.post("/human/task/{task_id}/submit")
async def submit_human_task(task_id: str, request: Request):
    form = await request.form()
    response = await _process_task_completion(task_id, dict(form))
    if isinstance(response, JSONResponse):
        return response
    return HTMLResponse(
        f"""<!DOCTYPE html>
        <html><head><title>已提交</title></head>
        <body style="background:#0a0a0f;color:#c8c8d4;font-family:sans-serif;padding:40px;">
        <h2>反馈已提交</h2>
        <p><a href="/dashboard" style="color:#00cec9;">返回 Dashboard</a></p>
        </body></html>"""
    )


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
@app.get("/status")
def status():
    return {
        "ok": True,
        "data_dir": str(db.DATA_DIR),
        "counts": {
            "missions": db._conn().execute("SELECT COUNT(*) FROM missions").fetchone()[0],
            "human_tasks": db._conn().execute("SELECT COUNT(*) FROM human_tasks").fetchone()[0],
            "artifacts": db._conn().execute("SELECT COUNT(*) FROM artifacts").fetchone()[0],
            "read_jobs": db._conn().execute("SELECT COUNT(*) FROM read_jobs").fetchone()[0],
        },
    }


@app.get("/records")
def list_records(
    source_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    # Backward-compatible alias: return artifacts
    arts = db.list_artifacts(artifact_type=source_type, limit=limit)
    return {"ok": True, "records": arts, "offset": offset}


@app.post("/pipeline/run")
def run_pipeline(req: PipelineRun):
    return {
        "ok": True,
        "message": "pipeline stub: use /ingest/feishu or /ingest/link to create a Mission",
        "record_id": req.record_id,
        "jd_snippet": (req.jd_text or "")[:200],
    }


@app.get("/api/call-list")
def call_list(limit: int = 20):
    missions = db.list_missions(status="human_pending", limit=limit)
    calls = []
    for m in missions:
        call_list_data = json.loads(m["call_list_json"]) if m.get("call_list_json") else []
        for item in call_list_data:
            calls.append({
                "mission_id": m["id"],
                "candidate": item.get("candidate", {}),
                "overall_score": item.get("overall_score"),
                "script": item.get("script"),
            })
    return {"ok": True, "calls": calls[:limit]}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("ttc_daemon:app", host="127.0.0.1", port=8766, reload=False)
