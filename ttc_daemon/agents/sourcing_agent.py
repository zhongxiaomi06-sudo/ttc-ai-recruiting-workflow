"""人才搜索 Agent：从公司人才库、candidate-collector 和公网召回候选人。"""
import json
import logging
from typing import Dict, Any, List

from .. import db
from ..candidate_collector_client import fetch_export_jd
from ..pipeline import enrich_candidate
from ..talent_db_adapter import query_talent_db, query_source_company_db

logger = logging.getLogger(__name__)


def search(mission: Dict[str, Any], jd_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    """执行人才召回，入库并返回候选人列表。"""
    all_candidates: List[Dict[str, Any]] = []

    # 公司人才库
    try:
        for c in query_talent_db(jd_fields):
            c.setdefault("source_types", []).append("talent_db")
            all_candidates.append(c)
    except Exception as e:
        logger.warning("Talent DB query failed: %s", e)

    # Source 公司人才库：API 或本地 JSON 导出，作为独立召回源。
    try:
        for c in query_source_company_db(jd_fields):
            c.setdefault("source_types", []).append("source_company_db")
            all_candidates.append(c)
    except Exception as e:
        logger.warning("Source company DB query failed: %s", e)

    # candidate-collector
    try:
        for c in fetch_export_jd(min_score=50):
            c.setdefault("source_types", []).append("candidate_collector")
            all_candidates.append(c)
    except Exception as e:
        logger.warning("Candidate-collector fetch failed: %s", e)

    # 去重：按 email + phone 简单去重
    seen = set()
    deduped = []
    for c in all_candidates:
        key = (
            c.get("email", "").lower(),
            c.get("phone", ""),
            c.get("name", ""),
            c.get("source_url", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    # 全网补全占位
    enriched = [enrich_candidate(c) for c in deduped]

    # 持久化并收集 candidate_ids
    candidate_ids = []
    for c in enriched:
        cid = db.insert_candidate(c)
        c["id"] = cid
        candidate_ids.append(cid)

    logger.info("Mission %s sourced %s candidates", mission["id"], len(candidate_ids))
    db.insert_agent_run(
        mission_id=mission["id"],
        agent_name="sourcing_agent.search",
        input_data=jd_fields,
        output_data={"candidate_count": len(candidate_ids), "candidate_ids": candidate_ids},
        decision="sourcing_done",
    )
    return enriched
