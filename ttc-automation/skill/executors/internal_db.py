"""Internal talent database executor using talentmatch Storage."""
from __future__ import annotations

import json
import os
from typing import List

from ..models import Candidate, SearchIntent
from .base import BaseExecutor


class InternalDBExecutor(BaseExecutor):
    """Search candidates stored in the local talentmatch SQLite DB."""

    name = "internal_db"

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.getenv(
            "TALENTMATCH_DB_PATH",
            "/Users/ashley/Downloads/ttc的交易系统/ttc-automation/daemon/data/talentmatch.db",
        )

    def _storage(self):
        try:
            from storage import init_storage
            return init_storage(db_path=self.db_path)
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize talentmatch storage: {exc}") from exc

    def _row_to_candidate(self, row) -> Candidate:
        skills = []
        try:
            skills = json.loads(row["skills"] or "[]")
        except Exception:
            pass

        return Candidate(
            id=row["id"],
            name=row["name"] or "",
            source=self.name,
            source_url=row.get("source_file", ""),
            current_role=row["current_role"] or "",
            current_company=row["current_company"] or "",
            years_experience=row["years_experience"] or 0,
            location=row.get("location", "") or "",
            skills=skills,
            email=row["email"] or "",
            phone=row["phone"] or "",
            summary=row["summary"] or "",
            overall_score=float(row["ats_score"] or 0),
            raw=dict(row),
        )

    async def search(self, intent: SearchIntent, limit: int = 10) -> List[Candidate]:
        if not os.path.exists(self.db_path):
            return []

        storage = self._storage()
        conn = storage._get_conn()

        # Build a simple SQL filter: any skill keyword match OR title/company/location match
        conditions = ["1=1"]
        params = []

        if intent.skills:
            skill_likes = " OR ".join(["skills LIKE ?"] * len(intent.skills))
            conditions.append(f"({skill_likes})")
            params.extend([f"%{s}%" for s in intent.skills])

        if intent.title:
            conditions.append("(current_role LIKE ? OR summary LIKE ?)")
            params.extend([f"%{intent.title}%", f"%{intent.title}%"])

        if intent.location:
            conditions.append("(location LIKE ? OR summary LIKE ?)")
            params.extend([f"%{intent.location}%", f"%{intent.location}%"])

        if intent.min_years:
            conditions.append("years_experience >= ?")
            params.append(intent.min_years)

        sql = f"""
            SELECT * FROM candidates
            WHERE {' AND '.join(conditions)}
            ORDER BY ats_score DESC, years_experience DESC
            LIMIT ?
        """
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [self._row_to_candidate(r) for r in rows]
