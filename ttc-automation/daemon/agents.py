"""Agent implementations for the TTC Orchestrator.

Each agent is a pure-ish function that receives Mission + context and returns
a dict describing the next state / output. No agent directly mutates DB; the
Orchestrator applies updates.
"""

import json
import os
import random
import re
from typing import Any, Optional

import requests

from db import (
    get_artifact,
    insert_agent_run,
    insert_human_task,
    update_mission,
)
from llm_client import complete, parse_json_safe
from source_talent import search as search_source_talent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _local_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    return s


def _jd_keywords(jd_struct: dict) -> list[str]:
    skills = jd_struct.get("skills") or []
    responsibilities = jd_struct.get("responsibilities") or ""
    position = jd_struct.get("position") or ""
    keywords = set([k.strip().lower() for k in skills if k.strip()])
    keywords.update(re.findall(r"[A-Za-z0-9+#\.]+(?:\s+[A-Za-z0-9+#\.]+)*", position))
    keywords.update(re.findall(r"[A-Za-z0-9+#\.]+(?:\s+[A-Za-z0-9+#\.]+)*", responsibilities))
    return list(keywords)


# ---------------------------------------------------------------------------
# Read / classify Agent
# ---------------------------------------------------------------------------
def classify_artifact(content: str, title: Optional[str] = None) -> dict[str, Any]:
    """Classify raw ingest content and extract initial fields."""
    prompt = f"""判断以下文本属于哪一类招聘相关文档，并提取关键字段。

可能的类型：jd（职位描述）、candidate（候选人资料）、evidence（证据/参考）、chat（聊天记录）、unknown（无法判断）。

如果是 jd，请提取 JSON：
{{
  "artifact_type": "jd",
  "confidence": "高|中|低",
  "extracted_fields": {{
    "company": "公司名",
    "position": "岗位名",
    "location": "地点",
    "salary": "薪资",
    "years": "年限要求",
    "education": "学历要求",
    "skills": ["技能1", "技能2"],
    "responsibilities": "职责摘要",
    "keywords": ["关键词1", "关键词2"]
  }}
}}

标题：{title or ''}

文本：
{content[:4000]}
"""
    llm_text = complete(prompt, json_mode=True)
    parsed = parse_json_safe(llm_text)
    if parsed and "artifact_type" in parsed:
        return parsed

    # Fallback heuristic
    text = (title or "") + " " + (content or "")
    lower = text.lower()
    is_jd = any(k in lower for k in ["职位", "岗位", "jd", "招聘", "薪资", "要求", "responsibilities"])
    is_candidate = any(k in lower for k in ["简历", "姓名", "工作经历", "教育经历", "项目经历"])
    if is_jd:
        artifact_type = "jd"
    elif is_candidate:
        artifact_type = "candidate"
    else:
        artifact_type = "unknown"

    skills = list(set(re.findall(r"\b(?:Python|Go|Java|C\+\+|Rust|Node|React|Vue|Kubernetes|Docker|AWS|GCP|Azure|TensorFlow|PyTorch|LLM|AI|SGLang|CUDA|Redis|Kafka|MySQL|PostgreSQL|MongoDB|Elasticsearch)\b", text, re.I)))
    return {
        "artifact_type": artifact_type,
        "confidence": "中" if is_jd or is_candidate else "低",
        "extracted_fields": {
            "skills": skills,
            "keywords": skills,
        },
    }


