"""Sync ALL local AI conversation histories to the cloud memories table.

Covers every tool 钟笑咪 uses, so the cloud holds one searchable long-term
memory across all of them:

    claude_code  ~/.claude/projects/**/*.jsonl        (Claude Code transcripts)
    codex        ~/.codex/sessions/**/*.jsonl         (Codex CLI sessions)
    opencode     ~/.local/share/opencode/opencode.db  (OpenCode sqlite)

Each session is concatenated into "ROLE: text" turns and split into ~6k-char
chunks (aligned with the embedding model's trim). Rows are idempotent: the
memories.content_hash generated column dedups identical content on re-runs.

Usage:
    cd /Users/ashley/Downloads/ttc的交易系统
    candidate-collector/.venv/bin/python scripts/sync_all_conversations_to_cloud.py --dry-run
    candidate-collector/.venv/bin/python scripts/sync_all_conversations_to_cloud.py
    candidate-collector/.venv/bin/python scripts/sync_all_conversations_to_cloud.py --source claude_code
"""
from __future__ import annotations

import argparse
import glob
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "candidate-collector"))

from cloud_sync.client import CloudSyncClient
from cloud_sync.config import rds_configured

HOME = Path.home()
MAX_CHARS = 6000  # per memory chunk; matches embedding trim


# ── text extraction helpers ───────────────────────────────────────

def _blocks_to_text(content) -> str:
    """Join text blocks from a Claude/Codex content field; skip tools/thinking."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict) and b.get("type") in ("text", "input_text", "output_text"):
                t = b.get("text")
                if isinstance(t, str):
                    out.append(t)
        return "\n".join(out)
    return ""


def _is_noise(text: str) -> bool:
    """Heuristic: skip command echoes, system reminders, tool wrappers."""
    s = text.strip()
    if not s or len(s) < 2:
        return True
    if s.startswith("<"):  # <command-name>, <system-reminder>, <local-command-*>, <ide_selection>
        return True
    head = s[:60]
    if any(k in head for k in ("command-name", "local-command", "system-reminder", "caveat")):
        return True
    if s.startswith(("cd /", "cd ~", "cd/", "export ")) and "\n" not in s:
        return True
    return False


# ── per-source extractors ─────────────────────────────────────────

def iter_claude_code(base: Path):
    for path in sorted(base.glob("**/*.jsonl")):
        turns = []
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                t = o.get("type")
                if t not in ("user", "assistant"):
                    continue
                text = _blocks_to_text(o.get("message", {}).get("content"))
                if not text:
                    continue
                if t == "user" and _is_noise(text):
                    continue
                turns.append((t, text))
        except OSError:
            continue
        if turns:
            yield path.stem, turns, {"file": str(path), "directory": path.parent.name}


def iter_codex(base: Path):
    for path in sorted(base.glob("**/*.jsonl")):
        turns = []
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("type") != "response_item":
                    continue
                p = o.get("payload", {})
                role = p.get("role")
                if role not in ("user", "assistant"):
                    continue
                text = _blocks_to_text(p.get("content"))
                if not text:
                    continue
                if role == "user" and _is_noise(text):
                    continue
                turns.append((role, text))
        except OSError:
            continue
        if turns:
            yield path.stem, turns, {"file": str(path)}


def iter_opencode(db_path: Path):
    if not db_path.exists():
        return
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT p.session_id AS sid,
                   json_extract(m.data, '$.role') AS role,
                   json_extract(p.data, '$.text') AS text,
                   p.time_created AS ts
            FROM part p JOIN message m ON p.message_id = m.id
            WHERE json_extract(p.data, '$.type') = 'text'
            ORDER BY p.session_id, p.time_created
            """
        ).fetchall()
        titles = {
            r[0]: r[1] for r in conn.execute("SELECT id, title FROM session")
        }
    finally:
        conn.close()

    sessions: dict[str, list] = {}
    for sid, role, text, _ts in rows:
        if not text or role not in ("user", "assistant"):
            continue
        if role == "user" and _is_noise(text):
            continue
        sessions.setdefault(sid, []).append((role, text))
    for sid, turns in sessions.items():
        if turns:
            yield sid, turns, {"title": titles.get(sid, ""), "db": str(db_path)}


# ── chunking into memory rows ─────────────────────────────────────

def chunk_to_rows(source: str, session_id: str, turns, meta: dict, project: str):
    parts: list[list[str]] = []
    cur: list[str] = []
    cur_len = 0
    for role, text in turns:
        seg = f"{role.upper()}: {text.strip()}\n\n"
        if cur_len + len(seg) > MAX_CHARS and cur:
            parts.append(cur)
            cur, cur_len = [], 0
        cur.append(seg)
        cur_len += len(seg)
    if cur:
        parts.append(cur)

    for i, chunk in enumerate(parts):
        row = {
            "project_id": project,
            "source": source,
            "content_type": "conversation",
            "content_text": "".join(chunk).strip(),
            "metadata": {**meta, "session_id": session_id, "part": i, "parts": len(parts)},
            "source_record_id": f"{source}:{session_id}:{i}",
        }
        yield row


SOURCES = {
    "claude_code": lambda: iter_claude_code(HOME / ".claude/projects"),
    "codex": lambda: iter_codex(HOME / ".codex/sessions"),
    "opencode": lambda: iter_opencode(HOME / ".local/share/opencode/opencode.db"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync all AI conversations to cloud memories")
    ap.add_argument("--source", choices=list(SOURCES) + ["all"], default="all")
    ap.add_argument("--project", default="ttc")
    ap.add_argument("--limit", type=int, default=0, help="max sessions per source (0=all)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ensure-schema", action="store_true")
    args = ap.parse_args()

    if not rds_configured():
        print("错误：RDS 未配置（RDS_HOST/RDS_DB/RDS_USER/RDS_PASSWORD）")
        return 1

    client = CloudSyncClient()
    if args.dry_run:
        client.dry_run = True
    if args.ensure_schema:
        client.ensure_schema()
        client.ensure_embedding_column()

    sources = [args.source] if args.source != "all" else list(SOURCES)
    grand = {"sessions": 0, "rows": 0, "inserted": 0, "updated": 0, "errors": 0}

    for src in sources:
        rows = []
        n_sess = 0
        for session_id, turns, meta in SOURCES[src]():
            n_sess += 1
            if args.limit and n_sess > args.limit:
                break
            rows.extend(chunk_to_rows(src, session_id, turns, meta, args.project))
        stats = client.upsert_memories(rows)
        grand["sessions"] += n_sess
        grand["rows"] += len(rows)
        for k in ("inserted", "updated", "errors"):
            grand[k] += stats[k]
        print(f"[{src}] 会话 {n_sess} → 记忆块 {len(rows)} | 新增 {stats['inserted']} 更新 {stats['updated']} 错误 {stats['errors']}")

    print(f"\n总计：会话 {grand['sessions']} → 记忆块 {grand['rows']} | 新增 {grand['inserted']} 更新 {grand['updated']} 错误 {grand['errors']}")
    print("提示：新记忆需要生成向量才能语义检索，接着跑 scripts/backfill_memory_embeddings.py")
    return 0 if grand["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
