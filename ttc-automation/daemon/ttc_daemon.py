"""TTC Local Daemon: central hub for the AI headhunter automation workflow.

Receives inputs from:
- TTC-Feishu Bridge userscript
- TTC-ChatGPT Reader userscript
- candidate-collector webhook / polling
- Manual API calls

Stores everything locally under data/ with full auditability.
"""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
for sub in ("feishu", "links", "resumes", "pipeline"):
    (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "ttc.db"

# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                record_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_url TEXT,
                title TEXT,
                content TEXT,
                markdown TEXT,
                collected_at TEXT,
                content_hash TEXT,
                access_basis TEXT DEFAULT 'user_authorized',
                confidence TEXT DEFAULT '中',
                extracted_fields TEXT,
                feedback TEXT,
                processed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def make_record_id(prefix: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    rand = hashlib.sha256(str(datetime.utcnow().timestamp()).encode()).hexdigest()[:6]
    return f"{prefix}_{ts}_{rand}"


def insert_record(data: dict[str, Any]) -> str:
    record_id = make_record_id(data.get("source_type", "rec"))
    content = data.get("content") or data.get("text") or ""
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    extracted = data.get("extracted_fields")
    if isinstance(extracted, dict):
        extracted = json.dumps(extracted, ensure_ascii=False)

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO records
            (record_id, source_type, source_url, title, content, markdown, collected_at,
             content_hash, access_basis, confidence, extracted_fields)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                data.get("source_type", "unknown"),
                data.get("source_url"),
                data.get("title"),
                content,
                data.get("markdown"),
                data.get("collected_at") or datetime.utcnow().isoformat() + "Z",
                content_hash,
                data.get("access_basis", "user_authorized"),
                data.get("confidence", "中"),
                extracted,
            ),
        )
        conn.commit()
    return record_id


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="TTC Daemon", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class FeishuIngest(BaseModel):
    source_type: str = "feishu_web"
    source_url: Optional[str] = None
    title: Optional[str] = None
    content: Any
    selected: bool = False
    user_agent: Optional[str] = None
    captured_at: Optional[str] = None


class LinkIngest(BaseModel):
    source_type: str
    source_url: str
    title: Optional[str] = None
    content: Any
    markdown: Optional[str] = None
    captured_at: Optional[str] = None
    access_basis: Optional[str] = "public"


class ResumeIngest(BaseModel):
    candidate_name: str
    source_url: Optional[str] = None
    resume_text: str
    file_path: Optional[str] = None
    captured_at: Optional[str] = None


class PipelineRun(BaseModel):
    record_id: Optional[str] = None
    jd_text: Optional[str] = None
    min_score: int = Field(default=50, ge=0, le=100)


class Feedback(BaseModel):
    record_id: str
    outcome: str  # contacted / interviewed / offered / hired / rejected
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.on_event("startup")
def startup():
    init_db()


@app.get("/status")
def status():
    with get_db() as conn:
        counts = {
            "total": conn.execute("SELECT COUNT(*) FROM records").fetchone()[0],
            "feishu": conn.execute(
                "SELECT COUNT(*) FROM records WHERE source_type LIKE 'feishu%'"
            ).fetchone()[0],
            "chatgpt": conn.execute(
                "SELECT COUNT(*) FROM records WHERE source_type = 'chatgpt_share'"
            ).fetchone()[0],
            "resumes": conn.execute(
                "SELECT COUNT(*) FROM records WHERE source_type = 'resume'"
            ).fetchone()[0],
        }
    return {"ok": True, "data_dir": str(DATA_DIR), "counts": counts}


@app.post("/ingest/feishu")
def ingest_feishu(payload: FeishuIngest):
    record_id = insert_record(payload.dict())
    return {"ok": True, "record_id": record_id, "message": "feishu content ingested"}


@app.post("/ingest/link")
def ingest_link(payload: LinkIngest):
    record_id = insert_record(payload.dict())
    return {"ok": True, "record_id": record_id, "message": "link content ingested"}


@app.post("/ingest/resume")
def ingest_resume(payload: ResumeIngest):
    data = {
        "source_type": "resume",
        "source_url": payload.source_url,
        "title": f"Resume: {payload.candidate_name}",
        "content": payload.resume_text,
        "markdown": payload.resume_text,
        "collected_at": payload.captured_at,
        "access_basis": "user_authorized",
    }
    record_id = insert_record(data)
    return {"ok": True, "record_id": record_id, "message": "resume ingested"}


@app.get("/records")
def list_records(
    source_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    with get_db() as conn:
        sql = "SELECT * FROM records"
        params = []
        if source_type:
            sql += " WHERE source_type = ?"
            params.append(source_type)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
    return {"ok": True, "records": [dict(r) for r in rows]}


@app.post("/link/read")
async def read_link_endpoint(url: str, use_playwright: bool = False):
    """Server-side link reader. Uses Playwright for ChatGPT share links."""
    from link_reader import read_link

    result = await read_link(url, use_playwright=use_playwright)
    record_id = insert_record(result)
    return {"ok": True, "record_id": record_id, "result": result}


@app.post("/pipeline/run")
def run_pipeline(req: PipelineRun):
    """Placeholder orchestration endpoint.

    Real implementation will:
    1. Parse JD into structured query.
    2. Query company talent DB and candidate-collector.
    3. Enrich each candidate from open web.
    4. Score and rank.
    5. Return call list.
    """
    # TODO: integrate TalentMatch / GoldScore / talent DB gateway
    return {
        "ok": True,
        "message": "pipeline stub executed",
        "record_id": req.record_id,
        "jd_snippet": (req.jd_text or "")[:200],
        "next": "integrate talent_db_gateway + scoring engine",
    }


@app.get("/api/call-list")
def call_list(limit: int = 20):
    """Placeholder call list."""
    return {
        "ok": True,
        "candidates": [],
        "message": "call-list placeholder: integrate with scoring engine",
    }


@app.post("/feedback")
def post_feedback(feedback: Feedback):
    with get_db() as conn:
        conn.execute(
            "UPDATE records SET feedback = ?, processed = 1 WHERE record_id = ?",
            (json.dumps(feedback.dict(), ensure_ascii=False), feedback.record_id),
        )
        conn.commit()
    return {"ok": True, "message": "feedback recorded"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("ttc_daemon:app", host="127.0.0.1", port=8766, reload=False)
