"""评分与话术核心。

评分引擎支持两种模式：
1. LLM CoT 分步评分（推荐）：6 步思维链，每步绑定简历证据
2. 简单加权兜底：jd_alignment * 0.6 + gold_score * 0.4

LLM 评分输出包含：
- overall_score（0-100）
- 各维度分数 + 证据绑定（每项分数绑定简历原句）
- risk_flags（红灯/黄灯）
- confidence（high/medium/low）
- level（扎实/中上/中等/较浅/不足）
- verification_questions（5-10 个追问题）
- company_analysis（公司含金量分析）
"""
import json
import logging
import statistics
from typing import Any, Dict, List, Optional, Tuple

from ..config import LLM_CONFIG
from ..llm_utils import is_llm_ready, call_llm_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 评分维度定义
# ---------------------------------------------------------------------------
SCORING_DIMENSIONS = [
    {
        "key": "tech_depth",
        "label": "技术深度",
        "weight": 0.25,
        "description": "在核心技术领域（如 AI/后端/架构）的深度，是否达到 JD 要求的技术水平",
    },
    {
        "key": "project_ownership",
        "label": "项目所有权",
        "weight": 0.20,
        "description": "是否对项目有端到端负责的经验，而非仅参与部分模块",
    },
    {
        "key": "complexity",
        "label": "复杂度",
        "weight": 0.20,
        "description": "所处理问题的复杂度（规模、并发、多维度权衡），系统设计能力",
    },
    {
        "key": "impact",
        "label": "结果影响",
        "weight": 0.15,
        "description": "工作成果对业务/产品的可量化影响（用户数、收入、效率提升）",
    },
    {
        "key": "engineering_integrity",
        "label": "工程完整性",
        "weight": 0.10,
        "description": "代码质量、文档、测试、监控、CI/CD 等工程实践",
    },
    {
        "key": "company_prestige",
        "label": "公司含金量",
        "weight": 0.10,
        "description": "过往公司/团队在行业内的认可度，与目标岗位的相关性",
    },
]

LEVEL_MAP = {
    (85, 100): "扎实",
    (70, 84): "中上",
    (55, 69): "中等",
    (40, 54): "较浅",
    (0, 39): "不足",
}

RISK_RED_FLAGS = [
    "竞业限制",
    "学历造假嫌疑",
    "频繁跳槽（1年内3次以上）",
    "简历时间线矛盾",
    "行业黑名单",
    "入职即离职（<3个月）",
    "薪资期望严重偏离",
    "工作地点完全不可匹配",
]

RISK_YELLOW_FLAGS = [
    "上一份工作不满1年",
    "薪资期望偏高（>预算20%）",
    "技能栈部分不匹配",
    "行业转换跨度大",
    "异地需 relocation",
    "多份工作间有空窗期（>6个月）",
    "候选人来路不明",
    "信息源矛盾",
]


# ---------------------------------------------------------------------------
# LLM CoT 评分
# ---------------------------------------------------------------------------

def _build_cot_system_prompt() -> str:
    """构建 CoT 评分的系统提示词。"""
    dims_desc = "\n".join(
        f"{i+1}. {d['label']}（权重 {d['weight']:.0%}）：{d['description']}"
        for i, d in enumerate(SCORING_DIMENSIONS)
    )
    return f"""你是一名资深猎头评分专家（TTC 猎头公司），需要按以下 6 个维度对候选人简历进行评分。

评分维度（按 CoT 顺序依次评分）：
{dims_desc}

对每个维度，请：
- 给出分数（0-100），其中 85+ = 顶尖，70-84 = 优秀，55-69 = 一般，40-54 = 偏弱，<40 = 不足
- 从简历原文中引用 1-3 句话作为证据（必须引用原文，标记原文句子）
- 简述评分理由（1-2 句话）

全部 6 个维度评分完毕后，计算：
- overall_score：加权总分（保留 1 位小数）
- level：扎实（≥85）/ 中上（70-84）/ 中等（55-69）/ 较浅（40-54）/ 不足（<40）
- confidence：high（简历详尽，证据充分）/ medium（部分推断）/ low（信息不足，大量推断）
- risk_flags：检测红灯/黄灯信号
- verification_questions：面试中需要追问的 5-10 个问题
- company_analysis：一句话分析候选人过往公司的行业含金量

只返回 JSON，严格遵循以下结构：
{{
  "scores": [
    {{"dimension": "tech_depth", "score": 85, "evidence": ["原文句子1", "原文句子2"], "reason": "..."}},
    ...
  ],
  "overall_score": 82.5,
  "level": "中上",
  "confidence": "high",
  "risk_flags": [{{"flag": "上一份工作不满1年", "severity": "yellow", "detail": "..."}}],
  "verification_questions": ["问题1", "问题2", ...],
  "company_analysis": "..."
}}"""


