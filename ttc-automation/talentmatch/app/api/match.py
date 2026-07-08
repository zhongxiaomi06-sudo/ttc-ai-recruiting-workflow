"""Match API — HybridEngine (规则+ML混合评分) + explain/compare/history"""
from __future__ import annotations
import re, json, uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
from storage import get_storage
from matching.engine import MatchEngine
from matching.hybrid_engine import HybridEngine

router = APIRouter(tags=["match"])

# Hybrid engine (规则 0.6 + ML 0.4)
_engine = HybridEngine()

COMMON_TECH_SKILLS = [
    'Python', 'Java', 'React', 'SQL', 'PyTorch', 'TensorFlow', 'Spring',
    'Docker', 'K8s', 'TypeScript', 'Node.js', 'Redis', 'Kafka', 'AWS',
    'GCP', 'NLP', 'RAG', 'LangChain', 'Go', 'Rust', 'Flutter', 'Vue',
    'Angular', 'MongoDB', 'PostgreSQL', 'MySQL', 'Spark', 'Flink',
    'Hadoop', '微服务', '高并发', '分布式',
    '机器学习', '深度学习', '自然语言处理', '计算机视觉',
    '推荐系统', '广告系统', '搜索算法', '数据挖掘',
    '产品经理', '用户增长', '数据分析', '商业化',
    '前端开发', '后端开发', '全栈开发', '移动端',
    '测试开发', '运维开发', 'DevOps', 'SRE',
    '项目管理', '技术管理', '架构设计', '系统设计',
]


class FastMatchRequest(BaseModel):
    jd_text: str = Field(..., min_length=1, description="JD描述文本")
    limit: int = Field(default=10, ge=1, le=50, description="返回结果数量")


class CompareRequest(BaseModel):
    candidate_ids: list[str] = Field(..., min_items=2, max_items=5, description="候选人ID列表（2-5个）")
    jd_text: str = Field(..., min_length=1, description="JD描述文本")


def _extract_skills(text: str) -> list:
    """从JD文本提取技能关键词"""
    keywords = re.findall(r'[A-Za-z#+.-]+(?:\s*[A-Za-z#+.-]+)*', text)
    keywords = [s.strip() for s in keywords if len(s.strip()) > 1]
    found = set()
    for cs in COMMON_TECH_SKILLS:
        if any(cs.lower() in kw.lower() for kw in keywords):
            found.add(cs.lower())
    return list(found)


def _search_candidates(storage, found: list, jd_text: str) -> list:
    """搜索候选人"""
    seen = set()
    cands = []
    for skill in found[:8]:
        for c in storage.search_candidates(skill, limit=3):
            if c['id'] not in seen:
                seen.add(c['id'])
                cands.append(c)
    if len(cands) < 3:
        words = [w for w in jd_text.split() if len(w) > 1][:10]
        for word in words:
            for c in storage.search_candidates(word, limit=3):
                if c['id'] not in seen:
                    seen.add(c['id'])
                    cands.append(c)
    return cands


def _build_job(jd_text: str, found: list, title: str = "") -> dict:
    return {
        "title": title or _extract_title(jd_text) or "JD快速匹配",
        "company": "",
        "required_skills": found,
        "preferred_skills": [],
        "min_years_experience": _extract_years(jd_text),
        "max_years_experience": None,
        "salary_range": _extract_salary_range(jd_text),
    }


def _score_one(engine, full: dict, job: dict):
    """对单个候选人打分并返回结构化结果"""
    ms = engine.compute(full, job)
    return {
        "candidate_id": full.get("id", ""),
        "candidate_name": full.get("name", "未知"),
        "current_role": full.get("current_role", ""),
        "current_company": full.get("current_company", ""),
        "years_experience": full.get("years_experience", 0),
        "overall_score": round(ms.overall_score, 3),
        "skill_score": round(ms.skill_score, 3),
        "experience_score": round(ms.experience_score, 3),
        "education_score": round(ms.education_score, 3),
        "matched_skills": ms.matched_skills,
        "missing_skills": ms.missing_skills,
        "strengths": ms.strengths,
        "gaps": ms.gaps,
        "reasoning": ms.reasoning,
        "explanation": ms.explanation,
        "recommendation": ms.recommendation,
    }


