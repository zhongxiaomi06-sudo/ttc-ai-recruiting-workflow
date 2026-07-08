import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
    load_dotenv()
except Exception:
    pass

DAEMON_HOST = os.getenv("TTC_DAEMON_HOST", "127.0.0.1")
DAEMON_PORT = int(os.getenv("TTC_DAEMON_PORT", "8766"))
DATA_DIR = Path(os.getenv("TTC_DATA_DIR", str(Path(__file__).parent / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

CANDIDATE_COLLECTOR_URL = os.getenv("TTC_CC_URL", "http://127.0.0.1:8765")
API_TOKEN = os.getenv("TTC_API_TOKEN", "")

# 公司人才库配置，用户需按实际接口填写
TALENT_DB_CONFIG = {
    "enabled": os.getenv("TTC_TALENT_DB_ENABLED", "false").lower() == "true",
    "base_url": os.getenv("TTC_TALENT_DB_URL", ""),
    "api_key": os.getenv("TTC_TALENT_DB_KEY", ""),
    "query_path": os.getenv("TTC_TALENT_DB_QUERY_PATH", "/api/candidates/search"),
}

# Source 公司人才库配置：可以先接本地 JSON 导出，后续再换成 API。
SOURCE_TALENT_CONFIG = {
    "enabled": os.getenv("TTC_SOURCE_TALENT_ENABLED", "false").lower() == "true",
    "base_url": os.getenv("TTC_SOURCE_TALENT_URL", ""),
    "api_key": os.getenv("TTC_SOURCE_TALENT_KEY", ""),
    "query_path": os.getenv("TTC_SOURCE_TALENT_QUERY_PATH", "/api/candidates/search"),
    "file_path": os.getenv("TTC_SOURCE_TALENT_FILE", ""),
    "mysql_host": os.getenv("TTC_SOURCE_TALENT_MYSQL_HOST", os.getenv("TTC_MYSQL_HOST", "")),
    "mysql_port": int(os.getenv("TTC_SOURCE_TALENT_MYSQL_PORT", os.getenv("TTC_MYSQL_PORT", "3306"))),
    "mysql_database": os.getenv("TTC_SOURCE_TALENT_MYSQL_DATABASE", os.getenv("TTC_MYSQL_DATABASE", "")),
    "mysql_user": os.getenv("TTC_SOURCE_TALENT_MYSQL_USER", os.getenv("TTC_MYSQL_USER", "")),
    "mysql_password": os.getenv("TTC_SOURCE_TALENT_MYSQL_PASSWORD", os.getenv("TTC_MYSQL_PASSWORD", "")),
}

# 成熟读取工具配置：按需启用，未安装/未配置时自动回退到内置读取器。
WEB_READER_CONFIG = {
    "prefer": os.getenv("TTC_WEB_READER", "auto"),  # auto / firecrawl / crawl4ai / requests
    "firecrawl_api_key": os.getenv("TTC_FIRECRAWL_API_KEY", ""),
    "firecrawl_base_url": os.getenv("TTC_FIRECRAWL_BASE_URL", "https://api.firecrawl.dev"),
    "crawl4ai_enabled": os.getenv("TTC_CRAWL4AI_ENABLED", "false").lower() == "true",
}

FILE_READER_CONFIG = {
    "prefer": os.getenv("TTC_FILE_READER", "markitdown"),  # markitdown / tika / none
}

# 飞书 Bot 通知配置
FEISHU_BOT_CONFIG = {
    "webhook_url": os.getenv("TTC_FEISHU_BOT_WEBHOOK", ""),
    "chat_id": os.getenv("TTC_FEISHU_CHAT_ID", ""),
    "enabled": os.getenv("TTC_FEISHU_NOTIFY_ENABLED", "false").lower() == "true",
    "dashboard_url": os.getenv("TTC_DASHBOARD_URL", "http://127.0.0.1:8766"),
}

# LLM 配置（可选）
LLM_CONFIG = {
    "provider": os.getenv("TTC_LLM_PROVIDER", "openai"),  # openai / kimi / none
    "api_key": os.getenv("TTC_LLM_API_KEY", ""),
    "base_url": os.getenv("TTC_LLM_BASE_URL", ""),
    "model": os.getenv("TTC_LLM_MODEL", "gpt-4o-mini"),
}
