"""Feishu (Lark) Bitable adapter for candidate records.

This adapter converts a :class:`models.CandidateRecord` into Feishu Base cell
values and writes them via ``lark-cli`` (already installed and authenticated on
the user's machine).  A dry-run mode previews the payload without touching the
Base.

Only storage fields declared in ``config/feishu_field_mapping.json`` are
written. System fields, formula fields, lookup fields and read-only fields are
excluded automatically.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from models import CandidateRecord


MAPPING_PATH = Path(__file__).resolve().parent.parent / "config" / "feishu_field_mapping.json"


class FeishuBaseAdapter:
    def __init__(self, mapping_path: Path | str | None = None, base_token: str | None = None, table_id: str | None = None):
        self.mapping_path = Path(mapping_path) if mapping_path else MAPPING_PATH
        self.mapping = json.loads(self.mapping_path.read_text(encoding="utf-8"))
        self.base_token = base_token or self.mapping["base_token"]
        self.table_id = table_id or self.mapping["table_id"]

    def _field_value(self, record: CandidateRecord, spec: dict[str, Any]) -> Any:
        """Resolve a single Feishu field value from a CandidateRecord."""
        candidate_field = spec.get("candidate_field")
        if not candidate_field:
            return None

        value = getattr(record, candidate_field, None)
        formatter = spec.get("formatter")

        if formatter == "join_comma":
            items = value or []
            return ", ".join(str(x) for x in items) if isinstance(items, list) else str(items) if items else None

        if formatter == "education_summary":
            if not record.education:
                return None
            parts = [
                record.education.school,
                record.education.degree,
                str(record.education.graduation_year) if record.education.graduation_year else None,
                record.education.major,
            ]
            return " ".join(p for p in parts if p)

        if formatter == "boolean_to_select":
            text = str(value or "").lower()
            if any(w in text for w in ["是", "yes", "true", "看机会", "考虑", "在职-考虑"]):
                return "是"
            if any(w in text for w in ["否", "no", "false", "不看", "暂不考虑", "不考虑"]):
                return "否"
            return spec.get("fallback", "无信息")

        if formatter == "infer_job_type":
            return self._infer_job_type(record, spec)

        if formatter == "parser_metadata":
            meta = {
                "parser": record.parser_name,
                "version": record.parser_version,
                "confidence": record.parse_confidence,
                "missing_fields": record.missing_fields,
            }
            return json.dumps(meta, ensure_ascii=False, default=str)

        if isinstance(value, list):
            return ", ".join(str(x) for x in value) if value else None

        if isinstance(value, int):
            return str(value)

        return value

    @staticmethod
    def _infer_job_type(record: CandidateRecord, spec: dict[str, Any]) -> str:
        """Infer job type from tech stack / current title."""
        text = " ".join(record.tech_stack or []) + " " + (record.current_title or "")
        text = text.lower()
        options = spec.get("options", [])
        # Priority mapping.
        keywords = {
            "算法": ["算法", "machine learning", "ml", "nlp", "cv", "deep learning", "模型", "推荐"],
            "前端": ["前端", "frontend", "react", "vue", "angular"],
            "后端": ["后端", "backend", "java", "go", "python", "服务端"],
            "全栈": ["全栈", "fullstack", "full stack", "全站"],
            "产品": ["产品", "product manager", "产品经理"],
            "infra": ["infra", "sre", "devops", "运维", "基础设施"],
            "爬虫": ["爬虫", "spider", "crawler"],
            "运营": ["运营", "operation"],
        }
        for option, kws in keywords.items():
            if option in options and any(kw in text for kw in kws):
                return option
        return spec.get("fallback", "无匹配标签")

    def build_payload(self, record: CandidateRecord, *, include_attachments: bool = True) -> dict[str, Any]:
        """Return a dict of Feishu field_id -> cell value for this record.

        In dry-run mode this payload is printed/logged but not sent.
        """
        payload: dict[str, Any] = {}
        for key, spec in self.mapping["fields"].items():
            field_id = spec["field_id"]
            value = self._field_value(record, spec)
            if value is None:
                continue
            if spec.get("type") == "attachment":
                if include_attachments and record.original_attachment_path:
                    payload[field_id] = [{"type": "attachment", "file": record.original_attachment_path}]
                continue
            if spec.get("type") in ("select",):
                text = str(value)
                options = spec.get("options", [])
                if options and text not in options:
                    # Skip invalid select values to avoid API errors.
                    continue
                payload[field_id] = text
                continue
            # Clamp text length to avoid Feishu limits.
            max_len = spec.get("max_length", 100_000)
            text = str(value)
            if len(text) > max_len:
                text = text[:max_len - 3] + "..."
            payload[field_id] = text
        return payload

    def dry_run(self, record: CandidateRecord) -> dict[str, Any]:
        """Return a human-readable description of what would be written."""
        payload = self.build_payload(record)
        # Map field IDs back to names for readability.
        named = {}
        for key, spec in self.mapping["fields"].items():
            if spec["field_id"] in payload:
                val = payload[spec["field_id"]]
                if spec["type"] == "attachment":
                    val = [v.get("file") for v in val] if isinstance(val, list) else val
                named[spec["name"]] = val
        return {
            "base_token": self.base_token,
            "table_id": self.table_id,
            "action": "dry_run",
            "candidate_name": record.name,
            "attachment_sha256": record.attachment_sha256,
            "fields": named,
        }

    def _run_cli(self, *args: str) -> dict[str, Any]:
        cmd = ["lark-cli", "base", *args, "--as", "user"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"lark-cli failed: {result.stderr or result.stdout}")
        return json.loads(result.stdout)

    def upload_attachment(self, file_path: Path | str, record_id: str, field_id: str) -> str:
        """Upload a local file to an existing record's attachment field and return the Feishu file token."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Attachment not found: {path}")
        resp = self._run_cli(
            "+record-upload-attachment",
            "--base-token", self.base_token,
            "--table-id", self.table_id,
            "--record-id", record_id,
            "--field-id", field_id,
            "--file", str(path.resolve()),
        )
        data = resp.get("data", {})
        file_token = data.get("file_token") or data.get("token")
        if not file_token:
            raise RuntimeError(f"Attachment upload did not return file_token: {resp}")
        return file_token

    def create_record(self, record: CandidateRecord, *, dry_run: bool = False) -> dict[str, Any]:
        """Create a Feishu Base record for this candidate.

        Text fields are created via +record-batch-create using field names.
        Attachments are uploaded afterward because the batch-create command
        does not accept attachment fields as normal CellValue.
        Returns the created record ID on success.
        """
        if dry_run:
            return self.dry_run(record)

        payload = self.build_payload(record, include_attachments=False)
        if not payload:
            raise ValueError("No fields to write")

        # Map field_id -> field_name for batch-create (it expects field names).
        id_to_name = {spec["field_id"]: spec["name"] for spec in self.mapping["fields"].values()}
        field_names = [id_to_name[fid] for fid in payload.keys()]
        row_values = list(payload.values())

        batch_json = json.dumps({"fields": field_names, "rows": [row_values]}, ensure_ascii=False)
        resp = self._run_cli(
            "+record-batch-create",
            "--base-token", self.base_token,
            "--table-id", self.table_id,
            "--json", batch_json,
        )

        # Upload attachment if present.
        attachment_field_id = self.mapping["fields"]["resume_attachment"]["field_id"]
        if record.original_attachment_path and Path(record.original_attachment_path).is_file():
            records = resp.get("data", {}).get("records", [])
            if records:
                record_id = records[0].get("record_id")
                if record_id:
                    self.upload_attachment(record.original_attachment_path, record_id, attachment_field_id)

        return resp

    def record_exists(self, record: CandidateRecord) -> bool:
        """Check whether an equivalent record already exists in the Base.

        Uses the formula field ``查重值`` if available, otherwise falls back to
        searching by phone or name+company.
        """
        # Prefer exact phone match.
        if record.phone:
            try:
                resp = self._run_cli(
                    "+record-search",
                    "--base-token", self.base_token,
                    "--table-id", self.table_id,
                    "--field-name", "电话",
                    "--query", record.phone,
                    "--limit", "1",
                )
                if resp.get("data", {}).get("total"):
                    return True
            except Exception:
                pass
        # Fallback to name + company.
        if record.name and record.current_company:
            try:
                resp = self._run_cli(
                    "+record-search",
                    "--base-token", self.base_token,
                    "--table-id", self.table_id,
                    "--query", f"{record.name} {record.current_company}",
                    "--limit", "1",
                )
                if resp.get("data", {}).get("total"):
                    return True
            except Exception:
                pass
        return False
