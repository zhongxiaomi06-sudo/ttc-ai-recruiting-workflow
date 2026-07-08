"""Candidate API routes"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from storage import get_storage

router = APIRouter(tags=["candidates"])


class CandidateImport(BaseModel):
    name: str = ""
    current_role: str = ""
    current_company: str = ""
    years_experience: int = 0
    skills: str = "[]"
    education: str = "[]"
    source: str = "plugin"
    phone: str = ""
    email: str = ""
    location: str = ""
    raw: Optional[dict] = None


class CandidateUpdate(BaseModel):
    tags: Optional[List[str]] = None
    uploaded_by: Optional[str] = None
    birthday: Optional[str] = None
    location: Optional[str] = None
    role_type: Optional[str] = None


@router.post("/candidates")
async def create_candidate(candidate: CandidateImport):
    import json
    storage = get_storage()
    try:
        cid = storage.save_candidate({
            "name": candidate.name,
            "current_role": candidate.current_role,
            "current_company": candidate.current_company,
            "years_experience": candidate.years_experience,
            "skills": json.loads(candidate.skills) if isinstance(candidate.skills, str) else candidate.skills,
            "education": json.loads(candidate.education) if isinstance(candidate.education, str) else candidate.education,
            "source": candidate.source,
            "phone": candidate.phone,
            "email": candidate.email,
            "location": candidate.location,
        })
        return {"status": "ok", "candidate_id": cid}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/candidates")
async def list_candidates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    q: Optional[str] = None,
    role_type: Optional[str] = None,
    sort_by: str = "ats_score",
):
    """候选人列表，支持搜索+工种筛选+服务端分页"""
    storage = get_storage()
    conn = storage._get_conn()

    where = []
    params = []

    if q and q.strip():
        where.append("(name LIKE ? OR current_role LIKE ? OR skills LIKE ? OR current_company LIKE ? OR raw_text LIKE ? OR education LIKE ? OR work_experience LIKE ?)")
        like = f"%{q.strip()}%"
        params.extend([like, like, like, like, like, like, like])

    if role_type:
        where.append("role_type = ?")
        params.append(role_type)

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    # Sort
    sort_cols = {"ats_score": "ats_score DESC", "years_experience": "years_experience DESC", "name": "name ASC"}
    order = sort_cols.get(sort_by, "ats_score DESC")

    # Count total
    count_sql = f"SELECT COUNT(*) FROM candidates {where_clause}"
    total = conn.execute(count_sql, params).fetchone()[0]

    # Page
    offset = (page - 1) * page_size
    query_sql = f"SELECT * FROM candidates {where_clause} ORDER BY {order} LIMIT ? OFFSET ?"
    rows = conn.execute(query_sql, params + [page_size, offset]).fetchall()
    conn.close()

    return {
        "items": [storage._row_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/candidates/stats")
async def get_candidate_stats():
    storage = get_storage()
    conn = storage._get_conn()
    total = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    excellent = conn.execute("SELECT COUNT(*) FROM candidates WHERE ats_score >= 80").fetchone()[0]
    good = conn.execute("SELECT COUNT(*) FROM candidates WHERE ats_score >= 60 AND ats_score < 80").fetchone()[0]
    avg_row = conn.execute("SELECT AVG(ats_score) FROM candidates WHERE ats_score IS NOT NULL").fetchone()
    avg = round(avg_row[0], 1) if avg_row[0] else 0
    conn.close()
    return {"total": total, "total_candidates": total, "excellent": excellent, "good": good, "avg_score": avg}


@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str):
    c = get_storage().get_candidate(candidate_id)
    if not c:
        raise HTTPException(404, "Candidate not found")
    return c


@router.get("/candidates/search/{query}")
async def search_candidates(query: str, limit: int = 10):
    results = get_storage().search_candidates(query, limit)
    return {"items": results, "total": len(results)}


@router.put("/candidates/{candidate_id}")
async def update_candidate(candidate_id: str, update: CandidateUpdate):
    storage = get_storage()
    conn = storage._get_conn()

    sets = []
    vals = []
    update_dict = update.model_dump(exclude_none=True)

    if "tags" in update_dict:
        import json
        update_dict["tags"] = json.dumps(update_dict["tags"], ensure_ascii=False)

    for k, v in update_dict.items():
        sets.append(f"{k} = ?")
        vals.append(v)

    if not sets:
        raise HTTPException(400, "No fields to update")

    vals.append(candidate_id)
    conn.execute(f"UPDATE candidates SET {', '.join(sets)}, updated_at = datetime('now') WHERE id = ?", vals)
    conn.commit()

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, "Candidate not found")
    return storage._row_to_dict(row)


@router.delete("/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str):
    ok = get_storage().delete_candidate(candidate_id)
    if not ok:
        raise HTTPException(404, "Candidate not found")
    return {"status": "ok"}


@router.post("/candidates/batch-classify")
async def batch_classify_candidates():
    from matching.role_classifier import classify_role
    import json

    storage = get_storage()
    conn = storage._get_conn()

    rows = conn.execute(
        "SELECT id, current_role, skills FROM candidates WHERE role_type IS NULL OR role_type = ''"
    ).fetchall()

    updated = 0
    for row in rows:
        cid, role, skills_raw = row
        skills = []
        if skills_raw:
            try:
                skills = json.loads(skills_raw) if isinstance(skills_raw, str) else skills_raw
            except (json.JSONDecodeError, TypeError):
                pass
        rt = classify_role(current_role=role or "", skills=skills or [])
        if rt:
            conn.execute("UPDATE candidates SET role_type = ?, updated_at = datetime('now') WHERE id = ?", (rt, cid))
            updated += 1

    conn.commit()
    conn.close()
    return {"status": "ok", "total_scanned": len(rows), "updated": updated}
