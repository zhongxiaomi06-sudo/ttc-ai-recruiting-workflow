"""
ML 模型集成到现有匹配引擎
在 matching/rules/ 下添加 MLScoringRule
"""
from __future__ import annotations
import json, os, joblib
from pathlib import Path
from typing import Optional, List
import numpy as np
from loguru import logger

# 导入现有规则系统
import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from matching.rules.base import MatchRule, RuleResult


class MLScoringRule(MatchRule):
    """
    ML 模型评分规则
    集成训练好的 XGBoost/RF/LR 模型，
    输出 0-1 的匹配分数作为综合参考
    """
    
    name = "ml_scoring"
    weight = 0.4  # 与规则引擎混合
    
    def __init__(self, model_path: Optional[str] = None):
        super().__init__()
        self.model = None
        self.model_path = model_path
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
    
    def load_model(self, path: str):
        """加载训练好的模型（支持单个 model 或 pipeline dict）"""
        try:
            loaded = joblib.load(path)
            if isinstance(loaded, dict) and 'model' in loaded:
                self.model = loaded['model']
                self.extractor = loaded.get('extractor')
                logger.info(f"Loaded ML pipeline from {path} (model={type(self.model).__name__})")
            else:
                self.model = loaded
                self.extractor = None
                logger.info(f"Loaded ML model from {path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
    
    def find_model(self) -> Optional[str]:
        """自动查找最新训练模型"""
        model_dir = Path(os.path.dirname(__file__)) / ".." / ".." / "training" / "models"
        if model_dir.exists():
            models = sorted(model_dir.glob("*.joblib"))
            if models:
                return str(models[-1])
        return None
    
    def _extract_features(self, candidate: dict, job: dict) -> np.ndarray:
        """提取模型所需特征"""
        # 技能
        c_skills = candidate.get("skills", [])
        if isinstance(c_skills, str):
            c_skills = c_skills.split(",")
        c_set = set(s.lower().strip() for s in c_skills if s)
        
        j_skills = job.get("required_skills", job.get("skills", []))
        if isinstance(j_skills, str):
            j_skills = j_skills.split(",")
        j_set = set(s.lower().strip() for s in j_skills if s)
        
        matched = len(c_set & j_set)
        missing = len(j_set - c_set)
        overlap_rate = matched / max(matched + missing, 1)
        
        # 经验
        c_exp = candidate.get("years_experience", 0) or 0
        j_min = job.get("min_years_experience", 0) or 0
        j_max = job.get("max_years_experience", 20) or 20
        exp_fit = 1.0 if j_min <= c_exp <= j_max else max(0, 1.0 - abs(c_exp - j_min) / 10)
        
        # 教育
        edu = str(candidate.get("education", "")).lower()
        has_advanced = 1.0 if ("硕士" in edu or "博士" in edu or "master" in edu or "phd" in edu) else 0.0
        has_985 = 1.0 if ("985" in edu or "211" in edu or "top" in edu) else 0.0
        
        features = np.array([[
            c_exp / 20.0,
            len(c_skills) / 20.0,
            has_advanced,
            has_985,
            overlap_rate,
            exp_fit,
        ]])
        return features
    
    def score(self, candidate: dict, job: dict) -> float:
        """Abstract method implementation: return ML score in [0,1]"""
        result = self.evaluate(candidate, job)
        if isinstance(result, dict):
            return result.get("score", 0.5)
        return 0.5

    def evaluate(self, candidate: dict, job: dict) -> dict:
        """规则评估入口"""
        if self.model is None:
            path = self.find_model()
            if path:
                self.load_model(path)
            else:
                return {"score": 0.5, "note": "ML模型未加载，返回默认分"}
        
        try:
            if self.extractor:
                cand_list = [{k: v for k, v in candidate.items() if k in ['current_role','current_company','years_experience','skills','education']}]
                job_list = [{k: v for k, v in job.items() if k in ['title','skills','required_skills','min_years_experience','max_years_experience']}]
                X = self.extractor.transform(cand_list, job_list)
            else:
                X = self._extract_features(candidate, job)
            proba = self.model.predict_proba(X)[0, 1]
            score = float(proba)
            
            note = f"ML模型评分: {score:.3f}"
            return {"score": score, "note": note}
        except Exception as e:
            logger.warning(f"ML scoring failed: {e}")
            return {"score": 0.5, "note": f"ML评分异常: {e}"}


# ── 使用示例 ──

def patch_match_engine():
    """
    将 MLScoringRule 注入现有 MatchEngine
    在 main.py 启动时调用一次即可
    """
    from matching.unified_engine import UnifiedMatchEngine

    engine = UnifiedMatchEngine()
    engine.weights["ml_scoring"] = 0.3

    logger.info("ML weight added to UnifiedMatchEngine")
    return engine


if __name__ == "__main__":
    # 测试集成
    engine = patch_match_engine()
    print(f"Engine rules: {[r.name for r in engine.rules]}")
    
    # 测试打分
    candidate = {
        "name": "测试候选人",
        "years_experience": 5,
        "skills": ["Python", "PyTorch", "NLP", "Transformer"],
        "education": "清华大学·985",
    }
    job = {
        "title": "算法工程师",
        "min_years_experience": 3,
        "max_years_experience": 8,
        "required_skills": "Python,PyTorch,Transformer,LLM,RAG",
    }
    
    score = engine.compute(candidate, job)
    print(f"\n测试匹配结果:")
    print(f"  Overall: {score.overall_score:.3f}")
    print(f"  Skill:   {score.skill_score:.3f}")
    print(f"  Matched: {score.matched_skills}")
    print(f"  Missing: {score.missing_skills}")
    print(f"  Reason:  {score.reasoning[:100]}")
