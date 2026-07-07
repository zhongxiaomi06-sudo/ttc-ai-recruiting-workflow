"""候选人信息补全核心。"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def enrich_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """全网信息补全：复用 GitHub API、公开网页读取。"""
    try:
        from ..agents.web_enrichment_agent import enrich as web_enrich
        return web_enrich(candidate)
    except Exception as e:
        logger.warning("Web enrichment failed: %s", e)
        enriched = dict(candidate)
        enriched.setdefault("enriched_profile", {})
        return enriched
