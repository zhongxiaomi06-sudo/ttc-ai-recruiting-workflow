"""Health check routes"""
from __future__ import annotations
from fastapi import APIRouter
from storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    stats = get_storage().get_stats()
    return {"status": "ok", "app": "recruit-bot", "version": "6.0.0", "stats": stats}
