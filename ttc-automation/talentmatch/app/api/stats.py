"""Stats API routes"""
from __future__ import annotations
from fastapi import APIRouter
from storage import get_storage

router = APIRouter(tags=["stats"])


@router.get("/stats")
async def api_stats():
    return get_storage().get_stats()


@router.get("/tracking/stats")
async def tracking_stats():
    """真实追踪统计"""
    storage = get_storage()
    conn = storage._get_conn()
    total = conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0]
    dwell = conn.execute("SELECT COALESCE(AVG(duration_seconds),0) FROM tracking WHERE event_type='view'").fetchone()[0]
    rows = conn.execute("SELECT event_type, COUNT(*) as cnt FROM tracking GROUP BY event_type ORDER BY cnt DESC").fetchall()
    conn.close()
    return {
        "total": total,
        "dwell_avg_seconds": round(dwell, 1),
        "breakdown": {r["event_type"]: r["cnt"] for r in rows},
    }
