"""FastAPI router for agent pipeline endpoints — mounts under /api/agents/
All new endpoints, no modifications to existing v5 routes."""
from __future__ import annotations
import json
import os
import uuid
import time
from typing import Optional
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from loguru import logger

from .pipeline import RecruitingPipeline, PipelineResult
from bot.feishu_client import FeishuClient
from .jd_agent import JDParserAgent
from .resume_agent import ResumeScreenerAgent
from .match_agent import MatchScorerAgent
from .outreach_agent import OutreachDrafterAgent
from .interview_agent import InterviewGeneratorAgent
from .bias_agent import BiasMitigatorAgent

# ── Router ──────────────────────────────────────

router = APIRouter(prefix="/api/agents", tags=["Agent Pipeline"])

# Store references set by main.py
_storage = None


def init_router(storage):
    """Initialize router with shared storage instance from main.py"""
    global _storage
    _storage = storage


def get_storage():
    if _storage is None:
        raise HTTPException(503, "Storage not initialized")
    return _storage


# In-memory pipeline tracking
_pipelines: dict = {}


# ── Health / Status ──────────────────────────────────────

@router.get("/status")
async def agent_status():
    """Get agent pipeline system status and statistics"""
    from .base import BaseAgent
    s = get_storage()
    stats = s.get_stats() if s else {}
    return {
        "status": "ok",
        "agents_available": [
            "JDParserAgent", "ResumeScreenerAgent", "MatchScorerAgent",
            "OutreachDrafterAgent", "InterviewGeneratorAgent", "BiasMitigatorAgent",
        ],
        "pipeline_available": True,
        "storage_stats": stats,
        "active_pipelines": len(_pipelines),
    }


# ── JD Parser ──────────────────────────────────────

@router.post("/parse-jd")
async def parse_jd(
    jd_text: str = Form(..., description="岗位描述文本"),
    source: str = Form("api", description="来源标识"),
):
    """Parse unstructured JD text into structured format"""
    agent = JDParserAgent()
    requirements, cost = agent.parse(jd_text, source)

    return {
        "status": "ok",
        "data": requirements.model_dump(),
        "cost": round(cost, 6),
    }


# ── Resume Screener ──────────────────────────────────────

@router.post("/screen-resume")
async def screen_resume(
    file: UploadFile = File(...),
):
    """Screen a resume file and extract structured candidate profile"""
    upload_dir = os.environ.get("UPLOAD_DIR", "/opt/recruit-bot/data/uploads")
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, f"agent_{uuid.uuid4().hex[:8]}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Extract text
    from resume_parser.parser import extract_text
    raw_text = extract_text(file_path)
    if not raw_text:
        raise HTTPException(400, "无法从文件中提取文本内容")

    agent = ResumeScreenerAgent()
    profile, cost = agent.screen(raw_text, file.filename)

    return {
        "status": "ok",
        "source_file": file.filename,
        "data": profile.model_dump(),
        "cost": round(cost, 6),
    }


@router.post("/screen-resume-text")
async def screen_resume_text(
    text: str = Form(..., description="简历文本内容"),
    filename: str = Form("resume.txt", description="文件名"),
):
    """Screen a resume from text (not file upload)"""
    agent = ResumeScreenerAgent()
    profile, cost = agent.screen(text, filename)

    return {
        "status": "ok",
        "data": profile.model_dump(),
        "cost": round(cost, 6),
    }


# ── Match Scoring ──────────────────────────────────────

@router.post("/match")
async def match_candidate(
    jd_text: str = Form(..., description="岗位描述"),
    resume_text: str = Form(..., description="简历文本"),
    use_llm: bool = Form(True, description="是否使用LLM深度分析"),
):
    """Score a single candidate against a job"""
    # Parse both
    jd_agent = JDParserAgent()
    resume_agent = ResumeScreenerAgent()
    match_agent = MatchScorerAgent(use_llm_analysis=use_llm)

    job, cost1 = jd_agent.parse(jd_text)
    profile, cost2 = resume_agent.screen(resume_text)
    score, cost3 = match_agent.score(profile, job)

    return {
        "status": "ok",
        "job": job.model_dump(),
        "candidate": profile.model_dump(),
        "match": score.model_dump(),
        "costs": {
            "parse_jd": round(cost1, 6),
            "screen_resume": round(cost2, 6),
            "match": round(cost3, 6),
            "total": round(cost1 + cost2 + cost3, 6),
        },
    }


