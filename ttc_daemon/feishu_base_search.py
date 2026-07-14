"""Feishu Bitable talent search adapter for ttc_daemon.

This module is intentionally self-contained and does **not** import from
``candidate-collector`` (the package name contains a hyphen).  It calls
``lark-cli base +record-search`` directly to query the Feishu talent base and
returns normalized candidate dicts that ``ttc_daemon.db.insert_candidate`` can
consume.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import FEISHU_BASE_CONFIG

logger = logging.getLogger(__name__)

# Field IDs we need to materialize a candidate from a Feishu record.
# These are stable IDs from the talent-base field mapping.
_FETCH_FIELD_IDS = [
    "fld3Wby9yq",   # 人才ID (auto_number, unique id)
    "fldzfT0qEZ",   # 姓名
    "fldPTfVrz3",   # 手机号
    "fldFpqo9p2",   # 邮箱
    "fld0P0N3Gs",   # 当前公司
    "fldNjJRmeJ",   # 当前岗位
    "fldPr5IxCT",   # 所在城市
    "fldjnybrkB",   # 求职意向
    "fldJKBL8eq",   # 期望地点
    "fld1AhIFXh",   # 技能标签
    "flddx2gXj9",   # 岗位方向
    "fld5G6LUN8",   # 工作年限
    "fldZp9r4I7",   # 学校
    "fldQkdlg9I",   # 学历
    "fldLRLMSjg",   # 专业
    "fldp2DjUDX",   # 原人才库链接
]

# Field name -> field id for search fields.
_SEARCH_FIELDS = {
    "当前岗位": "fldNjJRmeJ",
    "求职意向": "fldjnybrkB",
    "技能标签": "fld1AhIFXh",
    "岗位方向": "flddx2gXj9",
    "当前公司": "fld0P0N3Gs",
    "所在城市": "fldPr5IxCT",
    "期望地点": "fldJKBL8eq",
}

# Priority order for building queries from jd_fields.
_QUERY_PRIORITY: List[Tuple[str, str]] = [
    ("当前岗位", "position"),
    ("求职意向", "position"),
    ("技能标签", "skills.0"),
    ("技能标签", "skills.1"),
    ("技能标签", "skills.2"),
    ("岗位方向", "skills.0"),
    ("岗位方向", "skills.1"),
    ("当前公司", "target_companies.0"),
    ("所在城市", "location"),
    ("期望地点", "location"),
]


def _clamp_keyword(keyword: str, max_len: int) -> str:
    """Clamp keyword to Feishu's limit and strip whitespace."""
    keyword = keyword.strip()
    if len(keyword) > max_len:
        keyword = keyword[:max_len]
    return keyword