def _build_candidate_text(candidate: Dict[str, Any]) -> str:
    """从候选人记录中组装可评分的文本。"""
    parts = []
    name = candidate.get("name", "")
    if name:
        parts.append(f"候选人姓名：{name}")

    raw_profile = candidate.get("raw_profile", {}) or {}
    if isinstance(raw_profile, str):
        try:
            raw_profile = json.loads(raw_profile)
        except Exception:
            raw_profile = {"raw_text": raw_profile}
    enriched_profile = candidate.get("enriched_profile", {}) or {}
    if isinstance(enriched_profile, str):
        try:
            enriched_profile = json.loads(enriched_profile)
        except Exception:
            enriched_profile = {}

    # 简历正文
    resume_text = (
        raw_profile.get("raw_text", "")
        or raw_profile.get("summary", "")
        or raw_profile.get("resume_text", "")
        or enriched_profile.get("raw_text", "")
        or candidate.get("raw_text", "")
    )
    if resume_text:
        parts.append(f"简历内容：\n{resume_text[:6000]}")

    # 富化证据
    evidence = candidate.get("evidence", []) or enriched_profile.get("evidence", [])
    if evidence:
        ev_lines = []
        for ev in evidence:
            if isinstance(ev, dict):
                ev_lines.append(
                    f"- [{ev.get('field', 'evidence')}] {ev.get('raw_text', '')[:500]}"
                    f"（来源：{ev.get('source_url', '无')}）"
                )
        if ev_lines:
            parts.append("补充信息：\n" + "\n".join(ev_lines))

    # source_types
    source_types = candidate.get("source_types", [])
    if source_types:
        parts.append(f"数据来源：{', '.join(str(s) for s in source_types)}")

    return "\n\n".join(parts)


def _parse_score_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """标准化 LLM 返回的评分结果。"""
    scores = raw.get("scores", [])
    dim_scores = {}
    evidence_binding = []
    for s in scores:
        key = s.get("dimension", "")
        dim_scores[key] = {
            "score": int(s.get("score", 0)),
            "evidence": s.get("evidence", []),
            "reason": s.get("reason", ""),
        }
        for ev in s.get("evidence", []):
            evidence_binding.append({
                "dimension": key,
                "dimension_label": next(
                    (d["label"] for d in SCORING_DIMENSIONS if d["key"] == key), key
                ),
                "evidence_text": ev,
                "score": int(s.get("score", 0)),
            })

    risk_flags = []
    for rf in raw.get("risk_flags", []):
        if isinstance(rf, str):
            risk_flags.append({"flag": rf, "severity": "unknown", "detail": ""})
        elif isinstance(rf, dict):
            risk_flags.append({
                "flag": rf.get("flag", ""),
                "severity": rf.get("severity", "yellow"),
                "detail": rf.get("detail", ""),
            })

    return {
        "overall_score": round(float(raw.get("overall_score", 0)), 1),
        "level": raw.get("level", "中等"),
        "confidence": raw.get("confidence", "medium"),
        "dimension_scores": dim_scores,
        "evidence_binding": evidence_binding,
        "risk_flags": risk_flags,
        "verification_questions": raw.get("verification_questions", []),
        "company_analysis": raw.get("company_analysis", ""),
    }


def _merge_median_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """将 3 次评分取中位数，差异 >10 分时标记需要人工审核。"""
    if len(results) < 2:
        return results[0] if results else {}

    overall_scores = [r["overall_score"] for r in results if r]
    median_overall = round(statistics.median(overall_scores), 1)
    score_range = max(overall_scores) - min(overall_scores)

    # 用最接近中位数的结果作为基础
    base = min(results, key=lambda r: abs(r["overall_score"] - median_overall))

    merged = dict(base)
    merged["overall_score"] = median_overall
    merged["score_range"] = round(score_range, 1)
    merged["needs_human_review"] = score_range > 10
    merged["individual_scores"] = overall_scores
    merged["runs"] = len(results)

    # 合并所有 risk_flags
    all_flags = {}
    for r in results:
        for rf in r.get("risk_flags", []):
            key = rf.get("flag", "")
            if key not in all_flags:
                all_flags[key] = rf
    merged["risk_flags"] = list(all_flags.values())

    # 合并所有 verification_questions（去重）
    seen_q = set()
    merged_questions = []
    for r in results:
        for q in r.get("verification_questions", []):
            if q not in seen_q:
                seen_q.add(q)
                merged_questions.append(q)
    merged["verification_questions"] = merged_questions

    return merged


