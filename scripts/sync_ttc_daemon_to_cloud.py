"""Sync ttc_daemon data/ingest artifacts to cloud RDS memories.

Scans JSON artifacts produced by ttc_daemon (chatgpt_share, feishu_web,
web_page, candidate_resume, etc.) and imports them into the shared RDS
memories table so all AI tools can query one long-term store.

Usage:
    cd /Users/ashley/Downloads/ttc的交易系统
    python scripts/sync_ttc_daemon_to_cloud.py --ensure-schema --dry-run
    python scripts/sync_ttc_daemon_to_cloud.py --ensure-schema
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "candidate-collector"))

from cloud_sync.client import CloudSyncClient
from cloud_sync.config import rds_configured


def _scan_ingest(project: str, ingest_dir: Path) -> list[dict]:
    """Scan ttc_daemon data/ingest JSON files and convert to memory rows."""
    rows: list[dict] = []
    if not ingest_dir.exists():
        return rows

    for path in sorted(ingest_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        # source type is the directory two levels above the file,
        # e.g. data/ingest/chatgpt_share/2026-07-07/<id>.json
        source_type = path.parent.parent.name
        text = (
            data.get("conversation")
            or data.get("raw_text")
            or data.get("text")
            or data.get("content")
            or ""
        )
        if not text:
            continue

        record_id = data.get("id") or data.get("record_id") or f"{source_type}:{path.stem}"
        rows.append(
            {
                "project_id": project,
                "source": f"ttc_daemon:{source_type}",
                "content_type": "chat" if "chat" in source_type else "artifact",
                "content_text": text[:50000],
                "metadata": {
                    "path": str(path),
                    "source_type": source_type,
                    "artifact_id": data.get("id") or data.get("record_id"),
                },
                "source_record_id": record_id,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="把 ttc_daemon 的 data/ingest 数据同步到云端 RDS memories"
    )
    parser.add_argument("--project", default="ttc", help="项目标识")
    parser.add_argument(
        "--ingest-dir",
        type=Path,
        default=ROOT / "ttc_daemon" / "data" / "ingest",
        help="ttc_daemon data/ingest 目录",
    )
    parser.add_argument("--dry-run", action="store_true", help="预览但不写入")
    parser.add_argument("--ensure-schema", action="store_true", help="同步前先创建表")
    args = parser.parse_args()

    if not rds_configured():
        print("错误：RDS 环境变量未配置。请设置 RDS_HOST, RDS_DB, RDS_USER, RDS_PASSWORD。")
        return 1

    client = CloudSyncClient()
    if args.dry_run:
        client.dry_run = True
    if args.ensure_schema:
        client.ensure_schema()

    rows = _scan_ingest(args.project, args.ingest_dir)
    print(f"扫描到 {len(rows)} 条 artifact 记录")
    if not rows:
        return 0

    stats = client.upsert_memories(rows)
    print(
        f"同步完成：新增 {stats['inserted']}，更新 {stats['updated']}，错误 {stats['errors']}"
    )
    print(f"云端记忆总数：{client.count_memories()}")
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
