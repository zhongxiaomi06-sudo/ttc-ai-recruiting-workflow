"""Aggregate all API routers — unified /api prefix"""
from fastapi import APIRouter

from .health import router as health_router
from .candidates import router as candidates_router
from .jobs import router as jobs_router
from .match import router as match_router
from .stats import router as stats_router
from .auth import router as auth_router
from .auth_feishu import router as auth_feishu_router
from .feedback import router as feedback_router
from .analytics import router as analytics_router
from .tracking import router as tracking_router
from .messages import router as messages_router

api_router = APIRouter()

# /health
api_router.include_router(health_router)

# /api/*
api_router.include_router(candidates_router, prefix="/api")       # /api/candidates, /api/candidates/*, /api/candidates/search/*
api_router.include_router(jobs_router, prefix="/api")              # /api/jobs, /api/jobs/*
api_router.include_router(match_router, prefix="/api")             # /api/fast-match, /api/compare, /api/history, /api/explain/*
api_router.include_router(stats_router, prefix="/api")             # /api/stats, /api/tracking/stats
api_router.include_router(auth_router, prefix="/api")              # /api/auth/*
api_router.include_router(auth_feishu_router, prefix="/api")       # /api/auth/feishu/*
api_router.include_router(feedback_router, prefix="/api")          # /api/feedback, /api/feedback/*
api_router.include_router(analytics_router, prefix="/api")         # /api/analytics/*
api_router.include_router(tracking_router, prefix="/api")          # /api/tracking/event, /api/tracking/batch, /api/tracking/stats
api_router.include_router(messages_router, prefix="/api")          # /api/messages, /api/messages/*