# ── Pipeline ──────────────────────────────────────

@router.post("/pipeline")
async def run_pipeline(
    jd_text: str = Form(..., description="岗位描述文本"),
    batch_files: Optional[str] = Form(None, description="批量文件路径(逗号分隔)"),
    min_score: float = Form(70.0, description="最低匹配分阈值"),
    top_k: int = Form(10, description="返回top-K候选人"),
    outreach_tone: str = Form("professional", description="外联语气"),
    sender_name: str = Form("", description="猎头名字"),
    company_name: str = Form("", description="公司名称"),
    use_llm_match: bool = Form(True, description="是否使用LLM深度匹配"),
    save_to_db: bool = Form(True, description="是否保存结果到数据库"),
    background: bool = Form(False, description="是否后台运行"),
):
    """Run the full RecruitingPipeline end-to-end"""
    pipeline = RecruitingPipeline(
        min_score=min_score,
        top_k=top_k,
        outreach_tone=outreach_tone,
        sender_name=sender_name,
        company_name=company_name,
        use_llm_match=use_llm_match,
    )

    # Load resume texts from provided paths
    resume_texts = []
    if batch_files:
        from resume_parser.parser import extract_text
        for fpath in batch_files.split(","):
            fpath = fpath.strip()
            if os.path.exists(fpath):
                text = extract_text(fpath)
                if text:
                    resume_texts.append((os.path.basename(fpath), text))
                    logger.info(f"Loaded resume: {fpath} ({len(text)} chars)")

    if background:
        pipeline_id = pipeline.run_async(jd_text, resume_texts=resume_texts)
        _pipelines[pipeline_id] = {"status": "running", "created_at": time.time()}
        return {
            "status": "accepted",
            "pipeline_id": pipeline_id,
            "message": "管道已在后台运行，使用 GET /api/agents/pipeline/{id} 查询状态",
        }

    result = pipeline.run(jd_text, resume_texts=resume_texts)

    if save_to_db and _storage and result.job:
        s = get_storage()
        pipeline.save_results(result, s)

    return {
        "status": result.status,
        "pipeline_id": result.pipeline_id,
        "data": result.to_dict(),
    }


@router.get("/pipeline/{pipeline_id}")
async def get_pipeline_status(pipeline_id: str):
    """Get pipeline run status (for async runs)"""
    p = _pipelines.get(pipeline_id)
    if not p:
        raise HTTPException(404, f"Pipeline {pipeline_id} not found")
    return {
        "pipeline_id": pipeline_id,
        "status": p.get("status", "unknown"),
        "created_at": p.get("created_at", 0),
    }


# ── Outreach ──────────────────────────────────────

@router.post("/outreach")
async def draft_outreach(
    candidate_name: str = Form(...),
    candidate_role: str = Form(""),
    candidate_company: str = Form(""),
    strengths: str = Form(""),
    matched_skills: str = Form(""),
    job_title: str = Form(...),
    job_company: str = Form(""),
    selling_points: str = Form(""),
    tone: str = Form("professional"),
    sender_name: str = Form(""),
):
    """Draft a personalized outreach message"""
    from .match_agent import AgentMatchScore

    match = AgentMatchScore(
        candidate_name=candidate_name,
        candidate_role=candidate_role,
        candidate_company=candidate_company,
        strengths=strengths.split(",") if strengths else [],
        matched_skills=matched_skills.split(",") if matched_skills else [],
    )
    job = AgentJobRequirements(
        title=job_title,
        company=job_company,
        key_selling_points=selling_points.split(",") if selling_points else [],
    )

    agent = OutreachDrafterAgent()
    draft, cost = agent.draft(match, job, tone=tone, sender_name=sender_name, company_name=job_company)

    return {
        "status": "ok",
        "data": draft.model_dump(),
        "cost": round(cost, 6),
    }


