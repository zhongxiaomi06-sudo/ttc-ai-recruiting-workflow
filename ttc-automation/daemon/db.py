"""SQLite persistence for TTC Orchestrator, Missions, Human Tasks and Agent Runs."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ttc.db"

_local = threading.local()


def _conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db() -> None:
    conn = _conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS read_jobs (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_url TEXT,
            title TEXT,
            content TEXT,
            markdown TEXT,
            read_status TEXT DEFAULT 'pending',
            content_type_guess TEXT,
            error_reason TEXT,
            read_method TEXT,
            confidence TEXT DEFAULT '中',
            extracted_fields TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            read_job_id TEXT,
            artifact_type TEXT,
            title TEXT,
            content TEXT,
            markdown TEXT,
            confidence TEXT DEFAULT '中',
            extracted_fields TEXT,
            normalized_data TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (read_job_id) REFERENCES read_jobs(id)
        );

        CREATE TABLE IF NOT EXISTS missions (
            id TEXT PRIMARY KEY,
            artifact_id TEXT,
            status TEXT DEFAULT 'created',
            jd_struct TEXT,
            candidates_json TEXT,
            scores_json TEXT,
            call_list_json TEXT,
            feedback_json TEXT,
            problem_reason TEXT,
            resume_state TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
        );

        CREATE TABLE IF NOT EXISTS human_tasks (
            id TEXT PRIMARY KEY,
            mission_id TEXT,
            task_type TEXT,
            status TEXT DEFAULT 'created',
            payload_json TEXT,
            result_json TEXT,
            assignee TEXT,
            html_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (mission_id) REFERENCES missions(id)
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
            id TEXT PRIMARY KEY,
            mission_id TEXT,
            agent_name TEXT,
            input_json TEXT,
            output_json TEXT,
            status TEXT,
            error TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (mission_id) REFERENCES missions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
        CREATE INDEX IF NOT EXISTS idx_human_tasks_status ON human_tasks(status);
        CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(artifact_type);
        """
    )
    conn.commit()


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _to_json(obj: Any) -> Optional[str]:
    return json.dumps(obj, ensure_ascii=False) if obj is not None else None


def _from_json(s: Optional[str]) -> Any:
    return json.loads(s) if s else None


def insert_read_job(data: dict[str, Any]) -> str:
    import uuid

    rid = f"rj_{uuid.uuid4().hex[:12]}"
    conn = _conn()
    conn.execute(
        """
        INSERT INTO read_jobs
        (id, source_type, source_url, title, content, markdown, read_status,
         read_method, confidence, extracted_fields, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rid,
            data.get("source_type", "unknown"),
            data.get("source_url"),
            data.get("title"),
            data.get("content") if isinstance(data.get("content"), str) else _to_json(data.get("content")),
            data.get("markdown"),
            data.get("read_status", "pending"),
            data.get("read_method"),
            data.get("confidence", "中"),
            _to_json(data.get("extracted_fields")),
            now_iso(),
        ),
    )
    conn.commit()
    return rid


def update_read_job(rid: str, updates: dict[str, Any]) -> None:
    allowed = {"read_status", "content_type_guess", "error_reason", "read_method",
               "confidence", "extracted_fields", "content", "markdown", "title"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = now_iso()
    conn = _conn()
    conn.execute(
        f"UPDATE read_jobs SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?",
        list(fields.values()) + [rid],
    )
    conn.commit()


def get_read_job(rid: str) -> Optional[dict]:
    row = _conn().execute("SELECT * FROM read_jobs WHERE id=?", (rid,)).fetchone()
    return dict(row) if row else None


def insert_artifact(data: dict[str, Any]) -> str:
    import uuid

    aid = f"art_{uuid.uuid4().hex[:12]}"
    conn = _conn()
    conn.execute(
        """
        INSERT INTO artifacts
        (id, read_job_id, artifact_type, title, content, markdown, confidence,
         extracted_fields, normalized_data, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            aid,
            data.get("read_job_id"),
            data.get("artifact_type", "unknown"),
            data.get("title"),
            data.get("content") if isinstance(data.get("content"), str) else _to_json(data.get("content")),
            data.get("markdown"),
            data.get("confidence", "中"),
            _to_json(data.get("extracted_fields")),
            _to_json(data.get("normalized_data")),
            data.get("status", "pending"),
            now_iso(),
        ),
    )
    conn.commit()
    return aid