def _get_jd_value(jd_fields: Dict[str, Any], path: str) -> Optional[str]:
    """Resolve a dotted path like ``skills.0`` or ``location`` from jd_fields."""
    if "." in path:
        key, idx = path.split(".", 1)
        try:
            idx = int(idx)
        except ValueError:
            return None
        value = jd_fields.get(key)
        if isinstance(value, (list, tuple)) and 0 <= idx < len(value):
            value = value[idx]
        else:
            return None
    else:
        value = jd_fields.get(path)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class FeishuBaseSearcher:
    """Search a Feishu Bitable talent base using ``lark-cli``."""

    def __init__(
        self,
        base_token: str,
        table_id: str,
        view_id: Optional[str] = None,
        mapping_path: Optional[Path] = None,
        max_queries: int = 10,
        search_limit: int = 20,
        rate_limit_qps: float = 2.0,
        keyword_max_len: int = 50,
    ) -> None:
        self.base_token = base_token
        self.table_id = table_id
        self.view_id = view_id
        self.mapping_path = Path(mapping_path) if mapping_path else None
        self.max_queries = max(1, max_queries)
        self.search_limit = max(1, search_limit)
        self.min_interval = 1.0 / max(rate_limit_qps, 0.1)
        self.keyword_max_len = keyword_max_len
        self._last_request_time = 0.0
        self._field_id_to_name: Optional[Dict[str, str]] = None
        if self.mapping_path and self.mapping_path.exists():
            self.mapping = json.loads(self.mapping_path.read_text(encoding="utf-8"))
        else:
            self.mapping = {}

    @classmethod
    def from_config(cls) -> "FeishuBaseSearcher":
        cfg = FEISHU_BASE_CONFIG
        return cls(
            base_token=cfg["base_token"],
            table_id=cfg["table_id"],
            view_id=cfg.get("view_id") or None,
            mapping_path=Path(cfg["mapping_path"]) if cfg.get("mapping_path") else None,
            max_queries=cfg.get("max_queries", 10),
            search_limit=cfg.get("search_limit", 20),
            rate_limit_qps=cfg.get("rate_limit_qps", 2.0),
            keyword_max_len=cfg.get("keyword_max_len", 50),
        )

    def _enforce_rate_limit(self) -> None:
        """Sleep if necessary to respect the configured QPS."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.monotonic()

    def _run_cli(self, *args: str, _attempt: int = 1) -> Dict[str, Any]:
        """Run ``lark-cli base ...`` and parse JSON output."""
        self._enforce_rate_limit()
        cmd = ["lark-cli", "base", *args, "--as", "user", "--format", "json"]
        logger.debug("Running lark-cli: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"lark-cli failed: {result.stderr or result.stdout}")

        stdout = result.stdout.strip()
        # Some lark-cli commands wrap JSON in markdown fences.
        if stdout.startswith("```"):
            lines = stdout.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            stdout = "\n".join(lines)

        if not stdout:
            return {}

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("Could not parse lark-cli output as JSON: %r", stdout[:500])
            return {"raw_stdout": stdout}

        # Retry on Feishu rate limit or transient network errors.
        err = data.get("error", {}) if isinstance(data, dict) else {}
        is_rate_limit = isinstance(err, dict) and err.get("code") == 800004135
        is_network = isinstance(err, dict) and err.get("type") == "network"
        if (is_rate_limit or is_network) and _attempt < 4:
            wait = 2 ** _attempt
            logger.warning("Feishu rate limit/network error, retrying in %ss", wait)
            time.sleep(wait)
            return self._run_cli(*args, _attempt=_attempt + 1)

        return data

    def _field_name(self, field_id: str) -> str:
        """Return the Chinese field name for a field ID."""
        if self._field_id_to_name is None:
            self._field_id_to_name = {}
            all_fields = self.mapping.get("fields", {})
            for spec in all_fields.values():
                fid = spec.get("field_id")
                name = spec.get("name")
                if fid and name:
                    self._field_id_to_name[fid] = name
            readonly = self.mapping.get("readonly_fields", {})
            for spec in readonly.values():
                fid = spec.get("field_id")
                name = spec.get("name")
                if fid and name:
                    self._field_id_to_name[fid] = name
        return self._field_id_to_name.get(field_id, field_id)

    def _record_to_dict(self, record_array: List[Any], field_id_list: List[str]) -> Dict[str, Any]:
        """Map a Feishu record array to a dict keyed by Chinese field name."""
        result: Dict[str, Any] = {}
        for idx, field_id in enumerate(field_id_list):
            if idx >= len(record_array):
                break
            name = self._field_name(field_id)
            result[name] = record_array[idx]
        return result

    def search_field(
        self,
        field_name: str,
        keyword: str,
        limit: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Search one Feishu field by keyword.

        Returns a tuple of (records as dicts, field_id_list used for ordering).
        """
        limit = limit or self.search_limit
        keyword = _clamp_keyword(keyword, self.keyword_max_len)
        if not keyword:
            return [], []

        args = [
            "+record-search",
            "--base-token", self.base_token,
            "--table-id", self.table_id,
            "--keyword", keyword,
            "--search-field", field_name,
            "--limit", str(limit),
        ]
        # Form views do not support record_query; search without a view so the
        # Base uses its default searchable view.
        for fid in _FETCH_FIELD_IDS:
            args.extend(["--field-id", fid])

        resp = self._run_cli(*args)
        data = resp.get("data", {}) or {} if isinstance(resp, dict) else {}
        rows = data.get("data", [])
        field_id_list = data.get("field_id_list", [])
        if not isinstance(rows, list):
            return [], field_id_list

        records = []
        for row in rows:
            if isinstance(row, list):
                records.append(self._record_to_dict(row, field_id_list))
        return records, field_id_list

    def _build_queries(self, jd_fields: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Build a prioritized list of (field_name, keyword) queries."""
        queries: List[Tuple[str, str]] = []
        seen: set = set()

        def add(field_name: str, keyword: Optional[str]) -> None:
            if not keyword:
                return
            keyword = _clamp_keyword(keyword, self.keyword_max_len)
            if not keyword:
                return
            key = (field_name, keyword)
            if key in seen:
                return
            seen.add(key)
            queries.append(key)

        for field_name, path in _QUERY_PRIORITY:
            if len(queries) >= self.max_queries:
                break
            value = _get_jd_value(jd_fields, path)
            if value:
                add(field_name, value)

        return queries[: self.max_queries]

    @staticmethod
    def _extract_text(value: Any) -> str:
        """Extract a plain string from a Feishu text/select/multi_select cell."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            parts = [str(v) for v in value if v is not None]
            return ", ".join(parts)
        return str(value)

    @staticmethod
    def _extract_list(value: Any) -> List[str]:
        """Extract a list of strings from a Feishu multi_select/array cell."""
        if value is None:
            return []
        if isinstance(value, str):
            return [v.strip() for v in value.replace("，", ",").split(",") if v.strip()]
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value if v is not None and str(v).strip()]
        return [str(value)]

    def _compute_match_score(
        self,
        fields: Dict[str, Any],
        match_info: Dict[str, Any],
    ) -> float:
        """Compute a 0-100 jd_alignment_score from matched fields/keywords."""
        score = 0.0
        matched_fields = set(match_info.get("matched_fields", []))
        matched_keywords = set(match_info.get("matched_keywords", []))

        # Position match is the strongest signal.
        if {"当前岗位", "求职意向"} & matched_fields:
            score += 40.0

        # Skill matches: +15 per unique skill keyword, capped at 60.
        skill_matches = [k for k in matched_keywords if self._is_skill_keyword(k)]
        score += min(len(set(k.lower() for k in skill_matches)) * 15.0, 60.0)

        # Company background match.
        if "当前公司" in matched_fields:
            score += 10.0

        # Location match.
        if {"所在城市", "期望地点"} & matched_fields:
            score += 5.0

        return min(score, 100.0)

    @staticmethod
    def _is_skill_keyword(keyword: str) -> bool:
        """Heuristic: a skill keyword usually comes from the skills list."""
        # Skills are typically short technical terms.
        return len(keyword) <= 30 and not re.search(r"[市县区]$", keyword)

    def _map_record(
        self,
        fields: Dict[str, Any],
        match_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Convert a Feishu record dict into a ttc_daemon candidate dict."""
        skills = self._extract_list(fields.get("技能标签") or fields.get("岗位方向"))
        experience = fields.get("工作年限")
        try:
            experience_years = float(experience) if experience is not None else None
        except (TypeError, ValueError):
            experience_years = None

        education = self._extract_text(fields.get("学历"))
        school = self._extract_text(fields.get("学校"))
        major = self._extract_text(fields.get("专业"))

        # Prefer the original talent link if stored; otherwise link to the base view.
        source_url = self._extract_text(fields.get("原人才库链接"))
        if not source_url:
            source_url = (
                f"https://jxog8b3tny.feishu.cn/base/{self.base_token}"
                f"?table={self.table_id}"
                + (f"&view={self.view_id}" if self.view_id else "")
            )

        talent_id = self._extract_text(fields.get("人才ID"))
        name = self._extract_text(fields.get("姓名"))
        phone = self._extract_text(fields.get("手机号"))
        email = self._extract_text(fields.get("邮箱"))

        return {
            "name": name,
            "phone": phone,
            "email": email,
            "current_title": self._extract_text(fields.get("当前岗位")),
            "current_company": self._extract_text(fields.get("当前公司")),
            "current_location": self._extract_text(fields.get("所在城市")),
            "expected_title": self._extract_text(fields.get("求职意向")),
            "expected_location": self._extract_text(fields.get("期望地点")),
            "skills": skills,
            "experience_years": experience_years,
            "education": education,
            "school": school,
            "major": major,
            "source_url": source_url,
            "source_types": [],
            "raw_profile": {
                "feishu_talent_id": talent_id,
                "feishu_fields": fields,
                "match_info": match_info,
            },
            "enriched_profile": {},
            "jd_alignment_score": self._compute_match_score(fields, match_info),
            "gold_score": 0.0,
            "risk_flags": [],
            "overall_score": 0.0,
        }

    def search_by_jd(self, jd_fields: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
        """Search the Feishu base using JD criteria and return candidate dicts."""
        queries = self._build_queries(jd_fields)
        if not queries:
            logger.info("No Feishu Base queries generated for jd_fields: %s", jd_fields)
            return []

        # Record id -> merged dict and match info.
        merged: Dict[str, Dict[str, Any]] = {}
        match_infos: Dict[str, Dict[str, Any]] = {}

        for field_name, keyword in queries:
            logger.info("Searching Feishu Base field=%s keyword=%s", field_name, keyword)
            try:
                records, _ = self.search_field(field_name, keyword)
            except Exception as e:
                logger.warning("Feishu Base search failed for %s=%s: %s", field_name, keyword, e)
                continue

            for rec in records:
                talent_id = self._extract_text(rec.get("人才ID"))
                if not talent_id:
                    continue
                key = talent_id
                if key not in merged:
                    merged[key] = rec
                    match_infos[key] = {"matched_fields": [], "matched_keywords": []}
                if field_name not in match_infos[key]["matched_fields"]:
                    match_infos[key]["matched_fields"].append(field_name)
                if keyword not in match_infos[key]["matched_keywords"]:
                    match_infos[key]["matched_keywords"].append(keyword)

        candidates = []
        for key, fields in merged.items():
            candidate = self._map_record(fields, match_infos[key])
            candidates.append(candidate)

        # Sort by match score descending and clamp to limit.
        candidates.sort(key=lambda c: c.get("jd_alignment_score", 0.0), reverse=True)
        return candidates[:limit]


def query_feishu_base(jd_fields: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
    """Convenience wrapper used by ``sourcing_agent.search``.

    Returns an empty list when Feishu Base search is disabled or misconfigured.
    """
    if not FEISHU_BASE_CONFIG.get("enabled"):
        return []
    if not FEISHU_BASE_CONFIG.get("base_token") or not FEISHU_BASE_CONFIG.get("table_id"):
        logger.warning("Feishu Base search is enabled but token/table_id is missing")
        return []
    return FeishuBaseSearcher.from_config().search_by_jd(jd_fields, limit=limit)
