import json
import logging
from typing import Dict, Any, List, Optional

from . import db
from .candidate_collector_client import fetch_export_jd
from .core.enrichment import enrich_candidate
from .core.jd_parser import extract_jd
from .core.scoring import score_candidate, generate_talking_points
from .talent_db_adapter import query_talent_db

logger = logging.getLogger(__name__)


def run_pipeline(jd_record_id: Optional[str] = None) -> Dict[str, Any]:
    """主链路：JD → 人才库 + candidate-collector → 补全 → 评分 → 电话清单。"""
    jd_records = db.get_latest_jd(limit=5)
    if not jd_records:
        return {"ok": False, "error": "No JD record found"}

    jd_record = None
    if jd_record_id:
        jd_record = next((r for r in jd_records if r["id"] == jd_record_id), None)
    jd_record = jd_record or jd_records[0]

    jd_fields = extract_jd(jd_record["raw_text"])
    logger.info("Extracted JD fields: %s", jd_fields)

    all_candidates: List[Dict[str, Any]] = []

    talent_db_candidates = query_talent_db(jd_fields)
    for c in talent_db_candidates:
        c.setdefault("source_types", []).append("talent_db")
        all_candidates.append(c)

    cc_candidates = fetch_export_jd(min_score=50)
    for c in cc_candidates:
        c.setdefault("source_types", []).append("candidate_collector")
        all_candidates.append(c)

    if not all_candidates:
        return {"ok": True, "jd_record_id": jd_record["id"], "candidates_count": 0, "call_list_count": 0}

    call_list = []
    for cand in all_candidates:
        cand = enrich_candidate(cand)
        cand = score_candidate(cand, jd_fields)
        cid = db.insert_candidate(cand)

        if cand.get("overall_score", 0) >= 40:
            item = {
                "candidate_id": cid,
                "jd_record_id": jd_record["id"],
                "priority": int(cand["overall_score"]),
                "talking_points": generate_talking_points(cand, jd_fields),
                "evidence": cand.get("evidence", []),
                "status": "pending",
            }
            lid = db.insert_call_list(item)
            item["id"] = lid
            call_list.append(item)

    call_list.sort(key=lambda x: x["priority"], reverse=True)

    return {
        "ok": True,
        "jd_record_id": jd_record["id"],
        "jd_fields": jd_fields,
        "candidates_count": len(all_candidates),
        "call_list_count": len(call_list),
        "call_list": call_list,
    }
