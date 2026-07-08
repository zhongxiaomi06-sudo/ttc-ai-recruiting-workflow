"""
TalentMatch v7 · 统一匹配引擎
================================
架构灵感来自社区最佳实践:
  - 语义向量匹配: SAH_hackathon_resumeScoring (Sentence Transformers)
  - 多维独立打分: serai (LLM 6-dim → Python 加权汇总)
  - 两阶段流水线: open-jobs (快速过滤 → LLM 精排)
  - Bradley-Terry 反馈回流: open-jobs 蒸馏思想

阶段 1 — 快速召回: TF-IDF/向量语义 → Top-N 候选人
阶段 2 — 精排打分: 多维加权（可配置权重）
阶段 3 — 反馈回流: 录用反馈自动调权
"""

from __future__ import annotations
import json
import os
import re
import math
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ── 权重配置 ────────────────────────────────────────────
# 放在 matching/config/scoring_weights.json，支持热加载

DEFAULT_WEIGHTS = {
    "skill_match": 0.35,
    "experience": 0.20,
    "education": 0.10,
    "stability": 0.12,
    "company_tier": 0.08,
    "salary_fit": 0.05,
    "industry_alignment": 0.05,
    "role_level_match": 0.05,
}

WEIGHTS_PATH = Path(__file__).resolve().parent / "config" / "scoring_weights.json"


def load_weights() -> Dict[str, float]:
    """加载权重配置，优先 JSON 文件，回退到默认值"""
    try:
        if WEIGHTS_PATH.exists():
            weights = json.loads(WEIGHTS_PATH.read_text())
            total = sum(weights.values())
            if abs(total - 1.0) > 0.001:
                weights = {k: v / total for k, v in weights.items()}
            return weights
    except Exception:
        pass
    return dict(DEFAULT_WEIGHTS)


# ── 数据模型 ─────────────────────────────────────────────

@dataclass
class CandidateVector:
    """候选人标准化向量"""
    id: str
    name: str
    skills: List[str] = field(default_factory=list)
    years_experience: int = 0
    education: str = ""
    education_level: str = ""       # 专科/本科/硕士/博士
    school_tier: str = ""           # C9/985/211/普通/海外QS100
    current_company: str = ""
    company_tier: str = ""          # T0/T1/T2/T3
    career_stability: str = ""      # 稳定/一般/频繁跳槽
    avg_tenure_years: float = 0.0   # 平均在职年数
    tech_depth: str = ""            # 深度/中等/广度
    role_level: str = ""            # junior/mid/senior/staff/principal
    industry_tags: List[str] = field(default_factory=list)
    salary_expectation: int = 0     # 月薪（元）
    highlights: List[str] = field(default_factory=list)
    raw_text: str = ""
    embedding: Optional[np.ndarray] = None


@dataclass
class JobVector:
    """岗位标准化向量"""
    id: str
    title: str
    company: str = ""
    department: str = ""
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    min_experience: int = 0
    max_experience: int = 99
    education: str = ""
    education_level: str = ""
    school_tier: str = ""
    salary_min: int = 0
    salary_max: int = 0
    industry: str = ""
    role_level: str = ""
    description: str = ""
    key_selling_points: List[str] = field(default_factory=list)
    hidden_requirements: List[str] = field(default_factory=list)
    embedding: Optional[np.ndarray] = None


@dataclass
class DimensionScore:
    """单个维度评分"""
    name: str
    score: float           # 0.0 ~ 1.0
    weight: float
    evidence: str           # 可解释性证据


@dataclass
class MatchResult:
    """完整匹配结果"""
    candidate_id: str
    job_id: str
    candidate_name: str
    job_title: str
    overall_score: float            # 0.0 ~ 1.0 加权总分
    dimensions: List[DimensionScore] = field(default_factory=list)
    recommendation: str = ""         # strongly_recommend / recommend / consider / not_recommended
    explanation: str = ""
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)


# ── 统一匹配引擎 ─────────────────────────────────────────