def update_artifact(aid: str, updates: dict[str, Any]) -> None:
    allowed = {"artifact_type", "title", "content", "markdown", "confidence",
               "extracted_fields", "normalized_data", "status"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = now_iso()
    conn = _conn()
    conn.execute(
        f"UPDATE artifacts SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?",
        list(fields.values()) + [aid],
    )
    conn.commit()


def get_artifact(aid: str) -> Optional[dict]:
    row = _conn().execute("SELECT * FROM artifacts WHERE id=?", (aid,)).fetchone()
    return dict(row) if row else None


def list_artifacts(artifact_type: Optional[str] = None, status: Optional[str] = None, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM artifacts WHERE 1=1"
    params = []
    if artifact_type:
        sql += " AND artifact_type=?"
        params.append(artifact_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = _conn().execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def insert_mission(artifact_id: str, jd_struct: Optional[dict] = None) -> str:
    import uuid

    mid = f"mission_{uuid.uuid4().hex[:12]}"
    _conn().execute(
        """
        INSERT INTO missions (id, artifact_id, status, jd_struct, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (mid, artifact_id, "created", _to_json(jd_struct), now_iso()),
    )
    _conn().commit()
    return mid


def get_mission(mid: str) -> Optional[dict]:
    row = _conn().execute("SELECT * FROM missions WHERE id=?", (mid,)).fetchone()
    return dict(row) if row else None


def update_mission(mid: str, updates: dict[str, Any]) -> None:
    allowed = {"status", "jd_struct", "candidates_json", "scores_json",
               "call_list_json", "feedback_json", "problem_reason", "resume_state"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return
    fields["updated_at"] = now_iso()
    conn = _conn()
    conn.execute(
        f"UPDATE missions SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?",
        list(fields.values()) + [mid],
    )
    conn.commit()


def list_missions(status: Optional[str] = None, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM missions WHERE 1=1"
    params = []
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    rows = _conn().execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def insert_human_task(mission_id: str, task_type: str, payload: dict[str, Any],
                      assignee: Optional[str] = None, html_url: Optional[str] = None) -> str:
    import uuid

    tid = f"task_{uuid.uuid4().hex[:12]}"
    _conn().execute(
        """
        INSERT INTO human_tasks (id, mission_id, task_type, status, payload_json, assignee, html_url, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tid, mission_id, task_type, "created", _to_json(payload), assignee, html_url, now_iso()),
    )
    _conn().commit()
    return tid


def get_human_task(tid: str) -> Optional[dict]:
    row = _conn().execute("SELECT * FROM human_tasks WHERE id=?", (tid,)).fetchone()
    return dict(row) if row else None


def update_human_task(tid: str, updates: dict[str, Any]) -> None:
    allowed = {"status", "result_json", "assignee", "completed_at", "html_url"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return
    conn = _conn()
    conn.execute(
        f"UPDATE human_tasks SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?",
        list(fields.values()) + [tid],
    )
    conn.commit()


def list_human_tasks(status: Optional[str] = None, mission_id: Optional[str] = None, limit: int = 200) -> list[dict]:
    sql = "SELECT * FROM human_tasks WHERE 1=1"
    params = []
    if status:
        sql += " AND status=?"
        params.append(status)
    if mission_id:
        sql += " AND mission_id=?"
        params.append(mission_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = _conn().execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def insert_agent_run(mission_id: str, agent_name: str, input_data: Any, output_data: Any,
                     status: str, error: Optional[str] = None) -> None:
    import uuid

    _conn().execute(
        """
        INSERT INTO agent_runs (id, mission_id, agent_name, input_json, output_json, status, error, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (f"run_{uuid.uuid4().hex[:12]}", mission_id, agent_name, _to_json(input_data),
         _to_json(output_data), status, error, now_iso()),
    )
    _conn().commit()


def list_agent_runs(mission_id: Optional[str] = None, limit: int = 200) -> list[dict]:
    sql = "SELECT * FROM agent_runs WHERE 1=1"
    params = []
    if mission_id:
        sql += " AND mission_id=?"
        params.append(mission_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = _conn().execute(sql, params).fetchall()
    return [dict(r) for r in rows]
