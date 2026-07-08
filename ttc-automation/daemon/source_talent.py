"""Source company talent data adapter.

Supports three backends:
1. MySQL/RDS (e.g., Source 公司人才库)
2. Local JSON file
3. REST API

Configuration via environment variables.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

import requests


def _local_requests() -> requests.Session:
    """Create a requests session that bypasses environment proxies for local calls."""
    s = requests.Session()
    s.trust_env = False
    return s


def _expand_search_terms(jd_struct: dict) -> list[str]:
    """Expand JD position into broader search terms for source talent DB."""
    position = (jd_struct.get("position") or "").strip()
    terms = [position]
    lower = position.lower()

    # Non-technical roles
    if "总裁助理" in position or "董事长助理" in position or "ceo助理" in lower:
        terms.extend(["总裁助理", "董事长助理", "CEO助理", "高管助理", "秘书", "行政"])
    if "秘书" in position:
        terms.extend(["秘书", "行政", "总裁助理", "高管助理"])

    # Technical roles
    if "后端" in position or "back" in lower:
        terms.extend(["后端工程师", "后端开发", "Server"])
    if "前端" in position or "front" in lower:
        terms.extend(["前端工程师", "前端开发"])
    if "算法" in position or "algorithm" in lower:
        terms.extend(["算法工程师", "机器学习", "AI工程师"])

    return list(dict.fromkeys(t for t in terms if t))


def enabled() -> bool:
    return (
        os.getenv("TTC_SOURCE_TALENT_ENABLED", "").lower() == "true"
        or bool(os.getenv("TTC_MYSQL_HOST"))
        or bool(os.getenv("TTC_SOURCE_TALENT_FILE"))
        or bool(os.getenv("TTC_SOURCE_TALENT_URL"))
    )


def status() -> dict[str, Any]:
    """Return source talent configuration status and sample count."""
    result = {
        "enabled": enabled(),
        "mysql": bool(os.getenv("TTC_MYSQL_HOST")),
        "json_file": bool(os.getenv("TTC_SOURCE_TALENT_FILE")),
        "api": bool(os.getenv("TTC_SOURCE_TALENT_URL")),
        "sample_count": 0,
        "error": None,
    }
    if not result["enabled"]:
        return result

    try:
        candidates = _query_mysql("SELECT 1", limit=1) if result["mysql"] else []
        if candidates:
            result["sample_count"] = len(candidates)
        elif result["json_file"]:
            path = Path(os.getenv("TTC_SOURCE_TALENT_FILE"))
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                result["sample_count"] = len(data) if isinstance(data, list) else len(data.get("candidates", []))
    except Exception as exc:
        result["error"] = str(exc)
    return result


def search(jd_struct: dict, limit: int = 50) -> list[dict]:
    """Search source talent by expanded position terms and skills."""
    if not enabled():
        return []

    terms = _expand_search_terms(jd_struct)
    skills = jd_struct.get("skills") or []

    if os.getenv("TTC_MYSQL_HOST"):
        return _search_mysql(terms, skills, limit)
    if os.getenv("TTC_SOURCE_TALENT_FILE"):
        return _search_json_file(terms, skills, limit)
    if os.getenv("TTC_SOURCE_TALENT_URL"):
        return _search_api(terms, skills, limit)
    return []


def _search_mysql(terms: list[str], skills: list[str], limit: int) -> list[dict]:
    import pymysql

    host = os.getenv("TTC_MYSQL_HOST")
    port = int(os.getenv("TTC_MYSQL_PORT", "3306"))
    database = os.getenv("TTC_MYSQL_DATABASE")
    user = os.getenv("TTC_MYSQL_USER")
    password = os.getenv("TTC_MYSQL_PASSWORD")
    table = os.getenv("TTC_MYSQL_TABLE", "candidates")
    name_col = os.getenv("TTC_MYSQL_NAME_COL", "name")
    text_col = os.getenv("TTC_MYSQL_TEXT_COL", "resume_text")

    if not all([host, database, user, password]):
        return []

    # Build a simple LIKE query across terms
    like_clauses = " OR ".join([f"{text_col} LIKE %s" for _ in terms])
    params = [f"%{t}%" for t in terms]
    sql = f"SELECT {name_col}, {text_col} FROM {table} WHERE {like_clauses} LIMIT %s"
    params.append(limit)

    conn = None
    try:
        conn = pymysql.connect(host=host, port=port, database=database,
                               user=user, password=password, charset="utf8mb4")
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [{"name": r[0], "resume_text": r[1], "source": "source_mysql"} for r in rows]
    finally:
        if conn:
            conn.close()


def _query_mysql(sql: str, limit: int = 1) -> list[dict]:
    import pymysql

    host = os.getenv("TTC_MYSQL_HOST")
    port = int(os.getenv("TTC_MYSQL_PORT", "3306"))
    database = os.getenv("TTC_MYSQL_DATABASE")
    user = os.getenv("TTC_MYSQL_USER")
    password = os.getenv("TTC_MYSQL_PASSWORD")
    table = os.getenv("TTC_MYSQL_TABLE", "candidates")
    name_col = os.getenv("TTC_MYSQL_NAME_COL", "name")
    text_col = os.getenv("TTC_MYSQL_TEXT_COL", "resume_text")

    if not all([host, database, user, password]):
        return []

    conn = None
    try:
        conn = pymysql.connect(host=host, port=port, database=database,
                               user=user, password=password, charset="utf8mb4")
        with conn.cursor() as cur:
            cur.execute(f"SELECT {name_col}, {text_col} FROM {table} LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [{"name": r[0], "resume_text": r[1]} for r in rows]
    finally:
        if conn:
            conn.close()


def _search_json_file(terms: list[str], skills: list[str], limit: int) -> list[dict]:
    path = Path(os.getenv("TTC_SOURCE_TALENT_FILE"))
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates = data if isinstance(data, list) else data.get("candidates", [])
    results = []
    for c in candidates[:limit * 3]:
        text = json.dumps(c, ensure_ascii=False)
        if any(t.lower() in text.lower() for t in terms) or any(s.lower() in text.lower() for s in skills):
            c["source"] = "source_json"
            results.append(c)
        if len(results) >= limit:
            break
    return results


def _search_api(terms: list[str], skills: list[str], limit: int) -> list[dict]:
    url = os.getenv("TTC_SOURCE_TALENT_URL")
    key = os.getenv("TTC_SOURCE_TALENT_KEY")
    path = os.getenv("TTC_SOURCE_TALENT_QUERY_PATH", "/api/candidates/search")
    if not url:
        return []
    try:
        headers = {}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        s = _local_requests()
        r = s.post(f"{url.rstrip('/')}/{path.lstrip('/')}", headers=headers,
                   json={"terms": terms, "skills": skills, "limit": limit}, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("candidates", [])
    except Exception as exc:
        print(f"[source_talent] API error: {exc}")
        return []
