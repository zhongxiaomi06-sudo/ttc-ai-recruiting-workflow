"""JD 解析核心：把原始 JD 文本变成结构化字段。"""
import logging
import re
from typing import Dict, Any

from ..config import LLM_CONFIG
from ..llm_utils import is_llm_ready, call_llm_json

logger = logging.getLogger(__name__)


def extract_jd(raw_text: str) -> Dict[str, Any]:
    """从 JD 原始文本提取结构化字段。优先使用 LLM，否则简单兜底。"""
    if LLM_CONFIG.get("api_key"):
        try:
            return _extract_jd_with_llm(raw_text)
        except Exception as e:
            logger.warning("LLM JD extraction failed: %s; falling back", e)
    return _extract_jd_fallback(raw_text)


def _extract_jd_with_llm(raw_text: str) -> Dict[str, Any]:
    system_prompt = """你是一名招聘 JD 结构化提取助手。请从以下 JD/招聘描述中提取结构化信息，返回 JSON：
{
  "company": "公司名",
  "position": "岗位名",
  "location": "城市",
  "salary": "薪资范围",
  "experience_years": "经验要求",
  "education": "学历要求",
  "skills": ["技能1", "技能2"],
  "responsibilities": "职责摘要",
  "requirements": "要求摘要",
  "keywords": ["搜索关键词"]
}
如果字段无法确定，使用空字符串或空数组。只返回 JSON，不要其他内容。"""
    user_prompt = f"JD 内容：\n{raw_text[:8000]}"
    result = call_llm_json(system_prompt, user_prompt, temperature=0.2)
    for key in ["company", "position", "location", "salary", "experience_years", "education", "responsibilities", "requirements"]:
        result.setdefault(key, "")
    for key in ["skills", "keywords"]:
        result.setdefault(key, [])
    return result


def _extract_position(text: str) -> str:
    """从文本开头提取一个简洁的岗位名称。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""

    # 优先找显式标题字段
    for pat in [r"(?:岗位|职位)[：:]\s*([^\n]{1,40})", r"【(.{1,40})】"]:
        m = re.search(pat, text)
        if m:
            title = m.group(1).strip()
            if 3 <= len(title) <= 40:
                return _clean_position(title)

    # 第一行不太长时直接用
    first = lines[0]
    if 3 <= len(first) <= 50:
        return _clean_position(first)

    # 找包含常见岗位后缀的短语
    suffixes = r"(?:工程师|负责人|经理|总监|研究员|科学家|专家|架构师|算法|开发|运营|产品|设计师|顾问|主管|助理|秘书|行政|HR|财务|销售|市场|VP|CTO|CEO|COO)"
    m = re.search(r"([一-龥A-Za-z0-9\-/\s]{2,25}?(?:" + suffixes + r"))", text)
    if m:
        return _clean_position(m.group(1).strip())

    # 兜底：第一行截断
    return _clean_position(first[:50])


def _clean_position(position: str) -> str:
    position = re.sub(r"\bJD\b", "", position, flags=re.I)
    position = position.replace("职位描述", "").replace("岗位职责", "").strip(" ：:-\t")
    return re.sub(r"\s+", " ", position).strip()


def _infer_role_keywords(position: str, raw_text: str) -> list:
    text = f"{position}\n{raw_text}"
    groups = [
        (["总裁助理", "总助", "董事长助理", "CEO助理", "高管助理"], ["总裁助理", "总助", "董事长助理", "CEO助理", "高管助理", "秘书", "行政"]),
        (["产品经理", "AI产品", "产品"], ["产品", "产品经理", "需求分析", "商业化", "用户增长"]),
        (["运营"], ["运营", "用户运营", "内容运营", "增长"]),
        (["销售", "商务"], ["销售", "商务", "BD", "客户成功"]),
        (["财务"], ["财务", "会计", "审计", "预算"]),
        (["HR", "人力", "招聘"], ["HR", "人力资源", "招聘", "组织发展"]),
    ]
    found = []
    for triggers, keywords in groups:
        if any(trigger.lower() in text.lower() for trigger in triggers):
            found.extend(keywords)
    return list(dict.fromkeys(found))


def _extract_jd_fallback(raw_text: str) -> Dict[str, Any]:
    position = _extract_position(raw_text)
    skills = re.findall(
        r"\b(Python|Go|Java|Rust|C\+\+|JavaScript|TypeScript|React|Vue|Node|Kubernetes|Docker|Redis|Kafka|MySQL|PostgreSQL|MongoDB|Elasticsearch|AWS|阿里云|TensorFlow|PyTorch|LLM|AI|算法|后端|前端|全栈|运维|SRE|产品|设计|数据|vLLM|SGLang|CUDA|TensorRT)\b",
        raw_text,
        flags=re.I,
    )
    skills = list(dict.fromkeys(skills + _infer_role_keywords(position, raw_text)))
    return {
        "company": "",
        "position": position,
        "location": "",
        "salary": "",
        "experience_years": "",
        "education": "",
        "skills": skills,
        "responsibilities": "",
        "requirements": "",
        "keywords": skills,
    }