def _save_matches(storage, job_id: str, results: list):
    """保存匹配记录到数据库"""
    try:
        conn = storage._get_conn()
        now = datetime.now().isoformat()
        for r in results:
            mid = str(uuid.uuid4())
            conn.execute(
                """INSERT OR IGNORE INTO matches 
                   (id, candidate_id, job_id, overall_score, skill_score,
                    experience_score, matched_skills, missing_skills,
                    strengths, gaps, reasoning, explanation, recommendation, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (mid, r["candidate_id"], job_id,
                 r["overall_score"], r["skill_score"], r["experience_score"],
                 json.dumps(r["matched_skills"]), json.dumps(r["missing_skills"]),
                 json.dumps(r["strengths"]), json.dumps(r["gaps"]),
                 r["reasoning"], r["explanation"], r["recommendation"], now)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"保存匹配记录失败: {e}")


@router.post("/fast-match")
async def fast_match(req: FastMatchRequest):
    """快速匹配：输入JD文本 → HybridEngine评分 → 返回带解释的匹配结果"""
    jd_text = req.jd_text
    limit = req.limit
    storage = get_storage()
    try:
        found = _extract_skills(jd_text)
        cands = _search_candidates(storage, found, jd_text)
        if not cands:
            return {"matches": [], "total": 0, "message": "未找到匹配候选人"}

        job = _build_job(jd_text, found)
        results = []
        for c in cands:
            full = storage.get_candidate(c["id"])
            if full:
                results.append(_score_one(_engine, full, job))

        results.sort(key=lambda m: m["overall_score"], reverse=True)
        top = results[:limit]

        job_id = f"fast_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        _save_matches(storage, job_id, top)

        return {"matches": top, "total": len(results), "job_id": job_id}

    except Exception as e:
        logger.error(f"fast-match 错误: {e}")
        raise HTTPException(500, f"匹配失败: {str(e)[:200]}")


@router.post("/compare")
async def compare_candidates(req: CompareRequest):
    """对比多个候选人（2-5个）与同一JD的匹配"""
    storage = get_storage()
    found = _extract_skills(req.jd_text)
    job = _build_job(req.jd_text, found, "JD对比")
    results = []
    for cid in req.candidate_ids:
        full = storage.get_candidate(cid)
        if not full:
            results.append({"candidate_id": cid, "candidate_name": "?", "error": "候选人不存在"})
            continue
        results.append(_score_one(_engine, full, job))
    results.sort(key=lambda m: m.get("overall_score", 0), reverse=True)
    return {"comparison": results, "total": len(results)}


@router.get("/explain/{candidate_id}")
async def explain_match(candidate_id: str, jd_text: str = ""):
    """获取某个候选人的匹配评分详细解释"""
    storage = get_storage()
    full = storage.get_candidate(candidate_id)
    if not full:
        raise HTTPException(404, "候选人不存在")
    if not jd_text:
        return {
            "candidate": {
                "id": full["id"], "name": full.get("name"),
                "current_role": full.get("current_role"),
                "current_company": full.get("current_company"),
                "years_experience": full.get("years_experience", 0),
                "skills": full.get("skills", []),
                "education": full.get("education", ""),
            },
            "message": "请提供 jd_text 参数来获取匹配解释"
        }
    found = _extract_skills(jd_text)
    job = _build_job(jd_text, found, "JD解释")
    ms = _engine.compute(full, job)
    return {
        "candidate_id": candidate_id,
        "candidate_name": full.get("name", "未知"),
        "overall_score": round(ms.overall_score, 3),
        "skill_score": round(ms.skill_score, 3),
        "experience_score": round(ms.experience_score, 3),
        "education_score": round(ms.education_score, 3),
        "matched_skills": ms.matched_skills,
        "missing_skills": ms.missing_skills,
        "strengths": ms.strengths,
        "gaps": ms.gaps,
        "explanation": ms.explanation,
        "reasoning": ms.reasoning,
        "recommendation": ms.recommendation,
        "job": job,
    }


@router.post("/reload-rules")
async def reload_rules():
    try:
        _engine.rule_engine.reload_rules()
        return {"status": "ok", "message": "规则配置已重新加载"}
    except Exception as e:
        raise HTTPException(500, f"规则重载失败: {str(e)[:200]}")


@router.get("/match-rules")
async def get_match_rules():
    rules_info = [{"name": r.name, "weight": r.weight} for r in _engine.rule_engine.rules]
    return {
        "rules": rules_info,
        "total_rules": len(rules_info),
        "total_weight": round(sum(r.weight for r in _engine.rule_engine.rules), 2),
        "hybrid_weights": _engine.weights,
    }


@router.get("/history")
async def get_match_history(limit: int = 20):
    """获取最近的历史匹配记录"""
    storage = get_storage()
    conn = storage._get_conn()
    rows = conn.execute(
        """SELECT id, candidate_id, job_id, overall_score, recommendation,
                  explanation, created_at
           FROM matches ORDER BY created_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return {"matches": [dict(zip(
        ["id", "candidate_id", "job_id", "overall_score", "recommendation",
         "explanation", "created_at"], r
    )) for r in rows]}


def _extract_title(text: str) -> str:
    lines = text.strip().split('\n')
    titles = ['算法', '开发', '产品', '设计', '运营', '数据',
              '工程', '架构', '测试', '运维', '分析师', '顾问',
              '经理', '总监', '专家', '研究员']
    for line in lines[:5]:
        line = line.strip()
        if line and len(line) < 30 and any(t in line for t in titles):
            return line
    return ""


def _extract_years(text: str) -> int:
    nums = re.findall(r'(\d+)[-\s]*年', text)
    return int(nums[0]) if nums else 0


def _extract_salary_range(text: str) -> str:
    match = re.search(r'(\d+[Kk]?[-\s~到至]+[\d.]+[Kk万]?)', text)
    return match.group(1) if match else ""


__all__ = ["router"]
from fastapi import UploadFile, File
import os

@router.post("/parse")
async def api_parse_resume(file: UploadFile = File(...)):
    """上传简历文件（PDF/DOCX/TXT），解析并入库"""
    from app import _pipelines
    from fastapi.responses import JSONResponse
    upload_dir = os.environ.get("UPLOAD_DIR", "/opt/recruit-bot-v5/data/uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    try:
        content_bytes = await file.read()
        with open(file_path, "wb") as f:
            f.write(content_bytes)
    except Exception as e:
        raise HTTPException(500, f"文件保存失败: {str(e)[:200]}")
    resume_pipeline = _pipelines.get("resume_pipeline")
    if not resume_pipeline:
        raise HTTPException(500, "简历解析管道未初始化")
    try:
        result = resume_pipeline.process_file(file_path)
    except Exception as e:
        raise HTTPException(500, f"简历解析失败: {str(e)[:200]}")
    if result.get("status") == "ok":
        storage = get_storage()
        candidate = storage.get_candidate(result.get("candidate_id", ""))
        if candidate:
            return {"status": "ok", "candidate": candidate, "candidate_id": candidate.get("id")}
        return {"status": "ok", "candidate_id": result.get("candidate_id")}
    return JSONResponse(status_code=500, content=result)

