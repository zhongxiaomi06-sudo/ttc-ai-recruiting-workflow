"""Unified configuration — reads from .env / environment variables"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # LLM
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")

    # Feishu
    FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")

    # Storage
    DB_PATH: str = os.getenv("DB_PATH", os.environ.get("DEPLOY_PATH", "/opt/talentmatch") + "/data/sqlite/recruit.db")
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", os.environ.get("DEPLOY_PATH", "/opt/talentmatch") + "/data/chroma")
    CHROMA_HOST: str = os.getenv("CHROMA_HOST", "")
    CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", "0"))

    # Paths
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", os.environ.get("DEPLOY_PATH", "/opt/talentmatch") + "/data/uploads")
    DATA_DIR: str = os.getenv("DATA_DIR", os.environ.get("DEPLOY_PATH", "/opt/talentmatch") + "/data")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8878"))

    # Matching
    MATCH_RULES_DIR: str = os.getenv("MATCH_RULES_DIR", "")


settings = Settings()
