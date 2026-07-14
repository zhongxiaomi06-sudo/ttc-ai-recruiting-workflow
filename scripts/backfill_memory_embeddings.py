"""Backfill embeddings for cloud memories to enable semantic search.

Fetches memories that have no embedding yet, embeds them via the configured
OpenAI-compatible endpoint, and stores the vectors in ``memories.embedding``.

Usage:
    cd /Users/ashley/Downloads/ttc的交易系统
    candidate-collector/.venv/bin/python scripts/backfill_memory_embeddings.py --dry-run
    candidate-collector/.venv/bin/python scripts/backfill_memory_embeddings.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "candidate-collector"))

from cloud_sync import embeddings
from cloud_sync.client import CloudSyncClient
from cloud_sync.config import rds_configured


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill memory embeddings")
    parser.add_argument("--project", default=None, help="restrict to a project_id")
    parser.add_argument("--limit", type=int, default=0, help="max memories to embed (0 = all)")
    parser.add_argument("--batch-size", type=int, default=32, help="texts per embedding request")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not rds_configured():
        print("错误：RDS 未配置（RDS_HOST/RDS_DB/RDS_USER/RDS_PASSWORD）")
        return 1
    if not embeddings.embeddings_configured():
        print("错误：Embedding 未配置（EMBEDDING_API_KEY 或 OPENAI_NEXT_API_KEY）")
        return 1

    client = CloudSyncClient()
    if args.dry_run:
        client.dry_run = True

    # Migrate pre-existing databases: add embedding columns if missing.
    client.ensure_embedding_column()

    total_done = 0
    while True:
        fetch_limit = args.batch_size
        if args.limit:
            remaining = args.limit - total_done
            if remaining <= 0:
                break
            fetch_limit = min(fetch_limit, remaining)

        rows = client.list_memories_without_embedding(
            limit=fetch_limit, project_id=args.project
        )
        if not rows:
            break

        texts = [(r.get("content_text") or "") for r in rows]
        try:
            vectors = embeddings.embed_texts(texts)
        except Exception as exc:
            print(f"[error] embedding batch failed: {exc}")
            return 1

        updates = [
            (r["id"], embeddings.serialize_embedding(vec), embeddings.EMBEDDING_MODEL)
            for r, vec in zip(rows, vectors)
        ]
        client.update_memory_embeddings(updates)
        total_done += len(rows)
        print(f"已嵌入 {total_done} 条记忆（模型 {embeddings.EMBEDDING_MODEL}）")

    print(f"完成：共嵌入 {total_done} 条记忆")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