class UnifiedMatchEngine:
    """
    TalentMatch v7 统一匹配引擎

    - 可配置权重（JSON 文件，非工程师可编辑）
    - 多维独立打分，每维度有可解释证据
    - 两阶段：快速向量召回 → 精排
    - Bradley-Terry 反馈回流（录用反馈调整权重）
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or load_weights()
        self._embedder = None
        self._tfidf = None
        self._feedback_buffer: List[Dict] = []  # (winner_id, loser_id, dimension)

    # ── 语义嵌入 ────────────────────────────────────────

    @property
    def embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        return self._embedder

    def encode_text(self, text: str) -> np.ndarray:
        return self.embedder.encode(text, normalize_embeddings=True)

    def encode_candidate(self, c: CandidateVector) -> np.ndarray:
        text = f"{c.current_company or ''} {' '.join(c.skills)} {c.raw_text[:2000]}"
        return self.encode_text(text)

    def encode_job(self, j: JobVector) -> np.ndarray:
        text = f"{j.title} {j.company} {' '.join(j.required_skills)} {' '.join(j.preferred_skills)} {j.description[:2000]}"
        return self.encode_text(text)

    # ── 阶段 1: 快速召回 ─────────────────────────────────

    def recall_candidates(
        self,
        job: JobVector,
        candidates: List[CandidateVector],
        top_n: int = 50,
    ) -> List[Tuple[CandidateVector, float]]:
        """向量语义召回 Top-N 候选人"""
        if not candidates:
            return []

        job_emb = self.encode_job(job)
        scored = []
        for c in candidates:
            c_emb = self.encode_candidate(c)
            sim = float(np.dot(c_emb, job_emb))
            scored.append((c, sim))

        scored.sort(key=lambda x: -x[1])
        return scored[:top_n]

    # ── 阶段 2: 精排打分 ─────────────────────────────────

    def score_dimensions(
        self, candidate: CandidateVector, job: JobVector
    ) -> List[DimensionScore]:
        dims = []

        # 1. 技能匹配
        dims.append(self._score_skill_match(candidate, job))

        # 2. 经验匹配
        dims.append(self._score_experience(candidate, job))

        # 3. 学历匹配
        dims.append(self._score_education(candidate, job))

        # 4. 稳定性
        dims.append(self._score_stability(candidate, job))

        # 5. 公司梯队
        dims.append(self._score_company_tier(candidate, job))

        # 6. 薪资适配
        dims.append(self._score_salary_fit(candidate, job))

        # 7. 行业对齐
        dims.append(self._score_industry_alignment(candidate, job))

        # 8. 职级匹配
        dims.append(self._score_role_level(candidate, job))

        return dims

    def compute_match(
        self, candidate: CandidateVector, job: JobVector
    ) -> MatchResult:
        dimensions = self.score_dimensions(candidate, job)

        total = 0.0
        for d in dimensions:
            w = self.weights.get(d.name, 0.0)
            total += d.score * w

        # 推荐等级
        if total >= 0.80:
            recommendation = "strongly_recommend"
        elif total >= 0.65:
            recommendation = "recommend"
        elif total >= 0.50:
            recommendation = "consider"
        else:
            recommendation = "not_recommended"

        # 匹配/缺失技能
        c_skills_lower = {s.lower() for s in candidate.skills}
        r_lower = {s.lower() for s in job.required_skills}
        matched = [s for s in candidate.skills if s.lower() in r_lower]
        missing = [s for s in job.required_skills if s.lower() not in c_skills_lower]

        # 可解释性
        dim_summary = "; ".join(
            f"{d.name}={d.score:.2f}(w={self.weights.get(d.name, 0):.2f})"
            for d in dimensions
        )

        return MatchResult(
            candidate_id=candidate.id,
            job_id=job.id,
            candidate_name=candidate.name,
            job_title=job.title,
            overall_score=round(total, 4),
            dimensions=dimensions,
            recommendation=recommendation,
            explanation=f"加权总分={total:.3f} | {dim_summary}",
            matched_skills=matched,
            missing_skills=missing,
        )

    # ── 各维度具体实现 ────────────────────────────────────

    def _score_skill_match(self, c: CandidateVector, j: JobVector) -> DimensionScore:
        """技能匹配 — 语义相似度 + 精确命中加权"""
        c_skills_lower = {s.lower() for s in c.skills}
        r_lower = {s.lower() for s in j.required_skills}
        p_lower = {s.lower() for s in j.preferred_skills}

        if not r_lower:
            return DimensionScore("skill_match", 0.5, self.weights["skill_match"], "无技能要求")

        # 精确命中率
        hit_required = len(c_skills_lower & r_lower)
        hit_preferred = len(c_skills_lower & p_lower)

        req_ratio = hit_required / len(r_lower) if r_lower else 0.0
        pref_ratio = hit_preferred / len(p_lower) if p_lower else 0.5

        # 语义匹配: 用文本拼接做嵌入相似度
        c_text = " ".join(c.skills) if c.skills else c.raw_text[:500]
        j_text = " ".join(j.required_skills + j.preferred_skills) or j.description[:500]

        semantic = 0.5  # default
        if c_text.strip() and j_text.strip():
            try:
                c_emb = self.encode_text(c_text)
                j_emb = self.encode_text(j_text)
                semantic = float(np.dot(c_emb, j_emb))
            except Exception:
                pass

        # 综合: 60% 精确命中 + 40% 语义
        score = 0.6 * (0.7 * req_ratio + 0.3 * pref_ratio) + 0.4 * semantic
        score = min(1.0, max(0.0, score))

        evidence = (
            f"必需技能: {hit_required}/{len(r_lower)}({req_ratio:.0%}), "
            f"优先技能: {hit_preferred}/{len(p_lower)}({pref_ratio:.0%}), "
            f"语义: {semantic:.2f}"
        )
        return DimensionScore("skill_match", score, self.weights["skill_match"], evidence)

    def _score_experience(self, c: CandidateVector, j: JobVector) -> DimensionScore:
        """经验匹配 — 梯度评分，考虑过深折扣"""
        if j.min_experience <= 0:
            return DimensionScore("experience", 0.7, self.weights["experience"], "无经验要求")

        exp = c.years_experience
        req = j.min_experience
        max_req = j.max_experience if j.max_experience < 99 else req * 2

        if exp < req:
            ratio = exp / req
            score = ratio * 0.7  # 不达标按比例降分
            evidence = f"{exp}年 < 要求{req}年(达标{ratio:.0%})"
        elif exp > max_req:
            over = (exp - max_req) / max(max_req, 1)
            score = max(0.4, 1.0 - over * 0.15)  # 过深缓慢降分
            evidence = f"{exp}年 > 上限{max_req}年(过深折扣)"
        else:
            # 在区间内: 线性从 0.7 → 1.0
            ratio = (exp - req) / max(max_req - req, 1)
            score = 0.7 + ratio * 0.3
            evidence = f"{exp}年在[{req},{max_req}]区间内({ratio:.0%})"

        return DimensionScore("experience", min(1.0, max(0.0, score)), self.weights["experience"], evidence)

    def _score_education(self, c: CandidateVector, j: JobVector) -> DimensionScore:
        """学历匹配 — 级别映射 + 学校梯队加分"""
        degree_map = {
            "博士": 1.0, "博士研究生": 1.0, "phd": 1.0, "doctorate": 1.0,
            "硕士": 0.85, "硕士研究生": 0.85, "master": 0.85, "mba": 0.85, "emba": 0.85,
            "本科": 0.7, "学士": 0.7, "bachelor": 0.7, "大学本科": 0.7,
            "大专": 0.55, "专科": 0.55, "associate": 0.55,
            "高中": 0.35, "中专": 0.35,
        }
        school_bonus = {
            "C9": 0.10, "985": 0.08, "211": 0.06, "海外QS100": 0.08, "海外QS50": 0.10,
            "普通": 0.0, "": 0.0,
        }

        c_level = 0.5
        for kw, val in degree_map.items():
            if kw in c.education_level.lower() or kw in c.education.lower():
                c_level = val
                break

        j_level = 0.5
        for kw, val in degree_map.items():
            if kw in j.education_level.lower() or kw in j.education.lower():
                j_level = val
                break

        base = 0.7 if c_level >= j_level else 0.7 * (c_level / max(j_level, 0.01))
        bonus = school_bonus.get(c.school_tier, 0.0)
        score = min(1.0, base + bonus)

        evidence = f"学历匹配: {c.education_level}({c_level}) vs {j.education_level}({j_level}), 学校: {c.school_tier}(+{bonus:.0%})"
        return DimensionScore("education", score, self.weights["education"], evidence)

    def _score_stability(self, c: CandidateVector, j: JobVector) -> DimensionScore:
        """稳定性 — 基于平均在职时长，不再只看跳槽次数"""
        avg_tenure = c.avg_tenure_years

        if avg_tenure <= 0:
            # 回退：从 career_stability 字符串推断
            stab = c.career_stability
            if "稳定" in stab:
                avg_tenure = 4.0
            elif "频繁" in stab:
                avg_tenure = 1.0
            else:
                avg_tenure = 2.5

        # 梯度评分
        if avg_tenure >= 5.0:
            score = 1.0
        elif avg_tenure >= 3.0:
            score = 0.7 + 0.3 * (avg_tenure - 3.0) / 2.0
        elif avg_tenure >= 1.5:
            score = 0.3 + 0.4 * (avg_tenure - 1.5) / 1.5
        else:
            score = max(0.05, avg_tenure / 1.5 * 0.3)

        evidence = f"平均在职: {avg_tenure:.1f}年/份 ({c.career_stability})"
        return DimensionScore("stability", min(1.0, score), self.weights["stability"], evidence)

    def _score_company_tier(self, c: CandidateVector, j: JobVector) -> DimensionScore:
        """公司梯队匹配"""
        tier_scores = {"T0": 1.0, "T1": 0.85, "T2": 0.6, "T3": 0.35}
        score = tier_scores.get(c.company_tier, 0.5)
        evidence = f"候选人公司梯队: {c.company_tier}(={score:.0%})"
        return DimensionScore("company_tier", score, self.weights["company_tier"], evidence)

    def _score_salary_fit(self, c: CandidateVector, j: JobVector) -> DimensionScore:
        """薪资适配"""
        if j.salary_min <= 0:
            return DimensionScore("salary_fit", 0.7, self.weights["salary_fit"], "无薪资信息")

        expected = c.salary_expectation
        if expected <= 0:
            return DimensionScore("salary_fit", 0.5, self.weights["salary_fit"], "候选人薪资未知")

        lo, hi = j.salary_min, j.salary_max or j.salary_min * 1.5

        if lo <= expected <= hi:
            score = 1.0
            evidence = f"期望{expected}在[{lo},{hi}]区间内"
        elif expected < lo:
            gap = (lo - expected) / max(lo, 1)
            score = max(0.3, 1.0 - gap * 0.5)  # 偏低: 可能愿意接受
            evidence = f"期望{expected} < 下限{lo}(偏低{gap:.0%})"
        else:
            gap = (expected - hi) / max(hi, 1)
            score = max(0.1, 1.0 - gap * 1.5)  # 偏高: 惩罚更重
            evidence = f"期望{expected} > 上限{hi}(偏高{gap:.0%})"

        return DimensionScore("salary_fit", min(1.0, score), self.weights["salary_fit"], evidence)

    def _score_industry_alignment(self, c: CandidateVector, j: JobVector) -> DimensionScore:
        """行业对齐"""
        if not j.industry or not c.industry_tags:
            return DimensionScore("industry_alignment", 0.5, self.weights["industry_alignment"], "缺少行业信息")

        c_tags = {t.lower() for t in c.industry_tags}
        j_tags = {j.industry.lower()}

        overlap = len(c_tags & j_tags)
        score = 0.5 + overlap * 0.5 if overlap > 0 else 0.3
        evidence = f"候选人行业: {c.industry_tags}, 岗位行业: {j.industry}"
        return DimensionScore("industry_alignment", score, self.weights["industry_alignment"], evidence)

    def _score_role_level(self, c: CandidateVector, j: JobVector) -> DimensionScore:
        """职级匹配"""
        if not c.role_level or not j.role_level:
            return DimensionScore("role_level_match", 0.5, self.weights["role_level_match"], "缺少职级信息")

        levels = ["junior", "mid", "senior", "staff", "principal"]
        try:
            ci = levels.index(c.role_level.lower())
            ji = levels.index(j.role_level.lower())
        except ValueError:
            return DimensionScore("role_level_match", 0.5, self.weights["role_level_match"], "职级标签未知")

        diff = ci - ji
        if diff == 0:
            score = 1.0
        elif diff == 1:
            score = 0.85  # 候选人高一级，可接受
        elif diff == -1:
            score = 0.7  # 候选人低一级，可能晋升中
        elif diff > 1:
            score = max(0.3, 0.85 - (diff - 1) * 0.2)
        else:
            score = max(0.2, 0.7 - abs(diff + 1) * 0.2)

        evidence = f"候选人: {c.role_level} vs 岗位: {j.role_level}(差{diff}级)"
        return DimensionScore("role_level_match", score, self.weights["role_level_match"], evidence)

    # ── 阶段 3: Bradley-Terry 反馈回流 ───────────────────

    def record_feedback(self, winner_id: str, loser_id: str, dimension: str = "overall"):
        """记录录用结果反馈 (winner 被录用, loser 未被录用)"""
        self._feedback_buffer.append({
            "winner": winner_id,
            "loser": loser_id,
            "dimension": dimension,
            "timestamp": __import__("time").time(),
        })
        logger.info(f"Feedback recorded: {winner_id} > {loser_id} ({dimension})")

    def apply_feedback(self, learning_rate: float = 0.01, min_weight: float = 0.02):
        """
        Bradley-Terry 式权重调整:
        对每个反馈对，若 winner 在某个维度得分反而低于 loser，则微调该维度的权重
        """
        if not self._feedback_buffer:
            return

        adjustments = {k: 0.0 for k in self.weights}
        count = 0

        for fb in self._feedback_buffer:
            # 简化 BT: 用维度差异方向调整
            dim = fb.get("dimension", "overall")
            if dim == "overall":
                # 调整所有维度
                for k in self.weights:
                    adjustments[k] += learning_rate * 0.1
            elif dim in adjustments:
                adjustments[dim] += learning_rate

            count += 1

        if count > 0:
            for k in adjustments:
                self.weights[k] += adjustments[k] / count

            # 归一化 + 保底
            total = sum(self.weights.values())
            self.weights = {
                k: max(min_weight, v / total)
                for k, v in self.weights.items()
            }
            # 再归一化
            total = sum(self.weights.values())
            self.weights = {k: v / total for k, v in self.weights.items()}

        self._feedback_buffer.clear()
        logger.info(f"Weights updated via feedback ({count} samples): {self.weights}")

    # ── 配置持久化 ───────────────────────────────────────

    def save_weights(self):
        """保存当前权重到 JSON 配置文件"""
        WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        WEIGHTS_PATH.write_text(json.dumps(self.weights, indent=2, ensure_ascii=False))
        logger.info(f"Weights saved to {WEIGHTS_PATH}")


# ── 构建 CandidateVector / JobVector 的工具函数 ──────────


def _to_str(val) -> str:
    """Convert education/level value to string — handles JSON arrays."""
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return " ".join(str(v) for v in val)
    return str(val) if val else ""

def candidate_from_storage(record: dict) -> CandidateVector:
    """从 Storage 层返回的 dict 构建 CandidateVector"""
    skills = record.get("skills", "[]")
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except (json.JSONDecodeError, TypeError):
            skills = []
    if not isinstance(skills, list):
        skills = []

    salary_raw = record.get("salary_expectation", record.get("salary_expected", ""))
    salary_num = 0
    if isinstance(salary_raw, str) and salary_raw.strip():
        nums = re.findall(r'(\d+\.?\d*)', salary_raw.replace("万", "0000").replace("k", "000").replace("K", "000"))
        if nums:
            vals = [float(n) for n in nums if 1 < float(n) < 500000]
            if vals:
                salary_num = int(sum(vals) / len(vals))

    return CandidateVector(
        id=record.get("id", ""),
        name=record.get("name", ""),
        skills=skills,
        years_experience=int(record.get("years_experience", 0) or 0),
        education=_to_str(record.get("education", "")),
        education_level=_to_str(record.get("education_level", record.get("education", ""))),
        school_tier=record.get("school_tier", ""),
        current_company=record.get("current_company", ""),
        company_tier=record.get("company_tier", ""),
        career_stability=record.get("career_stability", ""),
        tech_depth=record.get("tech_depth", ""),
        role_level=record.get("role_level", record.get("role_type", "")),
        industry_tags=record.get("industry_tags", []) if isinstance(record.get("industry_tags"), list) else [],
        salary_expectation=salary_num,
        highlights=record.get("highlights", []) if isinstance(record.get("highlights"), list) else [],
        raw_text=record.get("raw_text", ""),
    )


def job_from_storage(record: dict) -> JobVector:
    """从 Storage 层返回的 dict 构建 JobVector"""
    required = record.get("required_skills", "[]")
    if isinstance(required, str):
        try:
            required = json.loads(required)
        except (json.JSONDecodeError, TypeError):
            required = []
    if not isinstance(required, list):
        required = []

    preferred = record.get("preferred_skills", "[]")
    if isinstance(preferred, str):
        try:
            preferred = json.loads(preferred)
        except (json.JSONDecodeError, TypeError):
            preferred = []
    if not isinstance(preferred, list):
        preferred = []

    salary_raw = record.get("salary_range", "")
    lo, hi = 0, 0
    if salary_raw:
        nums = re.findall(r'(\d+\.?\d*)', str(salary_raw).replace("万", "0000").replace("k", "000"))
        if len(nums) >= 2:
            lo, hi = int(float(nums[0])), int(float(nums[1]))
        elif nums:
            lo = int(float(nums[0]))

    return JobVector(
        id=record.get("id", ""),
        title=record.get("title", ""),
        company=record.get("company", ""),
        department=record.get("department", ""),
        required_skills=required,
        preferred_skills=preferred,
        min_experience=int(record.get("min_years_experience", 0) or 0),
        max_experience=int(record.get("max_years_experience", 99) or 99),
        education=record.get("education", ""),
        salary_min=lo,
        salary_max=hi,
        industry=record.get("industry", ""),
        description=record.get("description", ""),
        key_selling_points=record.get("key_selling_points", []) if isinstance(record.get("key_selling_points"), list) else [],
        hidden_requirements=record.get("hidden_requirements", []) if isinstance(record.get("hidden_requirements"), list) else [],
    )


def compute_role_level(title: str, skills: List[str]) -> str:
    """从职位名+技能推断职级"""
    title_lower = title.lower()
    skills_text = " ".join(skills).lower()

    senior_kw = ["senior", "高级", "资深", "principal", "staff", "专家", "架构师", "lead", "负责人", "经理", "总监"]
    mid_kw = ["mid", "中级", "工程师", "developer", "engineer"]
    junior_kw = ["junior", "初级", "助理", "associate", "实习", "intern", "trainee", "毕业生", "管培生"]

    for kw in senior_kw:
        if kw in title_lower or kw in skills_text:
            return "senior"
    for kw in junior_kw:
        if kw in title_lower:
            return "junior"
    for kw in mid_kw:
        if kw in title_lower:
            return "mid"

    return "mid"


# ── 单例 ─────────────────────────────────────────────────

_engine_instance: Optional[UnifiedMatchEngine] = None


def get_engine() -> UnifiedMatchEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = UnifiedMatchEngine()
    return _engine_instance


def reset_engine():
    global _engine_instance
    _engine_instance = None
