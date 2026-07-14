"""MySQL client for the cloud sync layer.

Provides connection helpers, idempotent upserts, and simple query helpers
for the unified cloud RDS (MySQL) instance.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

import pymysql
from pymysql.cursors import DictCursor

from .config import RDS_SYNC_BATCH_SIZE, RDS_SYNC_DRY_RUN, build_conn_kwargs


def _memory_id(row: dict[str, Any]) -> str:
    """Generate a stable idempotency key from project + source + content."""
    import hashlib

    raw = f"{row.get('project_id', '')}:{row.get('source', '')}:{row.get('content_text', '')}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


@contextmanager
def get_conn() -> Iterator[pymysql.Connection]:
    """Yield a MySQL connection and commit/rollback automatically."""
    conn = pymysql.connect(**build_conn_kwargs())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class CloudSyncClient:
    """Thin wrapper around pymysql for candidate and memory upserts."""

    def __init__(self) -> None:
        self.dry_run = RDS_SYNC_DRY_RUN

    def ensure_schema(self, schema_sql_path: str | None = None) -> None:
        """Create tables if they do not already exist."""
        if self.dry_run:
            print("[dry-run] would ensure schema")
            return
        from pathlib import Path

        if schema_sql_path is None:
            schema_sql_path = str(Path(__file__).with_name("schema.sql"))
        sql = Path(schema_sql_path).read_text(encoding="utf-8")
        # MySQL executes statements one at a time.
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        with get_conn() as conn:
            with conn.cursor() as cur:
                for stmt in statements:
                    try:
                        cur.execute(stmt)
                    except (pymysql.err.ProgrammingError, pymysql.err.OperationalError) as exc:
                        # Ignore duplicate index/table errors on re-runs.
                        if "Duplicate key name" in str(exc) or "already exists" in str(exc):
                            continue
                        raise

    def upsert_candidates(
        self,
        rows: list[dict[str, Any]],
        batch_size: int = RDS_SYNC_BATCH_SIZE,
    ) -> dict[str, int]:
        """Upsert candidate rows into cloud_candidates.

        Args:
            rows: List of dicts with keys matching cloud_candidates columns.
            batch_size: Commit every N rows.

        Returns:
            {"inserted": int, "updated": int, "errors": int}
        """
        if not rows:
            return {"inserted": 0, "updated": 0, "errors": 0}

        inserted = updated = errors = 0
        upsert_sql = """
        INSERT INTO cloud_candidates (
            fingerprint, name, platform, source_url, source_type, title,
            location, current_company, current_role, phone, email,
            undergraduate_school, expected_salary, experiences_json,
            education_json, keywords_json, raw_text, review_status,
            attachment_path, attachment_sha256, collected_at, parsed_json
        ) VALUES (
            %(fingerprint)s, %(name)s, %(platform)s, %(source_url)s,
            %(source_type)s, %(title)s, %(location)s, %(current_company)s,
            %(current_role)s, %(phone)s, %(email)s, %(undergraduate_school)s,
            %(expected_salary)s, %(experiences_json)s, %(education_json)s,
            %(keywords_json)s, %(raw_text)s, %(review_status)s,
            %(attachment_path)s, %(attachment_sha256)s, %(collected_at)s,
            %(parsed_json)s
        )
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            current_company = VALUES(current_company),
            current_role = VALUES(current_role),
            phone = VALUES(phone),
            email = VALUES(email),
            raw_text = VALUES(raw_text),
            review_status = VALUES(review_status),
            attachment_sha256 = VALUES(attachment_sha256),
            collected_at = VALUES(collected_at),
            parsed_json = VALUES(parsed_json),
            updated_at = NOW()
        """

        if self.dry_run:
            print(f"[dry-run] would upsert {len(rows)} candidates")
            return {"inserted": len(rows), "updated": 0, "errors": 0}

        with get_conn() as conn:
            with conn.cursor() as cur:
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    for row in batch:
                        try:
                            affected = cur.execute(upsert_sql, row)
                            # pymysql: 1 = insert, 2 = update (for ON DUPLICATE KEY UPDATE)
                            if affected == 1:
                                inserted += 1
                            else:
                                updated += 1
                        except Exception as exc:
                            errors += 1
                            print(f"[error] fingerprint={row.get('fingerprint')}: {exc}")
                    conn.commit()

        return {"inserted": inserted, "updated": updated, "errors": errors}

    def upsert_memories(
        self,
        rows: list[dict[str, Any]],
        batch_size: int = RDS_SYNC_BATCH_SIZE,
    ) -> dict[str, int]:
        """Upsert memory rows into memories.

        Rows must contain at least: project_id, source, content_type, content_text.
        """
        if not rows:
            return {"inserted": 0, "updated": 0, "errors": 0}

        inserted = updated = errors = 0
        upsert_sql = """
        INSERT INTO memories (
            project_id, source, content_type, content_text, metadata, source_record_id
        ) VALUES (
            %(project_id)s, %(source)s, %(content_type)s, %(content_text)s,
            %(metadata)s, %(source_record_id)s
        )
        ON DUPLICATE KEY UPDATE
            content_text = VALUES(content_text),
            metadata = VALUES(metadata),
            updated_at = NOW()
        """

        if self.dry_run:
            print(f"[dry-run] would upsert {len(rows)} memories")
            return {"inserted": len(rows), "updated": 0, "errors": 0}

        with get_conn() as conn:
            with conn.cursor() as cur:
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    for row in batch:
                        # Ensure idempotency key exists.
                        if not row.get("source_record_id"):
                            row["source_record_id"] = _memory_id(row)
                        # Serialize metadata dict to JSON string for pymysql.
                        if isinstance(row.get("metadata"), dict):
                            row["metadata"] = json.dumps(row["metadata"], ensure_ascii=False)
                        try:
                            affected = cur.execute(upsert_sql, row)
                            if affected == 1:
                                inserted += 1
                            else:
                                updated += 1
                        except Exception as exc:
                            errors += 1
                            print(f"[error] memory id={row.get('source_record_id')}: {exc}")
                    conn.commit()

        return {"inserted": inserted, "updated": updated, "errors": errors}

    def count_candidates(self) -> int:
        """Return total candidate count in cloud_candidates."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM cloud_candidates")
                return cur.fetchone()[0]

    def count_memories(self) -> int:
        """Return total memory count in memories."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM memories")
                return cur.fetchone()[0]

    def list_recent_candidates(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent candidates as a list of dicts."""
        with get_conn() as conn:
            with conn.cursor(DictCursor) as cur:
                cur.execute(
                    "SELECT * FROM cloud_candidates ORDER BY collected_at DESC LIMIT %s",
                    (limit,),
                )
                return [dict(r) for r in cur.fetchall()]

    # ── Embeddings / semantic search ────────────────────────────────

    def ensure_embedding_column(self) -> None:
        """Add embedding columns to ``memories`` for pre-existing databases.

        CREATE TABLE IF NOT EXISTS does not alter an existing table, so we
        add the columns explicitly and ignore duplicate-column errors.
        """
        if self.dry_run:
            print("[dry-run] would ensure embedding columns")
            return
        alters = [
            "ALTER TABLE memories ADD COLUMN embedding JSON",
            "ALTER TABLE memories ADD COLUMN embedding_model VARCHAR(128)",
            "ALTER TABLE memories ADD COLUMN embedded_at DATETIME",
        ]
        with get_conn() as conn:
            with conn.cursor() as cur:
                for stmt in alters:
                    try:
                        cur.execute(stmt)
                    except (pymysql.err.ProgrammingError, pymysql.err.OperationalError) as exc:
                        if "Duplicate column" in str(exc) or "already exists" in str(exc):
                            continue
                        raise

    def list_memories_without_embedding(
        self, limit: int = 500, project_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return memories that still need an embedding."""
        sql = (
            "SELECT id, content_text FROM memories WHERE embedding IS NULL"
        )
        params: list[Any] = []
        if project_id:
            sql += " AND project_id = %s"
            params.append(project_id)
        sql += " ORDER BY id LIMIT %s"
        params.append(limit)
        with get_conn() as conn:
            with conn.cursor(DictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]

    def update_memory_embeddings(self, updates: list[tuple[int, str, str]]) -> int:
        """Persist embeddings. ``updates`` = [(memory_id, embedding_json, model), ...]."""
        if not updates:
            return 0
        if self.dry_run:
            print(f"[dry-run] would update {len(updates)} memory embeddings")
            return len(updates)
        sql = (
            "UPDATE memories SET embedding = %s, embedding_model = %s, "
            "embedded_at = NOW() WHERE id = %s"
        )
        count = 0
        with get_conn() as conn:
            with conn.cursor() as cur:
                for memory_id, embedding_json, model in updates:
                    cur.execute(sql, (embedding_json, model, memory_id))
                    count += cur.rowcount
            conn.commit()
        return count

    def get_memory_embeddings(
        self, project_id: str | None = None, limit: int = 5000
    ) -> list[dict[str, Any]]:
        """Return id/source/content/embedding for memories that have an embedding."""
        sql = (
            "SELECT id, project_id, source, content_type, "
            "LEFT(content_text, 600) AS content_text, embedding "
            "FROM memories WHERE embedding IS NOT NULL"
        )
        params: list[Any] = []
        if project_id:
            sql += " AND project_id = %s"
            params.append(project_id)
        sql += " LIMIT %s"
        params.append(limit)
        with get_conn() as conn:
            with conn.cursor(DictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]
