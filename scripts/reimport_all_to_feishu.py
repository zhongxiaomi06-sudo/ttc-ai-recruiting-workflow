#!/usr/bin/env python3
"""
把 candidate-collector 后端 ingestion_log 中所有人选重新导入飞书人才库。

默认会强制重新写入（不跳过去重），因为用户明确要"再次导入"。

用法：
    uv run python scripts/reimport_all_to_feishu.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "candidate-collector" / "data" / "candidates.db"
IMPORT_API = "http://127.0.0.1:8765/api/import-browser-capture"


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def build_payload_from_log(row: sqlite3.Row) -> dict[str, Any] | None:
    """从 ingestion_log 行恢复可重新导入的 payload。"""
    dry_run_payload = row["dry_run_payload"]
    if not dry_run_payload:
        return None
    try:
        data = json.loads(dry_run_payload)
    except json.JSONDecodeError:
        return None
    candidate = data.get("candidate") if isinstance(data, dict) else None
    if not isinstance(candidate, dict):
        return None

    raw_text = candidate.get("raw_text") or ""
    if len(raw_text) < 20:
        # 尝试从 work_experiences / education 构造文本
        lines = [candidate.get("name") or ""]
        if candidate.get("current_company"):
            lines.append(f"当前公司: {candidate.get('current_company')}")
        if candidate.get("current_title"):
            lines.append(f"当前职位: {candidate.get('current_title')}")
        for w in candidate.get("work_experiences") or []:
            lines.append(f"{w.get('company', '')} | {w.get('role', '')} | {w.get('period', '')}")
        for e in candidate.get("education_list") or []:
            lines.append(f"{e.get('school', '')} | {e.get('degree', '')} | {e.get('major', '')}")
        raw_text = "\n".join(line for line in lines if line)

    if len(raw_text) < 10:
        return None

    return {
        "url": candidate.get("source_url") or "",
        "title": candidate.get("name") or "",
        "heading": candidate.get("name") or "",
        "text": raw_text,
        "platform": candidate.get("source_platform") or "unknown",
        "source_type": candidate.get("source_type") or "reimport",
        "skip_duplicates": False,
        "check_feishu_exists": False,
    }


def reimport(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        resp = requests.post(IMPORT_API, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def main() -> int:
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ingestion_log WHERE feishu_write_status='success' ORDER BY id ASC"
        ).fetchall()

    print(f"[1/2] 从后端读取到 {len(rows)} 条成功导入记录")
    created = 0
    failed = 0
    skipped = 0

    for idx, row in enumerate(rows, 1):
        payload = build_payload_from_log(row)
        if not payload:
            skipped += 1
            continue
        name = payload.get("title") or "未知"
        print(f"  {idx}/{len(rows)} {name} ...", end=" ", flush=True)
        result = reimport(payload)
        action = result.get("action", "")
        if result.get("ok") and action == "created":
            created += 1
            print("created", flush=True)
        elif result.get("ok") and "duplicate" in action:
            skipped += 1
            print("skipped", flush=True)
        else:
            failed += 1
            print(f"failed: {result.get('error', action)}", flush=True)
        if idx < len(rows):
            time.sleep(0.3)

    print(f"\n[2/2] 完成：导入 {created} / 跳过 {skipped} / 失败 {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
