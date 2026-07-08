"""
特征工程 - 从简历/JD 文本提取数值特征
"""
import numpy as np
from typing import List, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """特征提取器"""

    def __init__(self, use_embedding: bool = False):
        self.use_embedding = use_embedding
        self.tfidf = TfidfVectorizer(max_features=500, ngram_range=(1, 2))
        self.scaler = StandardScaler()
        self._fitted = False

    def _combine_text(self, candidate: dict, job: dict = None) -> str:
        """合并文本用于向量化"""
        skills = candidate.get("skills", [])
        if isinstance(skills, str): skills = skills.split(",")
        parts = [
            candidate.get("current_role", ""),
            candidate.get("current_company", ""),
            " ".join(skills),
            candidate.get("education", ""),
            str(candidate.get("summary", ""))[:200],
        ]
        if job:
            j_skills = job.get("skills", job.get("required_skills", []))
            if isinstance(j_skills, str): j_skills = j_skills.split(",")
            parts.extend([job.get("title", ""), " ".join(j_skills)])
        return " ".join(filter(None, parts))

    def _extract_single(self, cand: dict, job: dict = None) -> list:
        """提取单条样本的结构化特征"""
        exp = cand.get("years_experience", 0) or 0
        skills = cand.get("skills", [])
        if isinstance(skills, str): skills = skills.split(",")
        
        feats = [
            exp / 20.0,
            min(len(skills) / 20.0, 1.0),
            1.0 if "硕士" in str(cand.get("education", "")) or "博士" in str(cand.get("education", "")) else 0.0,
            1.0 if "985" in str(cand.get("education", "")) or "211" in str(cand.get("education", "")) else 0.0,
        ]
        
        if job:
            j_skills = job.get("skills", job.get("required_skills", []))
            if isinstance(j_skills, str): j_skills = j_skills.split(",")
            match = len(set(skills) & set(j_skills))
            total = max(len(j_skills), 1)
            feats.extend([
                match / total,
                min(exp / max(job.get("min_years_experience", 1), 1), 2.0),
            ])
        return feats

    def extract_structural_batch(self, candidates: List[dict], jobs: Optional[List[dict]] = None) -> np.ndarray:
        """批量提取结构化特征"""
        features = []
        for i, cand in enumerate(candidates):
            job = jobs[i] if jobs and i < len(jobs) else None
            features.append(self._extract_single(cand, job))
        return np.array(features) if features else np.empty((0, 0))

    def fit(self, candidates: List[dict], jobs: Optional[List[dict]] = None):
        """拟合 TF-IDF 和 Scaler"""
        texts = [self._combine_text(c) for c in candidates]
        if texts:
            self.tfidf.fit(texts)
        X_struct = self.extract_structural_batch(candidates, jobs)
        if X_struct.shape[0] > 1:
            self.scaler.fit(X_struct)
        self._fitted = True
        return self

    def transform(self, candidates: List[dict], jobs: Optional[List[dict]] = None) -> np.ndarray:
        """提取特征向量"""
        texts = [self._combine_text(c, jobs[i] if jobs and i < len(jobs) else None) for i, c in enumerate(candidates)]
        tfidf_feats = self.tfidf.transform(texts).toarray()
        struct_feats = self.extract_structural_batch(candidates, jobs)
        if struct_feats.shape[0] > 0 and struct_feats.shape[1] > 0:
            struct_feats = self.scaler.transform(struct_feats)
        return np.hstack([tfidf_feats, struct_feats]) if struct_feats.shape[1] > 0 else tfidf_feats


class SkillOverlapCalculator:
    """纯技能重叠计算器"""

    @staticmethod
    def overlap(candidate_skills: list, job_skills: list) -> dict:
        c_set = set(s.lower().strip() for s in candidate_skills if s)
        j_set = set(s.lower().strip() for s in job_skills if s)
        matched = c_set & j_set
        missing = j_set - c_set
        return {
            "matched": sorted(matched), "missing": sorted(missing),
            "overlap_rate": round(len(matched) / max(len(j_set), 1), 4),
            "coverage_rate": round(len(matched) / max(len(c_set), 1), 4),
        }

    @staticmethod
    def compute_score(candidate_skills: list, job_skills: list) -> float:
        return SkillOverlapCalculator.overlap(candidate_skills, job_skills)["overlap_rate"]
