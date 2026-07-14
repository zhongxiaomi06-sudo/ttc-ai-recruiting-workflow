"""Browser capture direct-to-Feishu ingestion.

This module takes the payload produced by the browser extension (page text and
optional structured sections) and writes it directly to the configured Feishu
Base. It skips the SQLite ``candidates`` table because the extension already has
a review/approval path through ``/api/capture``; this path is for the
"import-on-click" workflow.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import closing
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from adapters.feishu_base import FeishuBaseAdapter
from ingestion.pipeline import init_ingestion_tables, local_duplicate_exists, record_fingerprint
from models import CandidateRecord
from parsers.unified_parser import parse_resume_text


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "candidates.db"


def _db_conn() -> Any:
    import sqlite3

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class StructuredSection(BaseModel):
    heading: str = ""
    text: str = ""


class BrowserCapturePayload(BaseModel):
    url: str = ""
    title: str = ""
    heading: str = ""
    text: str = Field(min_length=10, max_length=600_000)
    platform: str = ""
    source_type: str = "browser_capture"
    captured_at: str | None = None
    structured_data: dict[str, Any] | None = None
    dry_run: bool = False
    skip_duplicates: bool = True
    check_feishu_exists: bool = False


def _build_text_from_payload(payload: BrowserCapturePayload) -> str:
    """Combine structured sections or fall back to plain text."""
    structured = payload.structured_data or {}
    sections = structured.get("sections") if isinstance(structured.get("sections"), list) else None
    if sections:
        parts = []
        for section in sections:
            heading = (section.get("heading") or "").strip()
            body = (section.get("text") or "").strip()
            if heading:
                parts.append(heading)
            if body:
                parts.append(body)
        combined = "\n".join(parts)
        if len(combined) >= 10:
            return combined
    return payload.text


def build_candidate_from_capture(payload: BrowserCapturePayload) -> CandidateRecord:
    """Convert a browser capture payload into a canonical CandidateRecord."""
    text = _build_text_from_payload(payload)
    source_type = payload.source_type or "browser_capture"
    source_platform = payload.platform or payload.source_type or "browser_capture"
    record = parse_resume_text(
        text,
        title=payload.title,
        source_url=payload.url,
        source_type=source_type,
    )
    # Override platform-specific metadata that parse_resume_text does not know.
    record.source_url = payload.url or record.source_url
    record.source_platform = source_platform
    record.source_type = source_type
    record.captured_at = payload.captured_at
    # Preserve the original raw text even if sections were provided.
    record.raw_text = text
    # Compute a stable fingerprint that covers the extension payload.
    fingerprint_input = f"{payload.url or ''}|{text[:4000]}"
    record.extra["browser_capture_fingerprint"] = hashlib.sha256(
        fingerprint_input.encode("utf-8")
    ).hexdigest()
    return record


def import_browser_capture(
    payload: BrowserCapturePayload,
    *,
    feishu_adapter: FeishuBaseAdapter | None = None,
) -> dict[str, Any]:
    """Import a browser capture directly into Feishu Base.

    Returns a dict with ``ok``, ``action``, ``candidate``, ``fingerprint`` and
    optionally ``feishu_record_id`` or ``error``.
    """
    init_ingestion_tables()
    record = build_candidate_from_capture(payload)
    fingerprint = record_fingerprint(record)

    duplicate = local_duplicate_exists(record)
    if duplicate and payload.skip_duplicates:
        return {
            "ok": True,
            "action": "skipped_duplicate",
            "candidate": record.model_dump(),
            "fingerprint": fingerprint,
            "duplicate": dict(duplicate),
        }

    adapter = feishu_adapter or FeishuBaseAdapter()

    if payload.check_feishu_exists and adapter.record_exists(record):
        return {
            "ok": True,
            "action": "skipped_duplicate_feishu",
            "candidate": record.model_dump(),
            "fingerprint": fingerprint,
        }

    if payload.dry_run:
        dry_payload = adapter.dry_run(record)
        dry_run_payload = {
            "candidate": record.model_dump(),
            "feishu_payload": dry_payload,
        }
        with closing(_db_conn()) as conn:
            conn.execute(
                """
                INSERT INTO ingestion_log (
                    fingerprint, attachment_sha256, phone, name, current_company,
                    current_title, feishu_write_status, review_status, dry_run_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(fingerprint) DO UPDATE SET
                    phone=excluded.phone,
                    name=excluded.name,
                    current_company=excluded.current_company,
                    current_title=excluded.current_title,
                    dry_run_payload=excluded.dry_run_payload,
                    updated_at=datetime('now')
                """,
                (
                    fingerprint,
                    record.attachment_sha256,
                    record.phone,
                    record.name,
                    record.current_company,
                    record.current_title,
                    "dry_run",
                    "pending",
                    json.dumps(dry_run_payload, ensure_ascii=False),
                ),
            )
            conn.commit()
        return {
            "ok": True,
            "action": "dry_run",
            "candidate": record.model_dump(),
            "fingerprint": fingerprint,
            "feishu_payload": dry_payload,
        }

    try:
        resp = adapter.create_record(record)
        feishu_record_id = _extract_record_id(resp)
        if not feishu_record_id:
            raise RuntimeError(f"Feishu create_record did not return a record_id: {resp}")
        dry_run_payload = {
            "candidate": record.model_dump(),
            "feishu_payload": adapter.dry_run(record),
        }
        with closing(_db_conn()) as conn:
            conn.execute(
                """
                INSERT INTO ingestion_log (
                    fingerprint, attachment_sha256, phone, name, current_company,
                    current_title, feishu_record_id, feishu_write_status, review_status, dry_run_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(fingerprint) DO UPDATE SET
                    phone=excluded.phone,
                    name=excluded.name,
                    current_company=excluded.current_company,
                    current_title=excluded.current_title,
                    feishu_record_id=excluded.feishu_record_id,
                    feishu_write_status=excluded.feishu_write_status,
                    review_status=excluded.review_status,
                    dry_run_payload=excluded.dry_run_payload,
                    updated_at=datetime('now')
                """,
                (
                    fingerprint,
                    record.attachment_sha256,
                    record.phone,
                    record.name,
                    record.current_company,
                    record.current_title,
                    feishu_record_id,
                    "success",
                    "pending",
                    json.dumps(dry_run_payload, ensure_ascii=False),
                ),
            )
            conn.commit()
        return {
            "ok": True,
            "action": "created",
            "candidate": record.model_dump(),
            "fingerprint": fingerprint,
            "feishu_record_id": feishu_record_id,
        }
    except Exception as exc:
        dry_run_payload = {"candidate": record.model_dump(), "error": str(exc)}
        with closing(_db_conn()) as conn:
            conn.execute(
                """
                INSERT INTO ingestion_log (
                    fingerprint, attachment_sha256, phone, name, current_company,
                    current_title, feishu_write_status, review_status, error_message, dry_run_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(fingerprint) DO UPDATE SET
                    phone=excluded.phone,
                    name=excluded.name,
                    current_company=excluded.current_company,
                    current_title=excluded.current_title,
                    feishu_write_status=excluded.feishu_write_status,
                    review_status=excluded.review_status,
                    error_message=excluded.error_message,
                    dry_run_payload=excluded.dry_run_payload,
                    updated_at=datetime('now')
                """,
                (
                    fingerprint,
                    record.attachment_sha256,
                    record.phone,
                    record.name,
                    record.current_company,
                    record.current_title,
                    "failed",
                    "pending",
                    str(exc),
                    json.dumps(dry_run_payload, ensure_ascii=False),
                ),
            )
            conn.commit()
        return {
            "ok": False,
            "action": "failed",
            "candidate": record.model_dump(),
            "fingerprint": fingerprint,
            "error": str(exc),
        }


def _extract_record_id(resp: dict[str, Any]) -> str | None:
    """Best-effort extraction of Feishu record ID from lark-cli response."""
    data = resp.get("data", {})
    if isinstance(data, dict):
        records = data.get("records")
        if isinstance(records, list) and records:
            return records[0].get("record_id")
        record_id_list = data.get("record_id_list")
        if isinstance(record_id_list, list) and record_id_list:
            return record_id_list[0]
        return data.get("record_id")
    if isinstance(data, list) and data:
        return data[0].get("record_id")
    return None
