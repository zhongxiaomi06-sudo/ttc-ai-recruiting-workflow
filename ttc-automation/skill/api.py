"""FastAPI router for the TTC Skill interface."""
from __future__ import annotations

from fastapi import APIRouter

from .intent import parse_intent
from .models import SearchRequest, SearchResult
from .scheduler import get_default_scheduler

router = APIRouter(prefix="/skill", tags=["skill"])


@router.post("/search", response_model=SearchResult)
async def skill_search(req: SearchRequest) -> SearchResult:
    """Accept a natural-language recruiting query and return candidates."""

    intent = parse_intent(req.query)
    intent.count = req.max_results
    if req.channels:
        intent.channels = req.channels

    scheduler = get_default_scheduler()
    candidates, raw = await scheduler.search(
        intent=intent,
        max_results=req.max_results,
        include_mock=req.include_mock,
    )

    sources = [k for k, v in raw.items() if v.get("count", 0) > 0]
    if not sources and req.include_mock:
        sources = ["mock"]

    return SearchResult(
        ok=True,
        query=req.query,
        intent=intent,
        sources=sources,
        candidates=candidates,
        total_found=len(candidates),
        review_url="",
        message="OK",
        raw_executor_results=raw,
    )


@router.get("/health")
async def skill_health():
    """Health check for the skill layer."""
    return {"ok": True, "skill": "available"}