# ── Interview Plan ──────────────────────────────────────

@router.post("/interview-plan")
async def generate_interview_plan(
    candidate_json: str = Form(..., description="候选人信息的JSON"),
    job_json: str = Form(..., description="岗位信息的JSON"),
    match_json: Optional[str] = Form(None, description="匹配分数的JSON(可选)"),
):
    """Generate a personalized interview plan for a candidate"""
    from .resume_agent import AgentCandidateProfile
    from .jd_agent import AgentJobRequirements

    try:
        candidate = AgentCandidateProfile(**json.loads(candidate_json))
        job = AgentJobRequirements(**json.loads(job_json))
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"JSON解析失败: {e}")

    match_score = None
    if match_json:
        try:
            from .match_agent import AgentMatchScore
            match_score = AgentMatchScore(**json.loads(match_json))
        except Exception:
            pass

    agent = InterviewGeneratorAgent()
    plan, cost = agent.generate_plan(candidate, job, match_score)

    return {
        "status": "ok",
        "data": plan.model_dump(),
        "cost": round(cost, 6),
    }


# ── Bias Audit ──────────────────────────────────────

@router.post("/bias-audit")
async def audit_bias(
    candidate_json: str = Form(..., description="候选人信息JSON"),
    match_json: str = Form(..., description="匹配分数JSON"),
):
    """Audit a match for potential bias"""
    try:
        from .resume_agent import AgentCandidateProfile
        from .match_agent import AgentMatchScore
        candidate = AgentCandidateProfile(**json.loads(candidate_json))
        match = AgentMatchScore(**json.loads(match_json))
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"JSON解析失败: {e}")

    agent = BiasMitigatorAgent()
    audit, cost = agent.audit_match(candidate, match)

    return {
        "status": "ok",
        "data": audit.model_dump(),
        "cost": round(cost, 6),
    }


# ── Full Pipeline with File Upload ──────────────────────────────────────

@router.post("/pipeline-upload")
async def run_pipeline_with_files(
    jd_text: str = Form(..., description="岗位描述文本"),
    files: list[UploadFile] = File(..., description="简历文件(支持多文件)"),
    min_score: float = Form(70.0, description="最低匹配分"),
    top_k: int = Form(10, description="返回top-K"),
    save_to_db: bool = Form(True, description="保存到数据库"),
):
    """Run pipeline with uploaded resume files (most convenient for Feishu integration)"""
    upload_dir = os.environ.get("UPLOAD_DIR", "/opt/recruit-bot/data/uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Save and extract uploaded files
    from resume_parser.parser import extract_text
    resume_texts = []
    for file in files:
        fpath = os.path.join(upload_dir, f"pipe_{uuid.uuid4().hex[:8]}_{file.filename}")
        with open(fpath, "wb") as f:
            f.write(await file.read())
        text = extract_text(fpath)
        if text:
            resume_texts.append((file.filename, text))
            logger.info(f"Loaded: {file.filename} ({len(text)} chars)")

    if not resume_texts:
        raise HTTPException(400, "未能从上传的文件中提取有效文本")

    pipeline = RecruitingPipeline(min_score=min_score, top_k=top_k)
    result = pipeline.run(jd_text, resume_texts=resume_texts)

    if save_to_db and _storage and result.job:
        s = get_storage()
        pipeline.save_results(result, s)

    return {
        "status": result.status,
        "pipeline_id": result.pipeline_id,
        "data": result.to_dict(),
    }


# ── Pipeline Stats ──────────────────────────────────────

@router.get("/stats")
async def agent_stats():
    """Get agent usage statistics"""
    stats = {
        "active_pipelines": len(_pipelines),
        "agents": {
            "JDParserAgent": {"description": "JD解析Agent", "model_count": 1},
            "ResumeScreenerAgent": {"description": "简历筛选Agent", "model_count": 1},
            "MatchScorerAgent": {"description": "匹配评分Agent", "model_count": 1},
            "OutreachDrafterAgent": {"description": "外联起草Agent", "model_count": 1},
            "InterviewGeneratorAgent": {"description": "面试题生成Agent", "model_count": 1},
            "BiasMitigatorAgent": {"description": "偏见审计Agent", "model_count": 1},
        },
    }
    if _storage:
        stats["storage"] = _storage.get_stats()
    return stats


# ── Interactive Endpoints (v6) ──────────────────────────────────────

@router.post("/notify-feishu")
async def notify_feishu(
    chat_id: str = Form(..., description="飞书会话ID"),
    card_type: str = Form(..., description="卡片类型: agent_result/interview/outreach/bias/job/candidate/dashboard/error"),
    data_json: str = Form(..., description="卡片数据的JSON"),
):
    """Send a rich card to Feishu chat"""
    try:
        data = json.loads(data_json)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"JSON解析失败: {e}")

    client = FeishuClient()
    card_builders = {
        "agent_result": FeishuClient.build_agent_result_card,
        "interview": FeishuClient.build_interview_card,
        "outreach": FeishuClient.build_outreach_card,
        "bias": FeishuClient.build_bias_audit_card,
        "job": FeishuClient.build_job_card,
        "candidate": FeishuClient.build_candidate_card,
        "dashboard": FeishuClient.build_dashboard_card,
        "error": FeishuClient.build_error_card,
    }

    builder = card_builders.get(card_type)
    if not builder:
        raise HTTPException(400, f"不支持的卡片类型: {card_type}")

    card = builder(data)
    client.send_card(chat_id, card)
    return {"status": "ok", "card_type": card_type}