# ---------------------------------------------------------------------------
# JD Parse Agent
# ---------------------------------------------------------------------------
def jd_parse_agent(mission: dict) -> dict[str, Any]:
    artifact = get_artifact(mission["artifact_id"])
    if not artifact:
        return {"status": "problem_pending", "problem_reason": "artifact_not_found"}

    content = artifact.get("markdown") or artifact.get("content") or ""
    title = artifact.get("title") or ""

    prompt = f"""从以下 JD 文本中提取结构化字段，返回 JSON：
{{
  "company": "",
  "position": "",
  "department": "",
  "location": "",
  "salary": "",
  "years": "",
  "education": "",
  "skills": [],
  "responsibilities": "",
  "keywords": []
}}

标题：{title}
文本：
{content[:6000]}
"""
    llm_text = complete(prompt, json_mode=True)
    jd_struct = parse_json_safe(llm_text)

    if not jd_struct:
        # Heuristic fallback
        jd_struct = {
            "company": _extract_field(content, ["公司", "企业"]),
            "position": title or _extract_field(content, ["职位", "岗位", "招聘"]),
            "location": _extract_field(content, ["地点", "城市", "base"]),
            "salary": _extract_field(content, ["薪资", "年薪", "月薪", "salary"]),
            "years": _extract_field(content, ["经验", "年限", "工作年限"]),
            "education": _extract_field(content, ["学历", "本科", "硕士", "博士"]),
            "skills": list(set(re.findall(r"\b(?:Python|Go|Java|C\+\+|Rust|Node|React|Vue|Kubernetes|Docker|AWS|GCP|Azure|TensorFlow|PyTorch|LLM|AI|SGLang|CUDA|Redis|Kafka|MySQL|PostgreSQL|MongoDB|Elasticsearch)\b", content, re.I))),
            "responsibilities": "",
            "keywords": [],
        }

    # Validate minimum confidence
    if not jd_struct.get("position") and not jd_struct.get("skills"):
        return {
            "status": "problem_pending",
            "problem_reason": "jd_clarify",
            "jd_struct": jd_struct,
        }

    return {"status": "jd_parsed", "jd_struct": jd_struct}


def _extract_field(text: str, keywords: list[str]) -> str:
    lines = text.splitlines()
    for kw in keywords:
        for line in lines:
            if kw in line:
                return line.strip()
    return ""


# ---------------------------------------------------------------------------
# Sourcing Agent
# ---------------------------------------------------------------------------
def _fetch_candidate_collector(min_score: int = 0) -> list[dict]:
    try:
        url = f"http://127.0.0.1:8765/api/export-jd?min_score={min_score}"
        s = _local_session()
        r = s.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("candidates", [])
    except Exception as exc:
        print(f"[sourcing_agent] candidate-collector unreachable: {exc}")
    return []


def _fetch_talent_db(jd_struct: dict) -> list[dict]:
    if os.getenv("TTC_TALENT_DB_ENABLED", "").lower() != "true":
        return []
    talent_url = os.getenv("TTC_TALENT_DB_URL")
    talent_key = os.getenv("TTC_TALENT_DB_KEY")
    if not talent_url:
        return []
    try:
        headers = {}
        if talent_key:
            headers["Authorization"] = f"Bearer {talent_key}"
        s = _local_session()
        payload = {"query": jd_struct.get("position", ""), "skills": jd_struct.get("skills", [])}
        r = s.post(talent_url, headers=headers, json=payload, timeout=20)
        r.raise_for_status()
        return r.json() if isinstance(r.json(), list) else r.json().get("candidates", [])
    except Exception as exc:
        print(f"[sourcing_agent] talent db error: {exc}")
    return []


def sourcing_agent(mission: dict) -> dict[str, Any]:
    jd_struct = json.loads(mission["jd_struct"]) if mission.get("jd_struct") else {}
    if not jd_struct:
        return {"status": "problem_pending", "problem_reason": "missing_jd_struct"}

    candidates = []
    candidates.extend(_fetch_candidate_collector(min_score=0))
    candidates.extend(_fetch_talent_db(jd_struct))
    candidates.extend(search_source_talent(jd_struct, limit=50))

    # Deduplicate by name + phone/email if present, else by name
    seen = set()
    deduped = []
    for c in candidates:
        key = c.get("phone") or c.get("email") or c.get("name", "") or str(c.get("id", ""))
        if key and key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    if not deduped:
        return {"status": "problem_pending", "problem_reason": "sourcing_empty", "jd_struct": jd_struct}

    return {"status": "sourcing", "candidates": deduped}


