"""Bulk import local resume files directly to cloud RDS MySQL.

Uses the candidate-collector unified parser to extract structured data,
then upserts into cloud_candidates. Does not require Feishu configuration.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "candidate-collector"))

from cloud_sync.client import CloudSyncClient
from cloud_sync.config import rds_configured
from cloud_sync.transform import candidate_record_to_cloud
from models import CandidateRecord
from parsers.unified_parser import parse_resume_file

RESUME_DIR = ROOT / "简历数据"
SUPPORTED = {".pdf", ".doc", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".tiff"}


def main() -> int:
    parser = argparse.ArgumentParser(description="批量导入本地简历到云端 RDS")
    parser.add_argument("--dir", type=Path, default=RESUME_DIR, help="简历目录")
    parser.add_argument("--limit", type=int, default=0, help="最多导入数量，0 表示全部")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ensure-schema", action="store_true")
    args = parser.parse_args()

    if not rds_configured():
        print("错误：RDS 环境变量未配置。请设置 RDS_HOST, RDS_DB, RDS_USER, RDS_PASSWORD。")
        return 1

    if not args.dir.exists():
        print(f"错误：目录不存在 {args.dir}")
        return 1

    client = CloudSyncClient()
    if args.dry_run:
        client.dry_run = True
    if args.ensure_schema:
        client.ensure_schema()

    files = sorted(
        p for p in args.dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED
    )
    if args.limit > 0:
        files = files[: args.limit]

    print(f"扫描到 {len(files)} 份简历")
    if not files:
        return 0

    rows: list[dict] = []
    failed = 0
    for idx, path in enumerate(files, 1):
        print(f"[{idx}/{len(files)}] {path.name} ...", end=" ", flush=True)
        try:
            record = parse_resume_file(path)
            row = candidate_record_to_cloud(record)
            # Preserve original file path as attachment_path.
            row["attachment_path"] = str(path)
            rows.append(row)
            print("OK")
        except Exception as exc:
            print(f"失败：{exc}")
            failed += 1

    if not rows:
        return 0

    stats = client.upsert_candidates(rows)
    print(f"\n同步完成：新增 {stats['inserted']}，更新 {stats['updated']}，错误 {stats['errors']}")
    print(f"解析失败：{failed}")
    print(f"云端总数：{client.count_candidates()}")
    return 0 if stats["errors"] == 0 and failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