def score_candidate_with_llm(
    candidate: Dict[str, Any], jd_fields: Dict[str, Any], runs: int = 3
) -> Dict[str, Any]:
    """使用 LLM CoT 对候选人进行 6 维评分，跑 3 次取中位数。

    Args:
        candidate: 候选人字典
        jd_fields: JD 结构化字段
        runs: 评分次数（默认 3，取中位数）

    Returns:
        结构化评分对象，包含 evidence_binding、risk_flags 等
    """
    if not is_llm_ready():
        logger.warning("LLM not ready, falling back to simple scoring")
        return _fallback_scoring(candidate, jd_fields)

    system_prompt = _build_cot_system_prompt()
    candidate_text = _build_candidate_text(candidate)

    position = jd_fields.get("position", "未知岗位")
    company = jd_fields.get("company", "未知公司")
    skills = jd_fields.get("skills", [])
    responsibilities = jd_fields.get("responsibilities", "")
    requirements = jd_fields.get("requirements", "")
    salary = jd_fields.get("salary", "")
    location = jd_fields.get("location", "")

    user_prompt = f"""请对以下候选人进行评分。

目标岗位信息：
- 公司：{company}
- 岗位：{position}
- 地点：{location}
- 薪资：{salary}
- 技能要求：{', '.join(skills) if skills else '未指定'}
- 职责：{responsibilities or '未指定'}
- 要求：{requirements or '未指定'}

{candidate_text}

请按 6 个维度依次评分，每个维度给出分数、证据（引用原文句子）和理由。只返回 JSON。"""

    results = []
    for i in range(runs):
        try:
            raw = call_llm_json(system_prompt, user_prompt, temperature=0.0)
            parsed = _parse_score_result(raw)
            results.append(parsed)
            logger.info(
                "LLM scoring run %d/%d for %s: overall=%.1f level=%s",
                i + 1, runs, candidate.get("name", "unknown"),
                parsed["overall_score"], parsed["level"],
            )
        except Exception as e:
            logger.warning("LLM scoring run %d failed: %s", i + 1, e)

    if not results:
        logger.warning("All LLM scoring runs failed, falling back to simple scoring")
        return _fallback_scoring(candidate, jd_fields)

    merged = _merge_median_results(results)
    logger.info(
        "Final score for %s: %.1f (range=%.1f, runs=%d, needs_review=%s)",
        candidate.get("name", "unknown"),
        merged["overall_score"],
        merged.get("score_range", 0),
        merged.get("runs", 0),
        merged.get("needs_human_review", False),
    )
    return merged


# ---------------------------------------------------------------------------
# 简单加权兜底
# ---------------------------------------------------------------------------

