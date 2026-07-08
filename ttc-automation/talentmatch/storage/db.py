"""Storage layer: SQLite for business data + ChromaDB for vector search"""
from __future__ import annotations
import json
import os
import sqlite3
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger


class Storage:
    """Unified storage with SQLite + ChromaDB"""

    def __init__(self, db_path: Optional[str] = None, chroma_host: str = "",
                 chroma_port: int = 0, embedding_fn=None, disable_vector: bool = False):
        self.db_path = db_path or os.environ.get("DB_PATH", "/opt/recruit-bot-v5/data/sqlite/recruit.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self._chroma_client = None
        self._embedding_fn = embedding_fn
        self._use_server = bool(chroma_host and chroma_port)

    # ── SQLite ──────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                current_role TEXT DEFAULT '',
                current_company TEXT DEFAULT '',
                years_experience INTEGER DEFAULT 0,
                skills TEXT DEFAULT '[]',
                skills_classified TEXT DEFAULT '{}',
                education TEXT DEFAULT '[]',
                work_experience TEXT DEFAULT '[]',
                projects TEXT DEFAULT '[]',
                summary TEXT DEFAULT '',
                highlights TEXT DEFAULT '[]',
                career_stability TEXT DEFAULT '',
                tech_depth TEXT DEFAULT '',
                industry_tags TEXT DEFAULT '[]',
                role_level TEXT DEFAULT '',
                ats_score REAL DEFAULT 0.0,
                salary_current TEXT DEFAULT '',
                salary_expected TEXT DEFAULT '',
                source_file TEXT DEFAULT '',
                raw_text TEXT DEFAULT '',
                owner_id TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                company TEXT DEFAULT '',
                department TEXT DEFAULT '',
                location TEXT DEFAULT '',
                employment_type TEXT DEFAULT '',
                description TEXT DEFAULT '',
                required_skills TEXT DEFAULT '[]',
                preferred_skills TEXT DEFAULT '[]',
                min_years_experience INTEGER DEFAULT 0,
                max_years_experience INTEGER,
                education TEXT DEFAULT '',
                salary_range TEXT DEFAULT '',
                company_tier TEXT DEFAULT '',
                industry TEXT DEFAULT '',
                urgency TEXT DEFAULT '',
                priority_level TEXT DEFAULT '',
                key_selling_points TEXT DEFAULT '[]',
                hidden_requirements TEXT DEFAULT '[]',
                raw_text TEXT DEFAULT '',
                source TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                owner_id TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                overall_score REAL DEFAULT 0.0,
                skill_score REAL DEFAULT 0.0,
                experience_score REAL DEFAULT 0.0,
                education_score REAL DEFAULT 0.0,
                project_score REAL DEFAULT 0.0,
                signal_score REAL DEFAULT 0.0,
                matched_skills TEXT DEFAULT '[]',
                missing_skills TEXT DEFAULT '[]',
                strengths TEXT DEFAULT '[]',
                gaps TEXT DEFAULT '[]',
                reasoning TEXT DEFAULT '',
                recommendation TEXT DEFAULT '',
                feedback TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id),
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                feedback_type TEXT NOT NULL,
                feedback_text TEXT DEFAULT '',
                reason_tags TEXT DEFAULT '[]',
                user_id TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS interviews (
                id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL DEFAULT '',
                job_id TEXT NOT NULL DEFAULT '',
                plan TEXT DEFAULT '{}',
                questions TEXT DEFAULT '[]',
                answers TEXT DEFAULT '[]',
                scores TEXT DEFAULT '[]',
                report TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_interviews_candidate ON interviews(candidate_id);
            CREATE INDEX IF NOT EXISTS idx_interviews_job ON interviews(job_id);

            CREATE INDEX IF NOT EXISTS idx_candidates_name ON candidates(name);
            CREATE INDEX IF NOT EXISTS idx_candidates_company ON candidates(current_company);
            CREATE INDEX IF NOT EXISTS idx_jobs_title ON jobs(title);
            CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
            CREATE INDEX IF NOT EXISTS idx_matches_candidate ON matches(candidate_id);
            CREATE INDEX IF NOT EXISTS idx_matches_job ON matches(job_id);
            CREATE INDEX IF NOT EXISTS idx_matches_score ON matches(overall_score);
        """)
        conn.commit()
        # Migration: add missing columns to matches table
        for col in ["candidate_name", "job_title", "company"]:
            try:
                conn.execute(f"ALTER TABLE matches ADD COLUMN {col} TEXT DEFAULT ''")
            except Exception:
                pass
        conn.commit()
        # Migration: add reason_tags to feedback table
        try:
            conn.execute("ALTER TABLE feedback ADD COLUMN reason_tags TEXT DEFAULT '[]'")
        except Exception:
            pass
        conn.commit()

        conn.close()
        logger.info("SQLite tables initialized")

    # ── Candidates ──────────────────────────────────────

    def save_candidate(self, data: dict) -> str:
        cid = data.get("id") or str(uuid.uuid4())
        data["id"] = cid
        data["updated_at"] = datetime.now().isoformat()

        for field in ("skills", "education", "work_experience", "projects", "highlights", "industry_tags"):
            if isinstance(data.get(field), (list, dict)):
                data[field] = json.dumps(data[field], ensure_ascii=False)
        for field in ("skills_classified",):
            if isinstance(data.get(field), dict):
                data[field] = json.dumps(data[field], ensure_ascii=False)

        salary = data.pop("salary_signal", {})
        if isinstance(salary, dict):
            data.setdefault("salary_current", salary.get("current", ""))
            data.setdefault("salary_expected", salary.get("expected", ""))

        # Remove fields not in table schema
        valid_cols = {"id","name","email","phone","current_role","current_company","years_experience",
                      "skills","skills_classified","education","work_experience","projects","summary",
                      "highlights","career_stability","tech_depth","industry_tags","role_level",
                      "ats_score","salary_current","salary_expected","source_file","source","location","raw_text",
                      "owner_id","created_at","updated_at"}
        data = {k: v for k, v in data.items() if k in valid_cols}

        conn = self._get_conn()
        existing = conn.execute("SELECT id FROM candidates WHERE id=?", (cid,)).fetchone()
        if existing:
            sets = ", ".join(f"{k}=?" for k in data.keys() if k != "id")
            vals = [data[k] for k in data.keys() if k != "id"]
            conn.execute(f"UPDATE candidates SET {sets} WHERE id=?", vals + [cid])
        else:
            data.setdefault("created_at", datetime.now().isoformat())
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" for _ in data)
            conn.execute(f"INSERT INTO candidates ({cols}) VALUES ({placeholders})", list(data.values()))
        conn.commit()
        conn.close()

        self._upsert_candidate_vector(cid, data)
        return cid

    def get_candidate(self, candidate_id: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_candidates(self, limit: int = 50, offset: int = 0) -> List[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM candidates ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def search_candidates_text(self, query: str, limit: int = 10) -> List[dict]:
        conn = self._get_conn()
        like = f"%{query}%"
        rows = conn.execute(
            """SELECT * FROM candidates 
               WHERE name LIKE ? OR current_company LIKE ? OR skills LIKE ? 
               OR summary LIKE ? OR current_role LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (like, like, like, like, like, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def search_candidates_fts(self, query: str, limit: int = 10) -> List[dict]:
        """FTS5全文搜索，比LIKE更快更准"""
        try:
            conn = self._get_conn()
            # FTS5 查询，用双引号做精确短语匹配
            fts_query = ' OR '.join(f'"{w}"' for w in query.split() if w.strip())
            if not fts_query:
                return self.search_candidates_text(query, limit)
            rows = conn.execute(
                """SELECT c.* FROM candidates_fts f 
                   JOIN candidates c ON c.rowid = f.rowid
                   WHERE candidates_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (fts_query, limit)
            ).fetchall()
            conn.close()
            result = [self._row_to_dict(r) for r in rows]
            if result:
                return result
            # FTS empty (e.g. Chinese query) → fallback to LIKE
            return self.search_candidates_text(query, limit)
        except Exception as e:
            logger.warning(f"FTS search failed, fallback to text: {e}")
            return self.search_candidates_text(query, limit)

    # ── Jobs ──────────────────────────────────────

    def save_job(self, data: dict) -> str:
        jid = data.get("id") or str(uuid.uuid4())
        data["id"] = jid
        data["updated_at"] = datetime.now().isoformat()

        for field in ("required_skills", "preferred_skills", "key_selling_points", "hidden_requirements"):
            if isinstance(data.get(field), (list, dict)):
                data[field] = json.dumps(data[field], ensure_ascii=False)

        valid_cols = {"id","title","company","department","location","employment_type",
                      "description","required_skills","preferred_skills","min_years_experience",
                      "max_years_experience","education","salary_range","company_tier","industry",
                      "urgency","priority_level","key_selling_points","hidden_requirements",
                      "raw_text","source","status","owner_id","created_at","updated_at"}
        data = {k: v for k, v in data.items() if k in valid_cols}

        conn = self._get_conn()
        existing = conn.execute("SELECT id FROM jobs WHERE id=?", (jid,)).fetchone()
        if existing:
            sets = ", ".join(f"{k}=?" for k in data.keys() if k != "id")
            vals = [data[k] for k in data.keys() if k != "id"]
            conn.execute(f"UPDATE jobs SET {sets} WHERE id=?", vals + [jid])
        else:
            data.setdefault("created_at", datetime.now().isoformat())
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" for _ in data)
            conn.execute(f"INSERT INTO jobs ({cols}) VALUES ({placeholders})", list(data.values()))
        conn.commit()
        conn.close()

        self._upsert_job_vector(jid, data)
        return jid

    def get_job(self, job_id: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_jobs(self, status: str = "active", limit: int = 50, offset: int = 0) -> List[dict]:
        conn = self._get_conn()
        if status == "all":
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset)
            ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def search_jobs_text(self, query: str, limit: int = 10) -> List[dict]:
        conn = self._get_conn()
        like = f"%{query}%"
        rows = conn.execute(
            """SELECT * FROM jobs 
               WHERE title LIKE ? OR company LIKE ? OR description LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (like, like, like, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    # ── Matches ──────────────────────────────────────

    def save_match(self, data: dict) -> str:
        mid = data.get("id") or str(uuid.uuid4())
        data["id"] = mid
        for field in ("matched_skills", "missing_skills", "strengths", "gaps"):
            if isinstance(data.get(field), (list, dict)):
                data[field] = json.dumps(data[field], ensure_ascii=False)
        conn = self._get_conn()
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        conn.execute(f"INSERT OR REPLACE INTO matches ({cols}) VALUES ({placeholders})", list(data.values()))
        conn.commit()
        conn.close()
        return mid

    def get_job_matches(self, job_id: str, limit: int = 20) -> List[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM matches WHERE job_id=? ORDER BY overall_score DESC LIMIT ?",
            (job_id, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def get_candidate_matches(self, candidate_id: str) -> List[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM matches WHERE candidate_id=? ORDER BY overall_score DESC",
            (candidate_id,)
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    # ── Feedback ──────────────────────────────────────

    def save_feedback(self, entity_type: str, entity_id: str, feedback_type: str,
                      feedback_text: str = "", user_id: str = "",
                      reason_tags: list | None = None) -> str:
        fid = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO feedback (id, entity_type, entity_id, feedback_type, feedback_text, user_id, reason_tags) VALUES (?,?,?,?,?,?,?)",
                (fid, entity_type, entity_id, feedback_type, feedback_text, user_id,
                 json.dumps(reason_tags or [], ensure_ascii=False))
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return fid

    # ── Stats ──────────────────────────────────────

    def get_stats(self) -> dict:
        conn = self._get_conn()
        candidates = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='active'").fetchone()[0]
        matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        feedback_count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        conn.close()
        return {
            "candidates": candidates,
            "active_jobs": jobs,
            "matches": matches,
            "feedback": feedback_count,
        }

    # ── CRUD Operations (v6 enhancement) ──────────────────────────────────────

    def update_candidate(self, candidate_id: str, data: dict) -> bool:
        """Update candidate fields"""
        allowed = {"name","email","phone","current_role","current_company","years_experience",
                    "skills","education","work_experience","projects","summary","highlights",
                    "career_stability","tech_depth","industry_tags","role_level","ats_score",
                    "salary_current","salary_expected","owner_id"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return False
        conn = self._get_conn()
        for k, v in updates.items():
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            conn.execute(f"UPDATE candidates SET {k}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (v, candidate_id))
        conn.commit()
        conn.close()
        return True

    def update_job(self, job_id: str, data: dict) -> bool:
        """Update job fields"""
        allowed = {"title","company","department","location","employment_type","description",
                    "required_skills","preferred_skills","min_years_experience","max_years_experience",
                    "education","salary_range","company_tier","industry","urgency",
                    "priority_level","key_selling_points","hidden_requirements","status"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return False
        conn = self._get_conn()
        for k, v in updates.items():
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            conn.execute(f"UPDATE jobs SET {k}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (v, job_id))
        conn.commit()
        conn.close()
        return True

    def delete_candidate(self, candidate_id: str) -> bool:
        """Delete candidate and cascaded matches"""
        conn = self._get_conn()
        conn.execute("DELETE FROM matches WHERE candidate_id=?", (candidate_id,))
        conn.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))
        conn.commit()
        conn.close()
        try:
            client = self._get_chroma()
            collection = client.get_or_create_collection("candidates")
            collection.delete(ids=[candidate_id])
        except Exception:
            pass
        return True

    def delete_job(self, job_id: str) -> bool:
        """Delete job and its matches"""
        conn = self._get_conn()
        conn.execute("DELETE FROM matches WHERE job_id=?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        conn.commit()
        conn.close()
        try:
            client = self._get_chroma()
            collection = client.get_or_create_collection("jobs")
            collection.delete(ids=[job_id])
        except Exception:
            pass
        return True

    # ── Interview Plans (v6) ──────────────────────────────────────

    def save_interview_plan(self, data: dict) -> str:
        """Save interview plan"""
        pid = data.get("id") or str(uuid.uuid4())
        data["id"] = pid
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO interviews (id, candidate_id, job_id, plan, questions, answers, scores, report, status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (pid, data.get("candidate_id", ""), data.get("job_id", ""),
             json.dumps(data.get("plan", {}), ensure_ascii=False),
             json.dumps(data.get("questions", []), ensure_ascii=False),
             json.dumps(data.get("answers", []), ensure_ascii=False),
             json.dumps(data.get("scores", []), ensure_ascii=False),
             data.get("report", ""),
             data.get("status", "pending"))
        )
        conn.commit()
        conn.close()
        return pid

    def get_interview_plan(self, interview_id: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM interviews WHERE id=?", (interview_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def list_interview_plans(self, candidate_id: str = "", limit: int = 20) -> List[dict]:
        conn = self._get_conn()
        if candidate_id:
            rows = conn.execute(
                "SELECT * FROM interviews WHERE candidate_id=? ORDER BY created_at DESC LIMIT ?",
                (candidate_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM interviews ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Unified Search (v6) ──────────────────────────────────────

    def search_all(self, query: str, limit: int = 10) -> dict:
        """Unified search across candidates, jobs, and matches"""
        candidates = self.search_candidates_vector(query, limit)
        jobs = self.search_jobs_vector(query, limit)
        conn = self._get_conn()
        like = f"%{query}%"
        match_rows = conn.execute(
            """SELECT m.*, c.name as cname, j.title as jtitle
               FROM matches m
               LEFT JOIN candidates c ON m.candidate_id = c.id
               LEFT JOIN jobs j ON m.job_id = j.id
               WHERE c.name LIKE ? OR j.title LIKE ? OR m.recommendation LIKE ?
               ORDER BY m.overall_score DESC LIMIT ?""",
            (like, like, like, limit)
        ).fetchall()
        conn.close()
        return {
            "candidates": candidates,
            "jobs": jobs,
            "matches": [dict(r) for r in match_rows],
            "query": query,
            "total": len(candidates) + len(jobs) + len(match_rows),
        }

    def batch_save_candidates(self, candidates: List[dict]) -> List[str]:
        """Batch save multiple candidates"""
        ids = []
        for c in candidates:
            cid = self.save_candidate(c)
            ids.append(cid)
        return ids

    def batch_save_jobs(self, jobs: List[dict]) -> List[str]:
        """Batch save multiple jobs"""
        ids = []
        for j in jobs:
            jid = self.save_job(j)
            ids.append(jid)
        return ids

    def get_recent_matches(self, days: int = 7, limit: int = 50) -> List[dict]:
        """Get matches from recent N days"""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT m.*, c.name as cname, j.title as jtitle
               FROM matches m
               LEFT JOIN candidates c ON m.candidate_id = c.id
               LEFT JOIN jobs j ON m.job_id = j.id
               WHERE m.created_at >= datetime('now', ?)
               ORDER BY m.overall_score DESC LIMIT ?""",
            (f'-{days} days', limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_candidates_by_owner(self, owner_id: str, limit: int = 50) -> List[dict]:
        """Get candidates by owner/hunter"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM candidates WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
            (owner_id, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def get_jobs_by_owner(self, owner_id: str, limit: int = 50) -> List[dict]:
        """Get jobs by owner/hunter"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM jobs WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
            (owner_id, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def get_duplicate_candidates(self, email: str = "", name: str = "") -> List[dict]:
        """Detect potential duplicate candidates by email or name"""
        conn = self._get_conn()
        if email:
            rows = conn.execute("SELECT * FROM candidates WHERE email=? ORDER BY created_at DESC", (email,)).fetchall()
        elif name:
            rows = conn.execute("SELECT * FROM candidates WHERE name=? ORDER BY created_at DESC", (name,)).fetchall()
        else:
            rows = []
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    # ── Vector search (embedded ChromaDB) ──────────────────────────────────────

    def _get_chroma(self):
        if self._chroma_client is None:
            try:
                import chromadb
                if self._use_server:
                    self._chroma_client = chromadb.HttpClient(
                        host=self.chroma_host, port=self.chroma_port
                    )
                    logger.info(f"ChromaDB server mode: {self.chroma_host}:{self.chroma_port}")
                else:
                    # Embedded mode - persistent local storage
                    persist_dir = os.environ.get("CHROMA_PERSIST_DIR", 
                        os.path.join(os.path.dirname(self.db_path), "..", "chromadb"))
                    os.makedirs(persist_dir, exist_ok=True)
                    self._chroma_client = chromadb.PersistentClient(path=persist_dir)
                    logger.info(f"ChromaDB embedded mode: {persist_dir}")
            except Exception as e:
                logger.warning(f"ChromaDB init failed: {e}, using in-memory")
                import chromadb
                self._chroma_client = chromadb.Client()
        return self._chroma_client

    def _upsert_candidate_vector(self, cid: str, data: dict):
        try:
            client = self._get_chroma()
            collection = client.get_or_create_collection("candidates")
            name = data.get("name", "")
            role = data.get("current_role", "")
            company = data.get("current_company", "")
            skills = data.get("skills", "")
            summary = data.get("summary", "")
            text = f"{name} {role} {company} {skills} {summary}"
            if isinstance(text, str) and len(text.strip()) > 5:
                collection.upsert(
                    ids=[cid],
                    documents=[text],
                    metadatas=[{"name": name, "role": role}]
                )
        except Exception as e:
            logger.warning(f"ChromaDB upsert candidate failed: {e}")

    def _upsert_job_vector(self, jid: str, data: dict):
        try:
            client = self._get_chroma()
            collection = client.get_or_create_collection("jobs")
            title = data.get("title", "")
            company = data.get("company", "")
            skills = data.get("required_skills", "")
            desc = data.get("description", "")
            text = f"{title} {company} {skills} {desc}"
            if isinstance(text, str) and len(text.strip()) > 5:
                collection.upsert(
                    ids=[jid],
                    documents=[text],
                    metadatas=[{"title": title, "company": company}]
                )
        except Exception as e:
            logger.warning(f"ChromaDB upsert job failed: {e}")

    def search_candidates_vector(self, query: str, limit: int = 10) -> List[dict]:
        try:
            client = self._get_chroma()
            collection = client.get_or_create_collection("candidates")
            # Check if collection has data
            count = collection.count()
            if count == 0:
                logger.info("ChromaDB candidates collection empty, using text search")
                return self.search_candidates_text(query, limit)
            results = collection.query(query_texts=[query], n_results=min(limit, count))
            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]
            candidates = []
            for cid, dist in zip(ids, distances):
                c = self.get_candidate(cid)
                if c:
                    c["_relevance"] = round(1 - dist, 3)
                    candidates.append(c)
            return candidates
        except Exception as e:
            logger.warning(f"Vector search failed, falling back to text: {e}")
            return self.search_candidates_text(query, limit)

    def search_jobs_vector(self, query: str, limit: int = 10) -> List[dict]:
        try:
            client = self._get_chroma()
            collection = client.get_or_create_collection("jobs")
            count = collection.count()
            if count == 0:
                return self.search_jobs_text(query, limit)
            results = collection.query(query_texts=[query], n_results=min(limit, count))
            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]
            jobs = []
            for jid, dist in zip(ids, distances):
                j = self.get_job(jid)
                if j:
                    j["_relevance"] = round(1 - dist, 3)
                    jobs.append(j)
            return jobs
        except Exception as e:
            logger.warning(f"Job vector search failed: {e}")
            return self.search_jobs_text(query, limit)

    # ── Helpers ──────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        for key, val in d.items():
            if isinstance(val, str) and val.startswith(("[", "{")):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    pass
        return d
