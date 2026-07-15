#!/usr/bin/env python3
"""
把 ttc_daemon.db 中的候选人同步到飞书多维表格。

用法
----
    # 默认 dry-run：预览第一条记录会写入什么
    python scripts/sync_daemon_candidates_to_feishu.py

    # 预览全部 147 条
    python scripts/sync_daemon_candidates_to_feishu.py --dry-run --limit 147

    # 真正写入（逐条去重、创建记录、上传附件）
    python scripts/sync_daemon_candidates_to_feishu.py --write --limit 147
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ttc_daemon import db as local_db

DEFAULT_BASE_TOKEN = ""
DEFAULT_TABLE_ID = "tblyT3bebRJsyHar"  # "正式版-简历解析"

DATA_DIR = REPO_ROOT / "data" / "sync_feishu"
PROGRESS_PATH = DATA_DIR / "progress.json"

# 目标表中可写的字段，按字段名映射到 ttc_daemon candidates / raw_profile 的键
FIELD_MAP: Dict[str, Tuple[str, ...]] = {
    "姓名": ("name",),
    "电话": ("phone",),
    "公司": ("current_company",),
    "就职岗位": ("current_title",),
    "现工作地点": ("current_location",),
    "期望工作地点": ("expected_location",),
    "薪资解析": ("expected_salary",),
    "学校": ("school",),
    "学校背景信息": ("education",),
    "本科毕业时间": ("undergraduate_graduation_year",),
    "技术栈": ("tech_stack",),
    "AI 经历": ("ai_experience",),
    "简历解析内容": ("raw_text",),
    "人才库链接": ("source_url",),
    "看机会AI提取": ("opportunity_intent",),
    "备注信息": ("notes",),
}

SELECT_FIELDS: Dict[str, List[str]] = {
    "是否看机会": ["是", "否", "无信息"],
    "是否看机会_无AI": ["是", "否", "无信息"],
    "工作地点": ["北京", "上海", "深圳", "广州", "杭州", "成都", "苏州", "南京", "无匹配类别"],
    "职位类型": ["算法", "前端", "后端", "全栈", "产品", "infra", "爬虫", "运营", "无匹配标签"],
}


def _utc_iso() -> str:
    return __import__("datetime").datetime.utcnow().isoformat()


def _load_json(text: str | None) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _extract_phone(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"1[3-9]\d{9}", str(text).replace(" ", "").replace("-", ""))
    return m.group(0) if m else ""


def _extract_email(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"[\w.-]+@[\w.-]+\.\w+", str(text))
    return m.group(0) if m else ""


def _coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _resolve_profile_value(raw: Dict[str, Any], enriched: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    """优先从 raw_profile 取值，缺失则从 enriched_profile 取。

    兼容两种存储格式：
    1. raw_profile.feishu_fields.{中文名}（飞书人才库导入）
    2. raw_profile.{英文名}（其他来源）
    """
    feishu_fields = raw.get("feishu_fields") or {}
    if not isinstance(feishu_fields, dict):
        feishu_fields = {}
    feishu_aliases = {
        "name": "姓名",
        "phone": "手机号",
        "current_company": "当前公司",
        "current_title": "当前岗位",
        "current_location": "所在城市",
        "expected_location": "期望地点",
        "expected_salary": "期望薪资",
        "school": "学校",
        "degree": "学历",
        "major": "专业",
        "tech_stack": "技能标签",
        "ai_experience": "AI 经历",
        "raw_text": "求职意向",
        "source_url": "原人才库链接",
        "notes": "备注",
        "opportunity_intent": "求职意向",
        "experience_years": "工作年限",
        "undergraduate_graduation_year": "毕业年份",
    }
    feishu_keys = [feishu_aliases.get(k, k) for k in keys]

    for profile in (raw, enriched):
        # 先查英文键
        for key in keys:
            val = profile.get(key)
            if val is not None and val != "":
                return val
        # 再查 feishu_fields 中文键
        for key in feishu_keys:
            val = feishu_fields.get(key)
            if val is not None and val != "":
                return val
    return None


def _build_education_summary(raw: Dict[str, Any], enriched: Dict[str, Any]) -> str:
    education = _resolve_profile_value(raw, enriched, ("education",))
    if isinstance(education, dict):
        parts = [
            education.get("school"),
            education.get("degree"),
            str(education.get("graduation_year")) if education.get("graduation_year") else None,
            education.get("major"),
        ]
        return " ".join(p for p in parts if p)
    education_list = _resolve_profile_value(raw, enriched, ("education_list",))
    if isinstance(education_list, list) and education_list:
        first = education_list[0]
        if isinstance(first, dict):
            parts = [
                first.get("school"),
                first.get("degree"),
                str(first.get("graduation_year")) if first.get("graduation_year") else None,
                first.get("major"),
            ]
            return " ".join(p for p in parts if p)
    # 飞书格式：学校、学历、专业拼接
    school = _resolve_profile_value(raw, enriched, ("school",))
    degree = _resolve_profile_value(raw, enriched, ("degree",))
    major = _resolve_profile_value(raw, enriched, ("major",))
    parts = []
    for p in (school, degree, major):
        if isinstance(p, list):
            p = ", ".join(str(x) for x in p) if p else ""
        if p:
            parts.append(str(p))
    return " ".join(parts)


def _infer_job_type(record: Dict[str, Any], raw: Dict[str, Any]) -> str:
    feishu_fields = raw.get("feishu_fields") or {}
    tech_stack = _coerce_list(record.get("tech_stack") or feishu_fields.get("技能标签"))
    current_title = record.get("current_title") or feishu_fields.get("当前岗位") or ""
    text = " ".join(str(x) for x in tech_stack) + " " + str(current_title)
    text = text.lower()
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
        if any(kw in text for kw in kws):
            return option
    return "无匹配标签"


def _infer_looking_for_opportunity(record: Dict[str, Any], raw: Dict[str, Any]) -> str:
    feishu_fields = raw.get("feishu_fields") or {}
    intent = str(record.get("opportunity_intent") or feishu_fields.get("求职意向") or "").lower()
    if any(w in intent for w in ["是", "yes", "true", "看机会", "考虑", "在职-考虑"]):
        return "是"
    if any(w in intent for w in ["否", "no", "false", "不看", "暂不考虑", "不考虑"]):
        return "否"
    return "无信息"


def _resolve_location(record: Dict[str, Any], raw: Dict[str, Any]) -> str:
    feishu_fields = raw.get("feishu_fields") or {}
    loc = (
        record.get("current_location")
        or record.get("expected_location")
        or raw.get("current_location")
        or raw.get("expected_location")
        or feishu_fields.get("所在城市")
        or feishu_fields.get("期望地点")
        or ""
    )
    if loc:
        # 如果选项中有精确匹配，优先返回
        if loc in SELECT_FIELDS["工作地点"]:
            return loc
        # 否则从文本中匹配第一个已知城市
        for city in SELECT_FIELDS["工作地点"]:
            if city in loc:
                return city
        return loc
    raw_text = str(record.get("raw_text") or "")
    for city in SELECT_FIELDS["工作地点"]:
        if city in raw_text:
            return city
    return ""


def candidate_to_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    """把 ttc_daemon candidate 字典转换为目标多维表格字段名 -> 值。"""
    raw = _load_json(record.get("raw_profile"))
    enriched = _load_json(record.get("enriched_profile"))

    # 基础字段
    payload: Dict[str, Any] = {}
    payload["姓名"] = record.get("name") or raw.get("name") or ""
    payload["电话"] = record.get("phone") or _extract_phone(raw.get("raw_text", "")) or ""

    # 从 profile 提取
    for field_name, keys in FIELD_MAP.items():
        if field_name in ("姓名", "电话"):
            continue
        if field_name == "学校背景信息":
            value = _build_education_summary(raw, enriched)
        elif field_name == "本科毕业时间":
            value = _resolve_profile_value(raw, enriched, keys)
            if value is not None:
                value = str(value)
        elif field_name == "技术栈":
            value = _resolve_profile_value(raw, enriched, keys)
            if isinstance(value, list):
                value = ", ".join(str(x) for x in value)
        else:
            value = _resolve_profile_value(raw, enriched, keys)
        if value is not None and value != "":
            payload[field_name] = value

    # 推断字段
    merged = {**record, **raw, **enriched}
    payload["职位类型"] = _infer_job_type(merged, raw)
    payload["工作地点"] = _resolve_location(merged, raw)
    payload["是否看机会"] = _infer_looking_for_opportunity(merged, raw)
    payload["是否看机会_无AI"] = payload["是否看机会"]

    # select 字段校验
    for field_name, options in SELECT_FIELDS.items():
        if field_name in payload:
            if payload[field_name] not in options:
                payload[field_name] = "无信息" if "看机会" in field_name else "无匹配类别" if field_name == "工作地点" else "无匹配标签"

    # 截断长文本
    max_lengths = {"简历解析内容": 95000}
    for field_name, max_len in max_lengths.items():
        if field_name in payload and len(str(payload[field_name])) > max_len:
            payload[field_name] = str(payload[field_name])[: max_len - 3] + "..."

    # 附件
    attachment_path = record.get("original_attachment_path") or ""
    if attachment_path and Path(attachment_path).is_file():
        payload["__attachment_path__"] = attachment_path

    return payload


def _run_cli(*args: str, cwd: Path | str | None = None) -> Dict[str, Any]:
    cmd = ["lark-cli", "base", *args, "--as", "user"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"lark-cli failed: {result.stderr or result.stdout}")
    stdout = result.stdout.strip()
    if stdout.startswith("```"):
        lines = stdout.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stdout = "\n".join(lines)
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw_stdout": stdout}


def _extract_attachment_token(resp: Dict[str, Any]) -> Optional[str]:
    data = resp.get("data", {})
    if isinstance(data, dict):
        token = data.get("file_token") or data.get("token")
        if token:
            return token
        attachments = data.get("attachments", {})
        if isinstance(attachments, dict):
            for rec_id, fields in attachments.items():
                if isinstance(fields, dict):
                    for fld_id, files in fields.items():
                        if isinstance(files, list) and files:
                            first = files[0]
                            if isinstance(first, dict):
                                token = first.get("file_token") or first.get("token")
                                if token:
                                    return token
    return None


def _record_exists(base_token: str, table_id: str, record: Dict[str, Any]) -> bool:
    """按电话/姓名+公司查询目标表是否已有重复记录。"""
    name = record.get("姓名") or ""
    phone = record.get("电话") or ""
    company = record.get("公司") or ""

    if phone:
        resp = _run_cli(
            "+record-search",
            "--base-token", base_token,
            "--table-id", table_id,
            "--keyword", phone,
            "--search-field", "电话",
            "--limit", "1",
            "--format", "json",
        )
        if _has_search_result(resp):
            return True

    if name and phone:
        keyword = f"{name} {phone}"[:50]
        resp = _run_cli(
            "+record-search",
            "--base-token", base_token,
            "--table-id", table_id,
            "--keyword", keyword,
            "--search-field", "姓名",
            "--search-field", "电话",
            "--limit", "1",
            "--format", "json",
        )
        if _has_search_result(resp):
            return True

    if name and company:
        keyword = f"{name} {company}"[:50]
        resp = _run_cli(
            "+record-search",
            "--base-token", base_token,
            "--table-id", table_id,
            "--keyword", keyword,
            "--search-field", "姓名",
            "--search-field", "公司",
            "--limit", "1",
            "--format", "json",
        )
        if _has_search_result(resp):
            return True

    return False


def _has_search_result(resp: Dict[str, Any]) -> bool:
    if not isinstance(resp, dict):
        return False
    data = resp.get("data", {}) or {}
    total = data.get("total")
    if total:
        return True
    records = data.get("data", [])
    return bool(records)


def _create_record(base_token: str, table_id: str, payload: Dict[str, Any]) -> str:
    """通过 +record-batch-create 创建一条记录，返回 record_id。"""
    attachment_path = payload.pop("__attachment_path__", None)
    fields = list(payload.keys())
    rows = [list(payload.values())]
    batch_json = json.dumps({"fields": fields, "rows": rows}, ensure_ascii=False)

    resp = _run_cli(
        "+record-batch-create",
        "--base-token", base_token,
        "--table-id", table_id,
        "--json", batch_json,
    )

    data = resp.get("data", {})
    record_id = None
    if isinstance(data, dict):
        record_id_list = data.get("record_id_list")
        if isinstance(record_id_list, list) and record_id_list:
            record_id = record_id_list[0]
        records = data.get("records")
        if not record_id and isinstance(records, list) and records:
            record_id = records[0].get("record_id")
    if not record_id:
        raise RuntimeError(f"Batch create did not return a record_id: {resp}")

    if attachment_path:
        _upload_attachment(base_token, table_id, record_id, attachment_path)

    return record_id


def _upload_attachment(base_token: str, table_id: str, record_id: str, file_path: str) -> None:
    path = Path(file_path)
    if not path.is_file():
        return
    resp = _run_cli(
        "+record-upload-attachment",
        "--base-token", base_token,
        "--table-id", table_id,
        "--record-id", record_id,
        "--field-id", "fldZjxabzr",
        "--file", path.name,
        cwd=path.parent,
    )
    token = _extract_attachment_token(resp)
    if not token:
        raise RuntimeError(f"Attachment upload did not return file_token: {resp}")


def _load_progress() -> Dict[str, Any]:
    if PROGRESS_PATH.exists():
        try:
            return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"synced_ids": [], "failed_ids": []}


def _save_progress(progress: Dict[str, Any]) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(progress, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _fetch_candidates(limit: int = 0) -> List[Dict[str, Any]]:
    local_db.init_db()
    with local_db.get_conn() as conn:
        sql = "SELECT * FROM candidates ORDER BY created_at DESC"
        params: List[Any] = []
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 ttc_daemon candidates 到飞书多维表格")
    parser.add_argument("--base-token", default=DEFAULT_BASE_TOKEN, help="飞书 Base token")
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID, help="飞书 table id")
    parser.add_argument("--write", action="store_true", help="真正写入（默认 dry-run）")
    parser.add_argument("--limit", type=int, default=1, help="处理条数，默认 1 条预览")
    parser.add_argument("--resume", action="store_true", help="跳过已同步/失败的记录")
    parser.add_argument("--sleep", type=float, default=3.0, help="每次写入间隔秒数")
    args = parser.parse_args()

    print(f"[INFO] 目标 Base: {args.base_token}")
    print(f"[INFO] 目标 Table: {args.table_id}")
    print(f"[INFO] 模式: {'WRITE' if args.write else 'DRY-RUN'}")

    candidates = _fetch_candidates(args.limit)
    print(f"[INFO] 本地 candidates 读取: {len(candidates)} 条")

    progress = _load_progress()
    synced_ids = set(progress.get("synced_ids", []))
    failed_ids = set(progress.get("failed_ids", []))

    stats = {"total": 0, "skipped": 0, "duplicate": 0, "created": 0, "failed": 0}
    report: List[Dict[str, Any]] = []

    for idx, candidate in enumerate(candidates, start=1):
        cid = candidate["id"]
        stats["total"] += 1

        if args.resume and cid in synced_ids:
            stats["skipped"] += 1
            print(f"[{idx}/{len(candidates)}] SKIP synced: {cid}")
            continue

        item: Dict[str, Any] = {"index": idx, "candidate_id": cid, "ok": False}
        try:
            payload = candidate_to_payload(candidate)
            if args.write:
                if _record_exists(args.base_token, args.table_id, payload):
                    stats["duplicate"] += 1
                    item["action"] = "duplicate"
                    item["ok"] = True
                    print(f"[{idx}/{len(candidates)}] SKIP duplicate: {payload.get('姓名') or cid}")
                else:
                    record_id = _create_record(args.base_token, args.table_id, payload)
                    stats["created"] += 1
                    item["action"] = "created"
                    item["feishu_record_id"] = record_id
                    item["ok"] = True
                    synced_ids.add(cid)
                    progress["synced_ids"] = sorted(synced_ids)
                    _save_progress(progress)
                    print(f"[{idx}/{len(candidates)}] CREATED {record_id}: {payload.get('姓名') or cid}")
            else:
                # dry-run：展示 payload
                item["action"] = "dry_run"
                item["payload"] = payload
                item["ok"] = True
                print(f"[{idx}/{len(candidates)}] DRY-RUN: {payload.get('姓名') or cid}")
                print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        except Exception as exc:
            stats["failed"] += 1
            item["action"] = "failed"
            item["error"] = str(exc)
            failed_ids.add(cid)
            progress["failed_ids"] = sorted(failed_ids)
            _save_progress(progress)
            print(f"[{idx}/{len(candidates)}] FAIL: {cid} -> {exc}", file=sys.stderr)

        report.append(item)

        if args.write and idx < len(candidates):
            time.sleep(args.sleep)

    summary = {
        "generated_at": _utc_iso(),
        "base_token": args.base_token,
        "table_id": args.table_id,
        "write_mode": args.write,
        "stats": stats,
        "report": report,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    report_path = DATA_DIR / f"report_{int(time.time())}.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"同步完成（mode={'WRITE' if args.write else 'DRY-RUN'}）")
    print(f"  总计:     {stats['total']}")
    print(f"  跳过:     {stats['skipped']}")
    print(f"  重复:     {stats['duplicate']}")
    print(f"  创建:     {stats['created']}")
    print(f"  失败:     {stats['failed']}")
    print(f"  报告:     {report_path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