@router.post("/pipeline-with-files-and-notify")
async def pipeline_with_notify(
    jd_text: str = Form(..., description="岗位描述文本"),
    files: list[UploadFile] = File(..., description="简历文件(支持多文件)"),
    chat_id: str = Form("", description="飞书会话ID(用于通知)"),
    min_score: float = Form(70.0),
    top_k: int = Form(10),
):
    """Run pipeline and notify via Feishu card"""
    upload_dir = os.environ.get("UPLOAD_DIR", "/opt/recruit-bot/data/uploads")
    os.makedirs(upload_dir, exist_ok=True)

    from resume_parser.parser import extract_text
    resume_texts = []
    for file in files:
        fpath = os.path.join(upload_dir, f"pipe_{uuid.uuid4().hex[:8]}_{file.filename}")
        with open(fpath, "wb") as f:
            f.write(await file.read())
        text = extract_text(fpath)
        if text:
            resume_texts.append((file.filename, text))

    if not resume_texts:
        raise HTTPException(400, "未能从上传的文件中提取有效文本")

    pipeline = RecruitingPipeline(min_score=min_score, top_k=top_k)
    result = pipeline.run(jd_text, resume_texts=resume_texts)

    # Save to storage
    if _storage and result.job:
        pipeline.save_results(result, _storage)
        # Also save interview plans
        if result.interview_plans:
            s = get_storage()
            for plan in result.interview_plans:
                s.save_interview_plan({
                    "candidate_id": plan.candidate_name,
                    "job_id": result.job.title if result.job else "",
                    "plan": plan.model_dump(),
                    "questions": [q.model_dump() for q in plan.questions],
                    "status": "completed",
                })

    # Notify via Feishu if chat_id provided
    if chat_id:
        client = FeishuClient()
        # Send agent result card
        result_card = FeishuClient.build_agent_result_card({
            "data": result.to_dict()
        })
        client.send_card(chat_id, result_card)

        # Send interview cards
        for plan in result.interview_plans[:1]:
            card = FeishuClient.build_interview_card(plan.model_dump())
            client.send_card(chat_id, card)

        # Send outreach cards
        for draft in result.outreach_drafts[:2]:
            card = FeishuClient.build_outreach_card(draft.model_dump())
            client.send_card(chat_id, card)

    return {
        "status": result.status,
        "pipeline_id": result.pipeline_id,
        "data": result.to_dict(),
        "notified": bool(chat_id),
    }


