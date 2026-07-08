"""TalentMatch backend application"""
from __future__ import annotations
import os
from typing import Optional, Dict, Any
from loguru import logger
from fastapi import FastAPI
from contextlib import asynccontextmanager

from .config import settings
from .api.router import api_router
from .feishu.webhook import router as feishu_router

# Global pipeline references — set during lifespan
_pipelines: Dict[str, Any] = {}


def get_pipelines() -> dict:
    return _pipelines


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # ── Startup ──
        logger.info("TalentMatch backend v6 starting...")

        # Initialize storage
        from storage import init_storage
        db_path = os.environ.get("DB_PATH", settings.DB_PATH)
        storage = init_storage(db_path=db_path)

        # Initialize Feishu client
        from bot.feishu_client import FeishuClient
        feishu = FeishuClient()

        # Initialize pipelines
        from pipelines.resume_pipeline import ResumePipeline
        from pipelines.match_pipeline import MatchPipeline

        resume_pipeline = ResumePipeline(storage=storage, feishu=feishu)
        match_pipeline = MatchPipeline(storage=storage, feishu=feishu)

        # Store global references
        _pipelines["storage"] = storage
        _pipelines["feishu"] = feishu
        _pipelines["resume_pipeline"] = resume_pipeline
        _pipelines["match_pipeline"] = match_pipeline

        # Initialize agents router
        try:
            from agents.router import init_router as init_agent_router
            init_agent_router(storage)
            logger.info("Agent router initialized ✅")
        except Exception as e:
            logger.warning(f"Agent router init skipped: {e}")

        # Initialize task queue
        from pipelines.task_queue import TaskQueue
        task_queue = TaskQueue()
        _pipelines["task_queue"] = task_queue

        # Initialize tracking aggregator (implicit feedback → candidates scores)
        try:
            aggregator.start()
            _pipelines["tracking_aggregator"] = aggregator
        except Exception as e:

        logger.info("TalentMatch v6 ready ✅")

        yield

        # ── Shutdown ──
        logger.info("TalentMatch shutting down...")

    import os

    app = FastAPI(
        title="TalentMatch · 猎头人岗匹配系统",
        version="6.0.0",
        lifespan=lifespan,
    )

    # Mount routers
    app.include_router(api_router)
    app.include_router(feishu_router)

    # Legacy: agents router
    try:
        from agents.router import router as agent_router
        app.include_router(agent_router)
    except ImportError:
        pass

    return app
