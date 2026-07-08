"""TalentMatch scoring adapter.

This module keeps TTC's Mission state machine independent from TalentMatch.
It only translates TTC candidate/JD dictionaries into TalentMatch vectors and
maps the result back into TTC's scoring fields.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests


def _candidate_paths() -> Iterable[Path]:
    env_path = os.getenv("TTC_TALENTMATCH_PATH", "").strip()
    if env_path:
        yield Path(env_path)
    yield Path("/opt/talentmatch")
    yield Path.cwd() / "ttc-automation" / "talentmatch"
    yield Path(__file__).resolve().parents[2] / "ttc-automation" / "talentmatch"


def _ensure_talentmatch_path() -> Optional[Path]:
    for path in _candidate_paths():
        if (path / "matching" / "unified_engine.py").exists():
            text = str(path)
            if text not in sys.path:
                sys.path.insert(0, text)
            return path
    return None


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    return _as_list(data)
            except Exception:
                pass
        return [p.strip() for p in re.split(r"[,，;；、\n]", text) if p.strip()]
    return []


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return int(match.group())
    return default


def _candidate_record(candidate: Dict[str, Any]) -> Dict[str, Any]:
    raw_profile = candidate.get("raw_profile") if isinstance(candidate.get("raw_profile"), dict) else {}
    skills = candidate.get("skills") or raw_profile.get("skills") or []
    return {
        "id": str(candidate.get("id") or raw_profile.get("id") or candidate.get("name") or "unknown"),
        "name": candidate.get("name") or candidate.get("candidate_name") or raw_profile.get("name") or "",
        "skills": _as_list(skills),
        "years_experience": _as_int(
            candidate.get("years_experience")
            or candidate.get("experience_years")
            or raw_profile.get("years_experience")
            or raw_profile.get("experience_years")
        ),
        "education": candidate.get("education") or raw_profile.get("education") or "",
        "education_level": candidate.get("education_level") or raw_profile.get("education_level") or candidate.get("education") or "",
        "school_tier": candidate.get("school_tier") or raw_profile.get("school_tier") or "",
        "current_company": candidate.get("current_company") or raw_profile.get("current_company") or "",
        "company_tier": candidate.get("company_tier") or raw_profile.get("company_tier") or "",
        "career_stability": candidate.get("career_stability") or raw_profile.get("career_stability") or "",
        "role_level": candidate.get("role_level") or raw_profile.get("role_level") or "",
        "industry_tags": _as_list(candidate.get("industry_tags") or raw_profile.get("industry_tags")),
        "salary_expectation": candidate.get("salary_expectation") or candidate.get("salary_expected") or "",
        "highlights": _as_list(candidate.get("highlights") or candidate.get("match_reasons")),
        "raw_text": candidate.get("raw_text") or candidate.get("summary") or raw_profile.get("raw_text") or "",
    }


def _job_record(jd_fields: Dict[str, Any]) -> Dict[str, Any]:
    skills = _as_list(jd_fields.get("skills") or jd_fields.get("keywords"))
    return {
        "id": str(jd_fields.get("id") or jd_fields.get("mission_id") or "jd"),
        "title": jd_fields.get("position") or jd_fields.get("title") or "岗位",
        "company": jd_fields.get("company") or "",
        "department": jd_fields.get("department") or "",
        "required_skills": skills,
        "preferred_skills": _as_list(jd_fields.get("preferred_skills")),
        "min_years_experience": _as_int(jd_fields.get("experience_years") or jd_fields.get("min_years_experience")),
        "max_years_experience": _as_int(jd_fields.get("max_years_experience"), 99),
        "education": jd_fields.get("education") or "",
        "salary_range": jd_fields.get("salary") or jd_fields.get("salary_range") or "",
        "industry": jd_fields.get("industry") or "",
        "description": " ".join(
            str(jd_fields.get(k) or "")
            for k in ["requirements", "responsibilities", "raw_text", "description"]
        ).strip(),
        "hidden_requirements": _as_list(jd_fields.get("hidden_requirements")),
        "key_selling_points": _as_list(jd_fields.get("key_selling_points")),
    }


def _dimension_map(result: Any) -> Dict[str, Any]:
    return {getattr(d, "name", ""): d for d in getattr(result, "dimensions", [])}


def _score_gold_from_dimensions(dimensions: Dict[str, Any], existing: Any = None) -> float:
    if existing not in (None, "", 0, 0.0):
        return round(max(0.0, min(100.0, float(existing))), 1)
    weighted = (
        getattr(dimensions.get("company_tier"), "score", 0.5) * 0.45
        + getattr(dimensions.get("education"), "score", 0.5) * 0.25
        + getattr(dimensions.get("stability"), "score", 0.5) * 0.20
        + getattr(dimensions.get("industry_alignment"), "score", 0.5) * 0.10
    )
    return round(max(0.0, min(100.0, weighted * 100)), 1)


def _normalize_gold_payload(data: Any) -> Dict[str, Any]:
    if hasattr(data, "to_dict"):
        data = data.to_dict()
    elif hasattr(data, "model_dump"):
        data = data.model_dump()
    elif hasattr(data, "__dict__"):
        data = dict(data.__dict__)
    if not isinstance(data, dict):
        return {}
    if isinstance(data.get("gold_score"), dict):
        data = data["gold_score"]
    score = data.get("overall_score", data.get("score", data.get("gold_score")))
    result: Dict[str, Any] = {}
    if score not in (None, ""):
        result["gold_score"] = round(max(0.0, min(100.0, float(score))), 1)
    for src, dst in [
        ("risk_flags", "risk_flags"),
        ("risks", "risk_flags"),
        ("evidence", "gold_evidence"),
        ("reasoning", "gold_reasoning"),
        ("verification_questions", "verification_questions"),
        ("follow_up_questions", "verification_questions"),
    ]:
        if src in data and data[src]:
            result[dst] = data[src]
    return result


def _resume_text_for_goldscore(candidate: Dict[str, Any]) -> str:
    raw_profile = candidate.get("raw_profile") if isinstance(candidate.get("raw_profile"), dict) else {}
    parts = [
        candidate.get("raw_text"),
        candidate.get("summary"),
        raw_profile.get("raw_text"),
        raw_profile.get("summary"),
        candidate.get("resume_text"),
    ]
    text = "\n".join(str(p).strip() for p in parts if str(p or "").strip())
    if text:
        return text
    record = _candidate_record(candidate)
    return "\n".join(
        str(v).strip()
        for v in [
            record.get("name"),
            record.get("current_company"),
            " ".join(record.get("skills") or []),
            record.get("education"),
            " ".join(record.get("highlights") or []),
        ]
        if str(v or "").strip()
    )


def _score_gold_with_service(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> Dict[str, Any]:
    url = os.getenv("TTC_GOLDSCORE_URL", "").strip()
    if not url:
        return {}
    headers = {"Content-Type": "application/json"}
    token = os.getenv("TTC_GOLDSCORE_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {
        "candidate": _candidate_record(candidate),
        "jd": _job_record(jd_fields),
        "raw_candidate": candidate,
        "raw_jd": jd_fields,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=20)
    resp.raise_for_status()
    return _normalize_gold_payload(resp.json())


def _score_gold_with_module(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> Dict[str, Any]:
    if os.getenv("TTC_GOLDSCORE_LOCAL_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        return {}
    path = _ensure_talentmatch_path()
    if not path:
        return {}
    try:
        from matching.gold_score_engine import GoldScoreEngine
    except Exception:
        return {}
    engine = GoldScoreEngine()
    resume_text = _resume_text_for_goldscore(candidate)
    for method_name in ["score", "score_candidate", "evaluate"]:
        method = getattr(engine, method_name, None)
        if not callable(method):
            continue
        try:
            result = method(resume_text, str(candidate.get("id") or candidate.get("name") or ""))
        except TypeError:
            result = method(resume_text)
        return _normalize_gold_payload(result)
    return {}


def _apply_gold_result(candidate: Dict[str, Any], gold_result: Dict[str, Any]) -> None:
    if not gold_result:
        return
    if "gold_score" in gold_result:
        candidate["gold_score"] = gold_result["gold_score"]
    if gold_result.get("risk_flags"):
        existing = list(candidate.get("risk_flags") or [])
        existing.extend(str(x) for x in _as_list(gold_result["risk_flags"]))
        candidate["risk_flags"] = list(dict.fromkeys(existing))
    if gold_result.get("gold_evidence"):
        evidence = candidate.setdefault("evidence", [])
        gold_evidence = gold_result["gold_evidence"]
        if isinstance(gold_evidence, list):
            evidence.extend(gold_evidence)
        else:
            evidence.append({"dimension": "gold_score", "evidence": str(gold_evidence)})
    if gold_result.get("gold_reasoning"):
        candidate["gold_reasoning"] = gold_result["gold_reasoning"]
    if gold_result.get("verification_questions"):
        candidate["verification_questions"] = _as_list(gold_result["verification_questions"])


def _score_gold_external(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = _score_gold_with_service(candidate, jd_fields)
        if result:
            result["gold_provider"] = "goldscore_service"
            return result
    except Exception:
        pass
    try:
        result = _score_gold_with_module(candidate, jd_fields)
    except Exception:
        result = {}
    if result:
        result["gold_provider"] = "goldscore_module"
    return result


def score_with_talentmatch(candidate: Dict[str, Any], jd_fields: Dict[str, Any], provider: str = "talentmatch") -> Dict[str, Any]:
    """Score with TalentMatch UnifiedMatchEngine and return TTC fields.

    Raises ImportError/RuntimeError on unavailable engine so caller can fall back.
    """
    path = _ensure_talentmatch_path()
    if not path:
        raise ImportError("TalentMatch matching/unified_engine.py not found")

    from matching.unified_engine import UnifiedMatchEngine, candidate_from_storage, job_from_storage

    engine = UnifiedMatchEngine()
    result = engine.compute_match(
        candidate_from_storage(_candidate_record(candidate)),
        job_from_storage(_job_record(jd_fields)),
    )
    dimensions = _dimension_map(result)
    overall = round(float(result.overall_score) * 100, 1)
    jd_alignment = round(getattr(dimensions.get("skill_match"), "score", 0.0) * 100, 1)
    gold_result = _score_gold_external(candidate, jd_fields) if provider in {"goldscore", "auto"} else {}
    gold = gold_result.get("gold_score") or _score_gold_from_dimensions(dimensions, candidate.get("gold_score"))

    evidence = [
        {
            "dimension": getattr(dim, "name", ""),
            "score": round(float(getattr(dim, "score", 0.0)) * 100, 1),
            "weight": getattr(dim, "weight", 0),
            "evidence": getattr(dim, "evidence", ""),
        }
        for dim in getattr(result, "dimensions", [])
    ]
    risk_flags = list(candidate.get("risk_flags") or [])
    for skill in getattr(result, "missing_skills", [])[:5]:
        risk_flags.append(f"缺失技能：{skill}")

    candidate["overall_score"] = overall
    candidate["jd_alignment_score"] = jd_alignment
    candidate["gold_score"] = gold
    candidate["risk_flags"] = risk_flags
    candidate["match_reasons"] = list(getattr(result, "matched_skills", []) or [])
    candidate["missing_skills"] = list(getattr(result, "missing_skills", []) or [])
    candidate["evidence"] = evidence
    candidate["recommendation"] = getattr(result, "recommendation", "")
    candidate["score_explanation"] = getattr(result, "explanation", "")
    _apply_gold_result(candidate, gold_result)
    if gold_result.get("gold_provider"):
        candidate["gold_provider"] = gold_result["gold_provider"]
    candidate["score_provider"] = "goldscore" if provider == "goldscore" else "talentmatch"
    return candidate