# ── Search & Retrieve (v6) ──────────────────────────────────────

@router.get("/search")
async def search_all(
    query: str = "",
    limit: int = 10,
):
    """Unified search across candidates, jobs, and matches"""
    s = get_storage()
    if not query:
        # Return recent items
        return {
            "candidates": s.list_candidates(limit=limit),
            "jobs": s.list_jobs("active", limit=limit),
            "recent_matches": s.get_recent_matches(days=7, limit=limit),
        }
    result = s.search_all(query, limit)
    return result


@router.get("/dashboard")
async def dashboard():
    """Get system dashboard data with stats"""
    s = get_storage()
    stats = s.get_stats()
    recent = s.get_recent_matches(days=7, limit=10)
    return {
        "stats": stats,
        "recent_matches": recent,
        "candidates_count": stats.get("candidates", 0),
        "jobs_count": stats.get("active_jobs", 0),
    }


@router.get("/candidates")
async def list_candidates(
    limit: int = 50,
    offset: int = 0,
    owner: str = "",
):
    """List candidates with optional owner filter"""
    s = get_storage()
    if owner:
        return {"candidates": s.get_candidates_by_owner(owner, limit)}
    return {"candidates": s.list_candidates(limit, offset)}


@router.get("/jobs")
async def list_jobs(
    status: str = "active",
    limit: int = 50,
    owner: str = "",
):
    """List jobs with optional filters"""
    s = get_storage()
    if owner:
        return {"jobs": s.get_jobs_by_owner(owner, limit)}
    return {"jobs": s.list_jobs(status, limit)}


@router.delete("/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str):
    """Delete a candidate and associated data"""
    s = get_storage()
    ok = s.delete_candidate(candidate_id)
    if not ok:
        raise HTTPException(404, "Candidate not found")
    return {"status": "ok", "deleted": candidate_id}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and associated data"""
    s = get_storage()
    ok = s.delete_job(job_id)
    if not ok:
        raise HTTPException(404, "Job not found")
    return {"status": "ok", "deleted": job_id}


@router.patch("/candidates/{candidate_id}")
async def patch_candidate(candidate_id: str, request: Request):
    """Update candidate fields"""
    data = await request.json()
    s = get_storage()
    ok = s.update_candidate(candidate_id, data)
    if not ok:
        raise HTTPException(400, "No valid fields to update")
    return {"status": "ok", "updated": candidate_id}


@router.patch("/jobs/{job_id}")
async def patch_job(job_id: str, request: Request):
    """Update job fields"""
    data = await request.json()
    s = get_storage()
    ok = s.update_job(job_id, data)
    if not ok:
        raise HTTPException(400, "No valid fields to update")
    return {"status": "ok", "updated": job_id}


@router.get("/interviews")
async def list_interviews(candidate_id: str = "", limit: int = 20):
    """List interview plans"""
    s = get_storage()
    return {"interviews": s.list_interview_plans(candidate_id, limit)}


@router.get("/candidates/duplicates")
async def find_duplicates(email: str = "", name: str = ""):
    """Find potential duplicate candidates"""
    if not email and not name:
        raise HTTPException(400, "Provide email or name")
    s = get_storage()
    return {"duplicates": s.get_duplicate_candidates(email, name)}
# ── Health / Status ──────────────────────────────────────


async def agent_status():
    """Get agent pipeline system status and statistics"""
    from .base import BaseAgent
    s = get_storage()
    stats = s.get_stats() if s else {}
    return {
        "status": "ok",
        "agents_available": [
            "JDParserAgent", "ResumeScreenerAgent", "MatchScorerAgent",
            "OutreachDrafterAgent", "InterviewGeneratorAgent", "BiasMitigatorAgent",
        ],
        "pipeline_available": True,
        "storage_stats": stats,
        "active_pipelines": len(_pipelines),
    }