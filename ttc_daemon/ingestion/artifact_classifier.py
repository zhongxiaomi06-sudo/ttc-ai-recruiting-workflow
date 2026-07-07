"""Artifact Classifier：判断原始内容是 JD、候选人、证据页、聊天记录还是未知。"""
import re
from typing import Tuple, Dict, Any

from ..llm_utils import is_llm_ready, call_llm_json


def _text_of(record: Dict[str, Any]) -> str:
    parts = [
        record.get("title", ""),
        record.get("raw_text", ""),
        record.get("markdown", ""),
    ]
    return "\n".join(p for p in parts if p)


def _source_type_of(record: Dict[str, Any]) -> str:
    return str(record.get("source_type", "") or "").lower()


def _heuristic_classify(text: str, record: Dict[str, Any]) -> Tuple[str, float, str]:
    lower = text.lower()
    if not text.strip():
        return "unknown", 0.0, "内容为空"

    source_type = _source_type_of(record)
    if source_type in {"candidate_resume", "resume_pdf"} or "resume" in source_type:
        return "candidate", 0.85, f"来源类型为 {source_type}，按候选人简历处理"

    jd_signals = [
        "岗位职责", "任职要求", "工作职责", "职位描述", "jd", "招聘",
        "薪资范围", "工作地点", "学历要求", "经验要求", "优先",
        "responsibilities", "requirements", "qualifications",
    ]
    jd_score = sum(1 for k in jd_signals if k in lower)

    cand_signals = [
        "简历", "候选人", "手机号", "邮箱", "联系方式", "工作年限",
        "期望薪资", "到岗时间", "教育背景", "项目经历",
        "联系电话", "微信号", "年龄", "工作经历", "教育经历", "优势亮点",
        "求职状态", "离职", "在职", "个人信息", "自我评价", "专业技能",
        "resume", "curriculum vitae", "work experience", "education",
    ]
    cand_score = sum(1 for k in cand_signals if k in lower)

    chat_signals = [
        "this is a copy of a shared chatgpt conversation",
        "uploaded a file", "uploaded an image", "report conversation",
    ]
    chat_score = sum(1 for k in chat_signals if k in lower)

    scores = [("jd", jd_score), ("candidate", cand_score), ("chat", chat_score)]
    scores.sort(key=lambda x: x[1], reverse=True)
    best_type, best_score = scores[0]

    if cand_score >= 2 and cand_score >= jd_score:
        confidence = min(0.55 + 0.1 * cand_score, 0.9)
        return "candidate", confidence, f"命中 {cand_score} 个 candidate 关键词"

    if best_score >= 2:
        confidence = min(0.5 + 0.1 * best_score, 0.85)
        return best_type, confidence, f"命中 {best_score} 个 {best_type} 关键词"

    if len(text) > 200:
        return "evidence", 0.4, "内容较长但未命中明确类型，暂归为证据页"

    return "unknown", 0.2, "无法判断内容类型"


def _llm_classify(text: str) -> Tuple[str, float, str]:
    system_prompt = """你是一名招聘内容分类助手。请判断以下内容是哪一类，并返回 JSON：
{
  "artifact_type": "jd | candidate | chat | evidence | unknown",
  "confidence": 0.0-1.0,
  "reason": "一句话理由"
}
分类标准：
- jd：包含岗位名称、职责、要求、薪资地点等招聘描述。
- candidate：候选人简历或档案，含姓名、联系方式、工作经历、技能等。
- chat：聊天记录、对话、沟通纪要。
- evidence：某篇文章、网页、文档片段，用于支持对候选人的判断。
- unknown：无法判断。
"""
    user_prompt = f"内容：\n{text[:6000]}"
    try:
        result = call_llm_json(system_prompt, user_prompt)
        artifact_type = result.get("artifact_type", "unknown")
        confidence = float(result.get("confidence", 0))
        reason = result.get("reason", "LLM 分类")
        return artifact_type, confidence, reason
    except Exception as e:
        return "unknown", 0.0, f"LLM 分类失败：{e}"


def classify(record: Dict[str, Any]) -> Tuple[str, float, str]:
    """返回 (artifact_type, confidence, reason)。优先 LLM，失败回退关键词。"""
    text = _text_of(record)
    source_type = _source_type_of(record)
    if source_type in {"candidate_resume", "resume_pdf"} or "resume" in source_type:
        return "candidate", 0.85, f"来源类型为 {source_type}，按候选人简历处理"
    if is_llm_ready() and len(text.strip()) > 50:
        llm_result = _llm_classify(text)
        if llm_result[1] >= 0.5:
            return llm_result
    return _heuristic_classify(text, record)
