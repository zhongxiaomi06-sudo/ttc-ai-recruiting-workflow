"""Job API routes"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request, Query
from storage import get_storage

router = APIRouter(tags=["jobs"])


@router.get("/jobs")
async def list_jobs(
    status: str = "active",
    limit: int = Query(default=50, le=200),
    q: str = "",
):
    storage = get_storage()
    if q.strip():
        return storage.search_jobs(q.strip(), limit)
    return storage.list_jobs(status, limit)


@router.get("/jobs/stats")
async def get_job_stats():
    storage = get_storage()
    conn = storage._get_conn()
    stats = {
        "total": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        "active": conn.execute("SELECT COUNT(*) FROM jobs WHERE status=\"active\"").fetchone()[0],
        "closed": conn.execute("SELECT COUNT(*) FROM jobs WHERE status=\"closed\"").fetchone()[0],
    }
    conn.close()
    return stats


@router.post("/jobs")
async def create_job(request: Request):
    data = await request.json()
    jid = get_storage().save_job(data)
    return {"id": jid, "status": "ok"}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    j = get_storage().get_job(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


@router.get("/jobs/{job_id}/matches")
async def get_job_matches(job_id: str, limit: int = 20):
    return get_storage().get_job_matches(job_id, limit)
