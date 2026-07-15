"""Convert local SQLite rows / CandidateRecord to cloud_candidates schema."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def _parse_timestamp(value: str | None) -> datetime | None:
    """Best-effort parse ISO timestamp to timezone-aware datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def sqlite_row_to_cloud(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    """Convert a local candidates SQLite row into the cloud_candidates schema."""
    # sqlite3.Row 没有 .get()，先统一转成 dict（调用方可能传 Row 或 dict）。
    if isinstance(row, sqlite3.Row):
        row = dict(row)
    collected_at = _parse_timestamp(row.get("collected_at"))

    # Preserve every local column in parsed_json so nothing is lost.
    parsed_json = {
        "id": row.get("id"),
        "explicit_age": row.get("explicit_age"),
        "experience_years": row.get("experience_years"),
        "undergraduate_tier": row.get("undergraduate_tier"),
        "employment_status": row.get("employment_status"),
        "summary": row.get("summary"),
        "hard_filter_reason": row.get("hard_filter_reason"),
        "consulting_evidence": row.get("consulting_evidence"),
        "inhouse_evidence": row.get("inhouse_evidence"),
        "product_evidence": row.get("product_evidence"),
        "brand_evidence": row.get("brand_evidence"),
        "channel_evidence": row.get("channel_evidence"),
        "client_evidence": row.get("client_evidence"),
        "score": row.get("score"),
        "jd_score": row.get("jd_score"),
        "jd_recommendation": row.get("jd_recommendation"),
        "jd_scores_json": row.get("jd_scores_json"),
        "recommendation": row.get("recommendation"),
        "strengths_json": row.get("strengths_json"),
        "risks_json": row.get("risks_json"),
    }

    return {
        "fingerprint": row.get("fingerprint") or str(row.get("id")),
        "name": row.get("name") or "",
        "platform": row.get("platform") or "",
        "source_url": row.get("source_url") or "",
        "source_type": row.get("source_type") or "",
        "title": row.get("title") or "",
        "location": row.get("location") or "",
        "current_company": row.get("current_company") or "",
        "current_role": row.get("current_role") or "",
        "phone": row.get("phone") or "",
        "email": row.get("email") or "",
        "undergraduate_school": row.get("undergraduate_school") or "",
        "expected_salary": row.get("expected_salary") or "",
        "experiences_json": row.get("experiences_json") or "[]",
        "education_json": row.get("education_json") or "{}",
        "keywords_json": row.get("keywords_json") or "[]",
        "raw_text": row.get("raw_text") or "",
        "review_status": "pending",
        "attachment_path": row.get("attachment_path"),
        "attachment_sha256": row.get("attachment_sha256"),
        "collected_at": collected_at,
        "parsed_json": json.dumps(parsed_json, ensure_ascii=False, default=str),
    }


def candidate_record_to_cloud(record: Any) -> dict[str, Any]:
    """Convert a CandidateRecord (models.py) to a cloud_candidates row."""
    data = record.model_dump() if hasattr(record, "model_dump") else dict(record)
    return {
        "fingerprint": data.get("attachment_sha256") or data.get("fingerprint") or "",
        "name": data.get("name") or "",
        "platform": data.get("source_platform") or data.get("platform") or "",
        "source_url": data.get("source_url") or "",
        "source_type": data.get("source_type") or "",
        "title": data.get("current_title") or data.get("title") or "",
        "location": data.get("current_location") or data.get("location") or "",
        "current_company": data.get("current_company") or "",
        "current_role": data.get("current_title") or "",
        "phone": data.get("phone") or "",
        "email": data.get("email") or "",
        "undergraduate_school": data.get("undergraduate_school") or data.get("school") or "",
        "expected_salary": data.get("expected_salary") or "",
        "experiences_json": json.dumps(data.get("work_experiences", []), ensure_ascii=False, default=str),
        "education_json": json.dumps(data.get("education", {}), ensure_ascii=False, default=str),
        "keywords_json": json.dumps(data.get("skills", []) or data.get("keywords", []), ensure_ascii=False, default=str),
        "raw_text": data.get("raw_text") or "",
        "review_status": data.get("review_status", "pending"),
        "attachment_path": data.get("original_attachment_path") or data.get("attachment_path"),
        "attachment_sha256": data.get("attachment_sha256"),
        "collected_at": data.get("captured_at") or data.get("collected_at"),
        "parsed_json": json.dumps(data, ensure_ascii=False, default=str),
    }
