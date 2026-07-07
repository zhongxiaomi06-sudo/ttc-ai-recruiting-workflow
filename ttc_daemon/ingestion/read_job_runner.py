"""Read Job Runner：执行读取任务，把来源变成 raw_ingest_records。"""
import logging
import json
from typing import Dict, Any

from .. import db
from ..link_reader import read_url, read_file

logger = logging.getLogger(__name__)


def _json_field(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def run_read_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """执行一个 read_job，返回生成的 raw_ingest_record。"""
    jid = job["id"]
    db.update_read_job(jid, {"status": "running"})
    logger.info("Running read job %s (%s)", jid, job.get("source_url") or job.get("source_type"))

    source_type = job.get("source_type", "unknown")
    source_url = job.get("source_url", "")
    provided_raw = job.get("raw_text", "")
    title = job.get("title", "")
    job_capture_meta = _json_field(job.get("capture_meta"), {}) or {}
    job_payload = _json_field(job.get("payload"), {}) or {}
    file_path = job_payload.get("file_path", "")

    try:
        if provided_raw:
            # 已由外部（油猴脚本、PDF 解析等）提供内容
            record = {
                "source_type": source_type,
                "source_url": source_url,
                "title": title,
                "raw_text": provided_raw,
                "markdown": job.get("markdown", provided_raw),
                "dom_text": provided_raw,
                "script_payload": {},
                "read_status": "succeeded" if provided_raw.strip() else "empty",
                "content_type_guess": job.get("content_type_guess", ""),
                "error_reason": "" if provided_raw.strip() else "empty_content",
                "read_method": "provided",
                "method": "provided",
                "error": "" if provided_raw.strip() else "内容为空",
                "capture_meta": job_capture_meta,
            }
        elif file_path:
            record = read_file(file_path)
            record["source_type"] = source_type
            record["capture_meta"] = job_capture_meta
        elif source_url and not source_url.startswith(("http://", "https://")):
            record = read_file(source_url)
            record["source_type"] = source_type
            record["capture_meta"] = job_capture_meta
        elif source_url:
            record = read_url(source_url)
            record["source_type"] = source_type
            record_capture_meta = _json_field(record.get("capture_meta"), {}) or {}
            record["capture_meta"] = {**record_capture_meta, **job_capture_meta}
        else:
            raise ValueError("read_job 缺少 source_url 和 raw_text，无法读取")

        record["read_job_id"] = jid
        rid = db.insert_ingest(record)
        record["id"] = rid
        db.save_raw_file(record)
        read_status = record.get("read_status") or ("succeeded" if record.get("raw_text", "").strip() else "empty")
        job_status = "succeeded" if read_status == "succeeded" else "failed"
        db.update_read_job(
            jid,
            {
                "status": job_status,
                "method": record.get("read_method") or record.get("method", ""),
                "raw_text": record.get("raw_text", ""),
                "markdown": record.get("markdown", ""),
                "read_status": read_status,
                "content_type_guess": record.get("content_type_guess", ""),
                "error_reason": record.get("error_reason", ""),
                "error": record.get("error", ""),
                "capture_meta": record.get("capture_meta", {}),
                "completed_at": db.now_iso(),
            },
        )
        logger.info("Read job %s succeeded, ingest record %s", jid, rid)
        return record

    except Exception as e:
        logger.exception("Read job %s failed: %s", jid, e)
        db.update_read_job(
            jid,
            {
                "status": "failed",
                "read_status": "failed",
                "error_reason": "runtime_error",
                "error": str(e),
                "completed_at": db.now_iso(),
            },
        )
        raise
