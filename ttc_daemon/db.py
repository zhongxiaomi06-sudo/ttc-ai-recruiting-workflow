import sqlite3
import json
import uuid
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from .config import DATA_DIR

DB_PATH = DATA_DIR / "ttc_daemon.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ingest_records (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_url TEXT,
                title TEXT,
                raw_text TEXT,
                markdown TEXT,
                dom_text TEXT,
                script_payload TEXT,
                read_method TEXT,
                read_status TEXT,
                content_type_guess TEXT,
                error_reason TEXT,
                error TEXT,
                capture_meta TEXT,
                payload TEXT,
                collected_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS read_jobs (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_url TEXT,
                title TEXT,
                status TEXT DEFAULT 'pending',
                method TEXT,
                raw_text TEXT,
                markdown TEXT,
                read_status TEXT,
                content_type_guess TEXT,
                error_reason TEXT,
                error TEXT,
                payload TEXT,
                capture_meta TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS normalized_artifacts (
                id TEXT PRIMARY KEY,
                raw_ingest_id TEXT,
                artifact_type TEXT,
                confidence REAL,
                reason TEXT,
                normalized_payload TEXT,
                status TEXT DEFAULT 'pending',
                mission_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                name TEXT,
                phone TEXT,
                email TEXT,
                source_types TEXT,
                raw_profile TEXT,
                enriched_profile TEXT,
                jd_alignment_score REAL,
                gold_score REAL,
                risk_flags TEXT,
                overall_score REAL,
                status TEXT DEFAULT 'new',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS call_list (
                id TEXT PRIMARY KEY,
                candidate_id TEXT,
                mission_id TEXT,
                jd_record_id TEXT,
                priority INTEGER,
                talking_points TEXT,
                evidence TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                candidate_id TEXT,
                call_list_id TEXT,
                outcome TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS missions (
                id TEXT PRIMARY KEY,
                jd_record_id TEXT,
                normalized_artifact_id TEXT,
                state TEXT DEFAULT 'created',
                resume_state TEXT,
                jd_fields TEXT,
                candidate_ids TEXT,
                call_list_ids TEXT,
                human_task_ids TEXT,
                config TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT,
                outcome TEXT
            );

            CREATE TABLE IF NOT EXISTS human_tasks (
                id TEXT PRIMARY KEY,
                mission_id TEXT,
                role TEXT,
                task_type TEXT,
                status TEXT DEFAULT 'pending',
                payload TEXT,
                result TEXT,
                html_url TEXT,
                assigned_to TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                opened_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (mission_id) REFERENCES missions(id)
            );

            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                mission_id TEXT,
                agent_name TEXT,
                input TEXT,
                output TEXT,
                decision TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mission_id) REFERENCES missions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_ingest_source ON ingest_records(source_type);
            CREATE INDEX IF NOT EXISTS idx_read_jobs_status ON read_jobs(status);
            CREATE INDEX IF NOT EXISTS idx_artifacts_status ON normalized_artifacts(status);
            CREATE INDEX IF NOT EXISTS idx_candidates_score ON candidates(overall_score DESC);
            CREATE INDEX IF NOT EXISTS idx_missions_state ON missions(state);
            CREATE INDEX IF NOT EXISTS idx_human_tasks_status ON human_tasks(status);
        """)
        _ensure_column(conn, "ingest_records", "dom_text", "TEXT")
        _ensure_column(conn, "ingest_records", "script_payload", "TEXT")
        _ensure_column(conn, "ingest_records", "read_status", "TEXT")
        _ensure_column(conn, "ingest_records", "content_type_guess", "TEXT")
        _ensure_column(conn, "ingest_records", "error_reason", "TEXT")
        _ensure_column(conn, "read_jobs", "title", "TEXT")
        _ensure_column(conn, "read_jobs", "markdown", "TEXT")
        _ensure_column(conn, "read_jobs", "read_status", "TEXT")
        _ensure_column(conn, "read_jobs", "content_type_guess", "TEXT")
        _ensure_column(conn, "read_jobs", "error_reason", "TEXT")
        _ensure_column(conn, "normalized_artifacts", "reason", "TEXT")
        _ensure_column(conn, "call_list", "mission_id", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# ---------------------------------------------------------------------------
# Raw / capture helpers (legacy compatibility)
# ---------------------------------------------------------------------------


def insert_ingest(record: Dict[str, Any]) -> str:
    rid = record.get("id") or ("rec_" + uuid.uuid4().hex[:16])
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO ingest_records (
                id, source_type, source_url, title, raw_text, markdown,
                dom_text, script_payload, read_method, read_status,
                content_type_guess, error_reason, error, capture_meta, payload, collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                raw_text=excluded.raw_text,
                markdown=excluded.markdown,
                dom_text=excluded.dom_text,
                script_payload=excluded.script_payload,
                read_method=excluded.read_method,
                read_status=excluded.read_status,
                content_type_guess=excluded.content_type_guess,
                error_reason=excluded.error_reason,
                error=excluded.error,
                capture_meta=excluded.capture_meta,
                payload=excluded.payload
            """,
            (
                rid,
                record.get("source_type", "unknown"),
                record.get("source_url", ""),
                record.get("title", ""),
                record.get("raw_text", ""),
                record.get("markdown", ""),
                record.get("dom_text", ""),
                json.dumps(record.get("script_payload", {}), ensure_ascii=False),
                record.get("read_method") or record.get("method", ""),
                record.get("read_status", ""),
                record.get("content_type_guess", ""),
                record.get("error_reason", ""),
                record.get("error", ""),
                json.dumps(record.get("capture_meta", {}), ensure_ascii=False),
                json.dumps(record, ensure_ascii=False),
                record.get("collected_at") or datetime.datetime.utcnow().isoformat() + "Z",
            ),
        )
    return rid


def get_ingest(rid: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM ingest_records WHERE id = ?", (rid,)).fetchone()
        return dict(row) if row else None


def get_latest_jd(limit: int = 5) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM ingest_records
            WHERE source_type IN ('feishu_docx', 'feishu_wiki', 'feishu_chat', 'chatgpt_share', 'web_page', 'manual_jd')
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Read Jobs
# ---------------------------------------------------------------------------


def insert_read_job(job: Dict[str, Any]) -> str:
    jid = job.get("id") or ("rjob_" + uuid.uuid4().hex[:16])
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO read_jobs (
                id, source_type, source_url, title, status, method, raw_text, markdown,
                read_status, content_type_guess, error_reason, error, payload, capture_meta
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                status=excluded.status,
                method=excluded.method,
                raw_text=excluded.raw_text,
                markdown=excluded.markdown,
                read_status=excluded.read_status,
                content_type_guess=excluded.content_type_guess,
                error_reason=excluded.error_reason,
                error=excluded.error,
                payload=excluded.payload,
                capture_meta=excluded.capture_meta,
                updated_at=?
            """,
            (
                jid,
                job.get("source_type", "unknown"),
                job.get("source_url", ""),
                job.get("title", ""),
                job.get("status", "pending"),
                job.get("method", ""),
                job.get("raw_text", ""),
                job.get("markdown", ""),
                job.get("read_status", ""),
                job.get("content_type_guess", ""),
                job.get("error_reason", ""),
                job.get("error", ""),
                json.dumps(job.get("payload", {}), ensure_ascii=False),
                json.dumps(job.get("capture_meta", {}), ensure_ascii=False),
                now_iso(),
            ),
        )
    return jid


def update_read_job(jid: str, updates: Dict[str, Any]) -> None:
    allowed = {
        "source_url",
        "title",
        "status",
        "method",
        "raw_text",
        "markdown",
        "read_status",
        "content_type_guess",
        "error_reason",
        "error",
        "payload",
        "capture_meta",
        "completed_at",
    }
    fields = ["updated_at = ?"]
    params: List[Any] = [now_iso()]
    for k, v in updates.items():
        if k not in allowed:
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        fields.append(f"{k} = ?")
        params.append(v)
    params.append(jid)
    with get_conn() as conn:
        conn.execute(f"UPDATE read_jobs SET {', '.join(fields)} WHERE id = ?", params)


def get_read_job(jid: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM read_jobs WHERE id = ?", (jid,)).fetchone()
        return dict(row) if row else None


def get_pending_read_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM read_jobs
            WHERE status IN ('pending', 'failed')
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Normalized Artifacts
# ---------------------------------------------------------------------------


def insert_normalized_artifact(artifact: Dict[str, Any]) -> str:
    aid = artifact.get("id") or ("art_" + uuid.uuid4().hex[:16])
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO normalized_artifacts (
                id, raw_ingest_id, artifact_type, confidence, reason, normalized_payload, status, mission_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                artifact_type=excluded.artifact_type,
                confidence=excluded.confidence,
                reason=excluded.reason,
                normalized_payload=excluded.normalized_payload,
                status=excluded.status,
                mission_id=excluded.mission_id,
                updated_at=?
            """,
            (
                aid,
                artifact.get("raw_ingest_id", ""),
                artifact.get("artifact_type", "unknown"),
                artifact.get("confidence", 0.0),
                artifact.get("reason", ""),
                json.dumps(artifact.get("normalized_payload", {}), ensure_ascii=False),
                artifact.get("status", "pending"),
                artifact.get("mission_id", ""),
                now_iso(),
            ),
        )
    return aid


def update_normalized_artifact(aid: str, updates: Dict[str, Any]) -> None:
    allowed = {"artifact_type", "confidence", "reason", "normalized_payload", "status", "mission_id"}
    fields = ["updated_at = ?"]
    params: List[Any] = [now_iso()]
    for k, v in updates.items():
        if k not in allowed:
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        fields.append(f"{k} = ?")
        params.append(v)
    params.append(aid)
    with get_conn() as conn:
        conn.execute(f"UPDATE normalized_artifacts SET {', '.join(fields)} WHERE id = ?", params)


def get_normalized_artifact(aid: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM normalized_artifacts WHERE id = ?", (aid,)).fetchone()
        return dict(row) if row else None


def get_pending_normalized_artifacts(limit: int = 100) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM normalized_artifacts
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_unrouted_jd_artifacts(limit: int = 100) -> List[Dict[str, Any]]:
    """未创建 Mission 的 JD 类型 artifact。"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM normalized_artifacts
            WHERE artifact_type = 'jd'
              AND confidence >= 0.6
              AND status = 'pending'
              AND (mission_id IS NULL OR mission_id = '')
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Candidates / Call list / Feedback
# ---------------------------------------------------------------------------


def insert_candidate(candidate: Dict[str, Any]) -> str:
    cid = candidate.get("id") or ("cand_" + uuid.uuid4().hex[:16])
    now = datetime.datetime.utcnow().isoformat() + "Z"
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO candidates (id, name, phone, email, source_types, raw_profile, enriched_profile,
                                    jd_alignment_score, gold_score, risk_flags, overall_score, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                raw_profile=excluded.raw_profile,
                enriched_profile=excluded.enriched_profile,
                jd_alignment_score=excluded.jd_alignment_score,
                gold_score=excluded.gold_score,
                risk_flags=excluded.risk_flags,
                overall_score=excluded.overall_score,
                updated_at=excluded.updated_at
            """,
            (
                cid,
                candidate.get("name", ""),
                candidate.get("phone", ""),
                candidate.get("email", ""),
                json.dumps(candidate.get("source_types", []), ensure_ascii=False),
                json.dumps(candidate.get("raw_profile", {}), ensure_ascii=False),
                json.dumps(candidate.get("enriched_profile", {}), ensure_ascii=False),
                candidate.get("jd_alignment_score", 0.0),
                candidate.get("gold_score", 0.0),
                json.dumps(candidate.get("risk_flags", []), ensure_ascii=False),
                candidate.get("overall_score", 0.0),
                now,
            ),
        )
    return cid


def insert_call_list(item: Dict[str, Any]) -> str:
    lid = item.get("id") or ("call_" + uuid.uuid4().hex[:16])
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO call_list (id, candidate_id, mission_id, jd_record_id, priority, talking_points, evidence, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                mission_id=excluded.mission_id,
                priority=excluded.priority,
                talking_points=excluded.talking_points,
                evidence=excluded.evidence
            """,
            (
                lid,
                item.get("candidate_id", ""),
                item.get("mission_id", ""),
                item.get("jd_record_id", ""),
                item.get("priority", 0),
                json.dumps(item.get("talking_points", []), ensure_ascii=False),
                json.dumps(item.get("evidence", []), ensure_ascii=False),
                item.get("status", "pending"),
            ),
        )
    return lid


def get_call_list(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM call_list"
    params = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY priority DESC, created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def insert_feedback(feedback: Dict[str, Any]) -> str:
    fid = feedback.get("id") or ("fb_" + uuid.uuid4().hex[:16])
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO feedback (id, candidate_id, call_list_id, outcome, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                fid,
                feedback.get("candidate_id", ""),
                feedback.get("call_list_id", ""),
                feedback.get("outcome", ""),
                feedback.get("notes", ""),
            ),
        )
    return fid


# ---------------------------------------------------------------------------
# File persistence
# ---------------------------------------------------------------------------


def save_raw_file(record: Dict[str, Any]) -> Path:
    rid = record.get("id") or ("rec_" + uuid.uuid4().hex[:16])
    record["id"] = rid
    today = datetime.date.today().isoformat()
    folder = DATA_DIR / "ingest" / record.get("source_type", "unknown") / today
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{rid}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Mission / Human Task / Agent Run helpers
# ---------------------------------------------------------------------------


now_iso = lambda: datetime.datetime.utcnow().isoformat() + "Z"


def insert_mission(
    jd_record_id: Optional[str] = None,
    normalized_artifact_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    mid = "miss_" + uuid.uuid4().hex[:16]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO missions (
                id, jd_record_id, normalized_artifact_id, state, resume_state,
                jd_fields, candidate_ids, call_list_ids, human_task_ids, config
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mid,
                jd_record_id or "",
                normalized_artifact_id or "",
                "created",
                None,
                "{}",
                "[]",
                "[]",
                "[]",
                json.dumps(config or {}, ensure_ascii=False),
            ),
        )
    return mid


def get_mission(mid: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM missions WHERE id = ?", (mid,)).fetchone()
        if not row:
            return None
        return dict(row)


def update_mission_state(mid: str, state: str, updates: Optional[Dict[str, Any]] = None) -> None:
    updates = updates or {}
    allowed = {
        "jd_fields",
        "candidate_ids",
        "call_list_ids",
        "human_task_ids",
        "outcome",
        "closed_at",
        "resume_state",
        "normalized_artifact_id",
    }
    fields = ["state = ?, updated_at = ?"]
    params: List[Any] = [state, now_iso()]
    for k, v in updates.items():
        if k not in allowed:
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        fields.append(f"{k} = ?")
        params.append(v)
    params.append(mid)
    with get_conn() as conn:
        conn.execute(f"UPDATE missions SET {', '.join(fields)} WHERE id = ?", params)


def get_pending_missions() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM missions
            WHERE state NOT IN ('closed', 'problem_pending')
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def insert_human_task(mission_id: Optional[str], role: str, task_type: str, payload: Dict[str, Any]) -> str:
    tid = "htask_" + uuid.uuid4().hex[:16]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO human_tasks (id, mission_id, role, task_type, status, payload, html_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tid,
                mission_id,
                role,
                task_type,
                "pending",
                json.dumps(payload, ensure_ascii=False),
                f"/human/task/{tid}",
            ),
        )
    return tid


def get_human_task(tid: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM human_tasks WHERE id = ?", (tid,)).fetchone()
        return dict(row) if row else None


def list_pending_human_tasks(limit: int = 100) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM human_tasks WHERE status IN ('pending', 'notified', 'opened') ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_human_task_status(tid: str, status: str) -> None:
    extra = ""
    params = [status, now_iso(), tid]
    if status == "opened":
        extra = ", opened_at = ?"
        params = [status, now_iso(), now_iso(), tid]
    with get_conn() as conn:
        conn.execute(f"UPDATE human_tasks SET status = ?, updated_at = ?{extra} WHERE id = ?", params)


def complete_human_task(tid: str, result: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE human_tasks SET status = ?, result = ?, completed_at = ?, updated_at = ? WHERE id = ?",
            ("completed", json.dumps(result, ensure_ascii=False), now_iso(), now_iso(), tid),
        )


def insert_agent_run(mission_id: str, agent_name: str, input_data: Any, output_data: Any, decision: str = "") -> str:
    rid = "run_" + uuid.uuid4().hex[:16]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO agent_runs (id, mission_id, agent_name, input, output, decision)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rid,
                mission_id,
                agent_name,
                json.dumps(input_data, ensure_ascii=False),
                json.dumps(output_data, ensure_ascii=False),
                decision,
            ),
        )
    return rid


def get_mission_human_tasks(mid: str) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM human_tasks WHERE mission_id = ? ORDER BY created_at DESC", (mid,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_mission_agent_runs(mid: str) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_runs WHERE mission_id = ? ORDER BY created_at DESC", (mid,)
        ).fetchall()
        return [dict(r) for r in rows]
