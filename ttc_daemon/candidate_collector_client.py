import logging
from typing import List, Dict, Any, Optional
import requests
from .config import CANDIDATE_COLLECTOR_URL

logger = logging.getLogger(__name__)


def fetch_export_jd(min_score: int = 50, timeout: int = 30) -> List[Dict[str, Any]]:
    url = f"{CANDIDATE_COLLECTOR_URL}/api/export-jd"
    try:
        session = requests.Session()
        session.trust_env = False
        resp = session.get(url, params={"min_score": min_score}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "candidates" in data:
            return data["candidates"]
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Failed to fetch candidate-collector export-jd: {e}")
        return []


def submit_resume(resume: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """若 candidate-collector 提供反向接收端点，可在此实现。"""
    logger.info("submit_resume not yet implemented")
    return None