def _fallback_scoring(candidate: Dict[str, Any], jd_fields: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 不可用时的简单加权兜底评分。"""
    jd_alignment = candidate.get("jd_alignment_score", 0) or 0
    gold = candidate.get("gold_score")
    if gold in (None, "", 0, 0.0):
        overall = round(float(jd_alignment), 1)
    else:
        overall = round(float(jd_alignment) * 0.6 + float(gold) * 0.4, 1)

    level = next(
        (label for (lo, hi), label in LEVEL_MAP.items() if lo <= overall <= hi),
        "中等",
    )

    return {
        "overall_score": overall,
        "level": level,
        "confidence": "low",
        "dimension_scores": {
            "tech_depth": {"score": overall, "evidence": [], "reason": "兜底评分，非 LLM 分步评分"},
        },
        "evidence_binding": [],
        "risk_flags": candidate.get("risk_flags", []) or [],
        "verification_questions": [
            f"请确认候选人技能是否匹配 {jd_fields.get('position', '岗位')} 的要求",
            "请与候选人确认当前薪资与期望",
            "请了解候选人近期是否有换工作意向",
        ],
        "company_analysis": "",
        "score_range": 0,
        "needs_human_review": False,
        "runs": 1,
        "_fallback": True,
    }


# ---------------------------------------------------------------------------
# 统一的评分入口
# ---------------------------------------------------------------------------

def score_candidate(
    candidate: Dict[str, Any], jd_fields: Dict[str, Any], use_llm: bool = True
) -> Dict[str, Any]:
    """对单个候选人进行综合评分。

    优先使用 LLM CoT 分步评分（如果 LLM 可用），否则使用简单加权兜底。
    评分结果会写回到 candidate 字典中。

    Args:
        candidate: 候选人字典
        jd_fields: JD 结构化字段
        use_llm: 是否尝试使用 LLM 评分

    Returns:
        更新后的 candidate 字典（含评分字段）
    """
    if use_llm and is_llm_ready():
        result = score_candidate_with_llm(candidate, jd_fields)
    else:
        result = _fallback_scoring(candidate, jd_fields)

    # 将评分结果写回 candidate
    candidate["overall_score"] = result["overall_score"]
    candidate["risk_flags"] = result.get("risk_flags", [])
    candidate["dimension_scores"] = result.get("dimension_scores", {})
    candidate["evidence_binding"] = result.get("evidence_binding", [])
    candidate["verification_questions"] = result.get("verification_questions", [])
    candidate["level"] = result.get("level", "中等")
    candidate["confidence"] = result.get("confidence", "medium")
    candidate["company_analysis"] = result.get("company_analysis", "")
    candidate["needs_human_review"] = result.get("needs_human_review", False)
    candidate["score_range"] = result.get("score_range", 0)

    return candidate


# ---------------------------------------------------------------------------
# 合规检测
# ---------------------------------------------------------------------------

def detect_compliance_issues(candidate: Dict[str, Any]) -> List[Dict[str, Any]]:
    """检测候选人的合规/数据可信度问题。

    返回需要触发合规仲裁的 issue 列表。
    """
    issues = []
    risk_flags = candidate.get("risk_flags", []) or []
    source_types = candidate.get("source_types", []) or []

    # 检查红灯信号
    red_flags = [rf for rf in risk_flags if rf.get("severity") == "red" or
                 any(r in str(rf) for r in RISK_RED_FLAGS)]
    if red_flags:
        issues.append({
            "type": "red_flag_present",
            "severity": "high",
            "detail": f"候选人存在红灯信号：{red_flags}",
            "flags": red_flags,
        })

    # 候选人来路不明
    if not source_types or source_types == ["unknown"]:
        issues.append({
            "type": "untrusted_source",
            "severity": "medium",
            "detail": "候选人数据来源不明确或不可信",
        })

    # 数据冲突检测：多来源信息矛盾
    if len(source_types) > 1:
        profile = candidate.get("raw_profile", {}) or {}
        enriched = candidate.get("enriched_profile", {}) or {}
        if profile.get("company") and enriched.get("company"):
            if profile.get("company") != enriched.get("company"):
                issues.append({
                    "type": "data_conflict",
                    "severity": "medium",
                    "detail": f"多来源信息矛盾：当前公司 {profile.get('company')} vs {enriched.get('company')}",
                })

    # 竞业限制检测
    raw_text = str(candidate.get("raw_profile", {}))
    if any(kw in raw_text for kw in ["竞业", "non-compete", "竞业限制", "保密协议有效期"]):
        issues.append({
            "type": "non_compete_concern",
            "severity": "high",
            "detail": "简历或资料中涉及竞业限制相关信息",
        })

    return issues


# ---------------------------------------------------------------------------
# 话术生成
# ---------------------------------------------------------------------------

def generate_talking_points(
    candidate: Dict[str, Any], jd_fields: Dict[str, Any]
) -> List[str]:
    """生成猎头电话话术要点。"""
    name = candidate.get("name", "候选人")
    position = jd_fields.get("position", "岗位")
    company = jd_fields.get("company", "客户")
    level = candidate.get("level", "")
    verification_questions = candidate.get("verification_questions", [])
    risk_flags = candidate.get("risk_flags", []) or []

    points = [
        f"向 {name} 介绍 {company} 的 {position} 机会",
        f"确认当前状态：在职/看机会/期望薪资/地点偏好",
        f"了解对 {position} 角色的匹配度和兴趣度",
        "了解近期是否有换工作意向",
    ]

    # 添加 AI 生成的追问题
    if verification_questions:
        points.append("—— AI 建议追问 ——")
        for q in verification_questions[:5]:
            points.append(f"追问：{q}")

    # 有风险信号时提示
    if risk_flags:
        yellow_flags = [
            rf.get("flag", str(rf))
            for rf in risk_flags
            if rf.get("severity") != "red"
        ]
        if yellow_flags:
            points.append(f"⚠️ 注意核实：{'; '.join(yellow_flags[:3])}")

    if level:
        points.insert(0, f"AI 评级：{level}（{candidate.get('overall_score', '?')} 分）")

    return points


def build_call_script(
    candidate: Dict[str, Any], jd_fields: Dict[str, Any]
) -> str:
    """生成电话开场白话术。"""
    name = candidate.get("name", "候选人")
    company = jd_fields.get("company", "客户") or "客户"
    position = jd_fields.get("position", "岗位") or "岗位"
    return (
        f"{name} 您好，我是 TTC 猎头顾问。我们这边有一个 {company} 的 {position} 机会，"
        f"想跟您简单聊聊是否感兴趣。您现在方便吗？"
    )
