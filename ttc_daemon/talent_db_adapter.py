import logging
from typing import List, Dict, Any
import json
from pathlib import Path
import requests
from .config import TALENT_DB_CONFIG, SOURCE_TALENT_CONFIG

logger = logging.getLogger(__name__)


def query_talent_db(jd_fields: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
    """公司人才库查询适配器。用户需根据实际接口文档实现。"""
    if not TALENT_DB_CONFIG.get("enabled") or not TALENT_DB_CONFIG.get("base_url"):
        logger.info("Talent DB not enabled or not configured; returning empty list")
        return []

    url = TALENT_DB_CONFIG["base_url"].rstrip("/") + TALENT_DB_CONFIG["query_path"]
    headers = {}
    if TALENT_DB_CONFIG.get("api_key"):
        headers["Authorization"] = f"Bearer {TALENT_DB_CONFIG['api_key']}"

    payload = {
        "keywords": jd_fields.get("skills", []),
        "location": jd_fields.get("location", ""),
        "position": jd_fields.get("position", ""),
        "experience_years": jd_fields.get("experience_years", ""),
        "limit": limit,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # 假设返回 { "candidates": [...] } 或 [...]
        if isinstance(data, dict) and "candidates" in data:
            return data["candidates"]
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Talent DB query failed: {e}")
        return []


def query_source_company_db(jd_fields: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
    """Source 公司人才库适配器。

    支持两种成熟接入方式：
    1. MySQL：配置 TTC_MYSQL_* 或 TTC_SOURCE_TALENT_MYSQL_*。
    2. API：配置 TTC_SOURCE_TALENT_URL / KEY / QUERY_PATH。
    3. 本地导出：配置 TTC_SOURCE_TALENT_FILE 指向 JSON 文件，格式为 candidates 数组或 {"candidates": [...]}。
    """
    if not SOURCE_TALENT_CONFIG.get("enabled"):
        return []

    candidates: List[Dict[str, Any]] = []
    candidates.extend(_query_source_mysql(jd_fields, limit))
    if len(candidates) >= limit:
        return candidates[:limit]

    candidates.extend(_query_source_file(jd_fields, limit))
    remaining = max(limit - len(candidates), 0)
    if remaining:
        candidates.extend(_query_source_api(jd_fields, remaining))
    return candidates[:limit]


def _query_source_mysql(jd_fields: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    host = SOURCE_TALENT_CONFIG.get("mysql_host")
    user = SOURCE_TALENT_CONFIG.get("mysql_user")
    password = SOURCE_TALENT_CONFIG.get("mysql_password")
    database = SOURCE_TALENT_CONFIG.get("mysql_database")
    if not all([host, user, password, database]):
        return []

    try:
        import pymysql
    except Exception as e:
        logger.warning("PyMySQL not available for Source talent MySQL: %s", e)
        return []

    keywords = _source_query_terms(jd_fields)
    where = ""
    params: List[Any] = []
    if keywords:
        clauses = []
        for term in keywords[:8]:
            like = f"%{term}%"
            clauses.append(
                "(name LIKE %s OR raw_text LIKE %s OR current_role LIKE %s OR "
                "current_company LIKE %s OR JSON_SEARCH(skills, 'one', %s) IS NOT NULL)"
            )
            params.extend([like, like, like, like, like])
        where = "WHERE " + " OR ".join(clauses)

    sql = f"""
        SELECT id, name, raw_text, skills, years_experience, education,
               current_role, current_company, source
        FROM candidates
        {where}
        ORDER BY updated_at DESC
        LIMIT %s
    """
    params.append(max(limit * 5, 100))

    try:
        conn = pymysql.connect(
            host=host,
            port=int(SOURCE_TALENT_CONFIG.get("mysql_port", 3306)),
            user=user,
            password=password,
            database=database,
            connect_timeout=8,
            read_timeout=20,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Source talent MySQL query failed: %s", e)
        return []

    mapped = [_map_source_mysql_row(row) for row in rows]
    scored = [(_source_match_score(row, jd_fields), row) for row in mapped]
    scored.sort(key=lambda item: item[0], reverse=True)
    result = []
    for score, row in scored:
        if score <= 0:
            continue
        row.setdefault("jd_alignment_score", min(score * 5, 100))
        row.setdefault("gold_score", 0)
        result.append(row)
    return result[:limit]


def _source_query_terms(jd_fields: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    for value in [
        jd_fields.get("position", ""),
        jd_fields.get("location", ""),
        *(jd_fields.get("skills", []) or []),
        *(jd_fields.get("target_companies", []) or []),
    ]:
        for text in _expand_source_term(str(value).strip()):
            if text and text.lower() not in {t.lower() for t in terms}:
                terms.append(text)
    return terms


def _expand_source_term(value: str) -> List[str]:
    value = value.replace("JD", "").replace("jd", "").strip(" ：:-\t")
    if not value:
        return []
    terms = [value]
    synonym_map = {
        "总裁助理": ["总助", "董事长助理", "CEO助理", "高管助理", "秘书", "行政"],
        "总助": ["总裁助理", "董事长助理", "CEO助理", "高管助理", "秘书", "行政"],
        "产品经理": ["产品", "需求分析", "商业化"],
        "AI产品": ["AI产品经理", "产品经理", "AI", "LLM"],
    }
    for key, values in synonym_map.items():
        if key.lower() in value.lower():
            terms.extend(values)
    return list(dict.fromkeys(terms))


def _map_source_mysql_row(row: Dict[str, Any]) -> Dict[str, Any]:
    skills = row.get("skills") or []
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except Exception:
            skills = _norm_split(skills)
    return {
        "id": str(row.get("id", "")),
        "name": row.get("name", ""),
        "skills": skills if isinstance(skills, list) else [],
        "experience_years": row.get("years_experience", ""),
        "education": row.get("education", ""),
        "current_title": row.get("current_role", ""),
        "current_company": row.get("current_company", ""),
        "summary": (row.get("raw_text") or "")[:1000],
        "raw_profile": row,
        "source_url": f"mysql://source/recruit_bot/candidates/{row.get('id', '')}",
        "source": row.get("source", "mysql"),
    }


def _query_source_api(jd_fields: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    if not SOURCE_TALENT_CONFIG.get("base_url"):
        return []

    url = SOURCE_TALENT_CONFIG["base_url"].rstrip("/") + SOURCE_TALENT_CONFIG["query_path"]
    headers = {}
    if SOURCE_TALENT_CONFIG.get("api_key"):
        headers["Authorization"] = f"Bearer {SOURCE_TALENT_CONFIG['api_key']}"

    payload = {
        "keywords": jd_fields.get("skills", []),
        "location": jd_fields.get("location", ""),
        "position": jd_fields.get("position", ""),
        "target_companies": jd_fields.get("target_companies", []),
        "limit": limit,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("candidates", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            return []
        for row in rows:
            row.setdefault("jd_alignment_score", 60)
            row.setdefault("gold_score", 0)
        return rows
    except Exception as e:
        logger.warning("Source talent API query failed: %s", e)
        return []


def _query_source_file(jd_fields: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    path_value = SOURCE_TALENT_CONFIG.get("file_path")
    if not path_value:
        return []

    path = Path(path_value).expanduser()
    if not path.exists():
        logger.warning("Source talent file does not exist: %s", path)
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Source talent file parse failed: %s", e)
        return []

    rows = data.get("candidates", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []

    scored = [(_source_match_score(row, jd_fields), row) for row in rows]
    scored.sort(key=lambda item: item[0], reverse=True)
    result = []
    for score, row in scored:
        if score <= 0:
            continue
        row.setdefault("jd_alignment_score", min(score * 5, 100))
        row.setdefault("gold_score", 0)
        result.append(row)
    return result[:limit]


def _norm_split(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [
        item.strip()
        for item in str(value or "").replace("，", ",").replace("；", ",").replace(";", ",").split(",")
        if item.strip()
    ]


def _source_match_score(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> int:
    haystack = json.dumps(candidate, ensure_ascii=False).lower()
    score = 0
    for skill in jd_fields.get("skills", []) or []:
        if str(skill).lower() in haystack:
            score += 3
    position = str(jd_fields.get("position", "")).lower()
    if position and position in haystack:
        score += 4
    location = str(jd_fields.get("location", "")).lower()
    if location and location in haystack:
        score += 1
    for company in jd_fields.get("target_companies", []) or []:
        if str(company).lower() in haystack:
            score += 2
    return score
