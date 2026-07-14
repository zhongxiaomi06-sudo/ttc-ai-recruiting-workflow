"""Sync ttc_daemon SQLite candidates to cloud RDS MySQL.

Reads the ttc_daemon `candidates` table and upserts each row into the shared
`cloud_candidates` table so all AI tools can query one candidate store.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "candidate-collector"))

from cloud_sync.client import CloudSyncClient
from cloud_sync.config import rds_configured

DB_PATH = ROOT / "ttc_daemon" / "data" / "ttc_daemon.db"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def _row_to_cloud(row: sqlite3.Row) -> dict:
    raw_profile = {}
    enriched_profile = {}
    try:
        raw_profile = json.loads(row["raw_profile"] or "{}")
    except Exception:
        pass
    try:
        enriched_profile = json.loads(row["enriched_profile"] or "{}")
    except Exception:
        pass

    source_types = []
    try:
        source_types = json.loads(row["source_types"] or "[]")
    except Exception:
        source_types = [row["source_types"]] if row["source_types"] else []

    return {
        "fingerprint": row["id"],
        "name": row["name"] or "",
        "platform": "ttc_daemon",
        "source_url": raw_profile.get("source_url") or "",
        "source_type": ";".join(source_types) or "",
        "title": raw_profile.get("current_title") or "",
        "location": raw_profile.get("current_location") or "",
        "current_company": raw_profile.get("current_company") or "",
        "current_role": raw_profile.get("current_title") or "",
        "phone": row["phone"] or "",
        "email": row["email"] or "",
        "undergraduate_school": raw_profile.get("undergraduate_school") or "",
        "expected_salary": raw_profile.get("expected_salary") or "",
        "experiences_json": json.dumps(raw_profile.get("work_experiences", []), ensure_ascii=False, default=str),
        "education_json": json.dumps(raw_profile.get("education", {}), ensure_ascii=False, default=str),
        "keywords_json": json.dumps(raw_profile.get("skills", []), ensure_ascii=False, default=str),
        "raw_text": raw_profile.get("raw_text") or "",
        "review_status": "pending",
        "attachment_path": row["original_attachment_path"],
        "attachment_sha256": raw_profile.get("attachment_sha256"),
        "collected_at": _parse_dt(row["created_at"]),
        "parsed_json": json.dumps(
            {
                "ttc_daemon_id": row["id"],
                "raw_profile": raw_profile,
                "enriched_profile": enriched_profile,
                "jd_alignment_score": row["jd_alignment_score"],
                "gold_score": row["gold_score"],
                "risk_flags": row["risk_flags"],
                "overall_score": row["overall_score"],
                "status": row["status"],
            },
            ensure_ascii=False,
            default=str,
        ),
    }


def fetch_candidates(limit: int = 0) -> list[dict]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    sql = "SELECT * FROM candidates ORDER BY created_at"
    if limit > 0:
        sql += f" LIMIT {limit}"
    rows = [_row_to_cloud(r) for r in cur.execute(sql).fetchall()]
    conn.close()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 ttc_daemon 候选人到云端 RDS")
    parser.add_argument("--limit", type=int, default=0, help="最多同步数量，0 表示全部")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ensure-schema", action="store_true")
    args = parser.parse_args()

    if not rds_configured():
        print("错误：RDS 环境变量未配置。请设置 RDS_HOST, RDS_DB, RDS_USER, RDS_PASSWORD。")
        return 1

    client = CloudSyncClient()
    if args.dry_run:
        client.dry_run = True
    if args.ensure_schema:
        client.ensure_schema()

    rows = fetch_candidates(args.limit)
    print(f"本地 ttc_daemon 候选人数：{len(rows)}")
    if not rows:
        return 0

    stats = client.upsert_candidates(rows)
    print(f"同步完成：新增 {stats['inserted']}，更新 {stats['updated']}，错误 {stats['errors']}")
    print(f"云端总数：{client.count_candidates()}")
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