# ---------------------------------------------------------------------------
# Scoring Agent
# ---------------------------------------------------------------------------
def scoring_agent(mission: dict, candidates: list[dict]) -> dict[str, Any]:
    jd_struct = json.loads(mission["jd_struct"]) if mission.get("jd_struct") else {}
    keywords = _jd_keywords(jd_struct)
    jd_text = json.dumps(jd_struct, ensure_ascii=False).lower()

    scored = []
    for c in candidates:
        candidate_text = json.dumps(c, ensure_ascii=False).lower()
        hits = sum(1 for kw in keywords if kw.lower() in candidate_text)
        jd_alignment = min(100, int(40 + hits * 8))
        gold_score = int(50 + random.random() * 40)  # placeholder for GoldScoreEngine
        risk = 0
        risk_flags = []

        # Simple risk signals
        if "外包" in candidate_text or "odc" in candidate_text:
            risk += 15
            risk_flags.append("外包/ODC 经历")
        if "频繁" in candidate_text or candidate_text.count("公司") > 5:
            risk += 5
            risk_flags.append("多段经历需验证")

        overall = round(jd_alignment * 0.6 + gold_score * 0.4 - risk, 1)
        scored.append({
            "candidate": c,
            "jd_alignment": jd_alignment,
            "gold_score": gold_score,
            "risk": risk,
            "risk_flags": risk_flags,
            "overall_score": max(0, overall),
        })

    scored.sort(key=lambda x: x["overall_score"], reverse=True)
    return {"status": "scored", "scores": scored}


# ---------------------------------------------------------------------------
# Human Review / Calling Agent
# ---------------------------------------------------------------------------
def human_review_agent(mission: dict, scores: list[dict]) -> dict[str, Any]:
    if not scores:
        return {"status": "problem_pending", "problem_reason": "no_scored_candidates"}

    top = scores[0]
    if top["overall_score"] < 60 or top["risk"] >= 20:
        task_payload = {
            "reason": "top_candidate_low_score_or_high_risk",
            "top_candidate": top,
            "jd": json.loads(mission["jd_struct"]) if mission.get("jd_struct") else {},
        }
        return {
            "status": "human_review",
            "task_type": "client_review",
            "task_payload": task_payload,
        }

    return {"status": "calling", "scores": scores}


def generate_call_script(candidate: dict, jd_struct: dict) -> str:
    name = candidate.get("candidate", {}).get("name", "候选人")
    position = jd_struct.get("position", "该岗位")
    company = jd_struct.get("company", "客户公司")
    skills = ", ".join(jd_struct.get("skills", [])[:5])
    return (
        f"{name} 您好，我是 TTC 猎头顾问。我们这边有一个 {company} 的 {position} 机会，"
        f"主要看 {skills} 方向，和您的背景比较匹配。想先跟您花 3-5 分钟简单聊聊，"
        f"看看您对这个机会是否感兴趣？"
    )


def calling_agent(mission: dict, scores: list[dict]) -> dict[str, Any]:
    jd_struct = json.loads(mission["jd_struct"]) if mission.get("jd_struct") else {}
    top_n = scores[:3]
    call_list = []
    for s in top_n:
        item = {
            "candidate": s["candidate"],
            "overall_score": s["overall_score"],
            "jd_alignment": s["jd_alignment"],
            "gold_score": s["gold_score"],
            "risk_flags": s["risk_flags"],
            "script": generate_call_script(s, jd_struct),
            "evidence": s["candidate"].get("evidence", "") or s["candidate"].get("source_url", ""),
            "verification_questions": [
                "您目前的状态是在职还是看机会？",
                f"您对 {jd_struct.get('location', '')} 的机会是否接受？",
                "您最近一年的主要技术栈和项目是什么？",
            ],
        }
        call_list.append(item)
    return {"status": "calling", "call_list": call_list}


# ---------------------------------------------------------------------------
# Feedback Agent
# ---------------------------------------------------------------------------
def feedback_agent(mission: dict, tasks: list[dict]) -> dict[str, Any]:
    results = [json.loads(t["result_json"]) if t.get("result_json") else {} for t in tasks]
    feedback = {
        "total_tasks": len(tasks),
        "results": results,
        "summary": "人类反馈已收集，待用于模型校准。",
    }
    return {"status": "closed", "feedback": feedback}


# ---------------------------------------------------------------------------
# Human Dispatch
# ---------------------------------------------------------------------------
def create_problem_task(mission: dict, problem_reason: str, context: dict) -> dict[str, Any]:
    payload = {
        "problem_reason": problem_reason,
        "context": context,
        "jd": json.loads(mission["jd_struct"]) if mission.get("jd_struct") else {},
    }
    return {"task_type": "problem_solve", "task_payload": payload}


def record_agent_run(mission_id: str, agent_name: str, input_data: Any,
                     output_data: Any, status: str, error: Optional[str] = None) -> None:
    insert_agent_run(mission_id, agent_name, input_data, output_data, status, error)
