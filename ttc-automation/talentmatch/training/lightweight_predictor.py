"""
轻量级 ML 预测器 — Zero 依赖（纯 Python + JSON）
用于在无法安装 sklearn 的服务器上做 ML 推理

推理方法: 简化版 TF-IDF + 特征权重
"""
import json, math, re, os
from pathlib import Path
from typing import List, Optional


class LightweightPredictor:
    """
    轻量匹配预测器
    不需要 sklearn / numpy / joblib
    
    工作原理:
    1. 关键词匹配（简化 TF-IDF）
    2. 结构化特征（经验/教育/技能数）
    3. 加权求和（从训练好的模型导出权重）
    """
    
    def __init__(self, weights_path: Optional[str] = None):
        self.weights = None
        self.keywords = self._build_keyword_map()
        if weights_path and os.path.exists(weights_path):
            self.load_weights(weights_path)
    
    def _build_keyword_map(self) -> dict:
        """技能关键词权重映射（从训练数据的 TF-IDF 学到的）"""
        return {
            # AI/算法
            "python": 0.8, "pytorch": 0.9, "tensorflow": 0.9, "nlp": 0.85,
            "transformer": 0.9, "llm": 0.95, "rag": 0.9, "deep learning": 0.8,
            "machine learning": 0.75, "cv": 0.7, "mlops": 0.75,
            # 后端
            "java": 0.7, "go": 0.75, "kafka": 0.7, "redis": 0.6,
            "mysql": 0.6, "docker": 0.65, "k8s": 0.7, "grpc": 0.65,
            "microservices": 0.7,
            # 前端
            "javascript": 0.6, "typescript": 0.65, "react": 0.65,
            "vue": 0.6, "node.js": 0.6, "next.js": 0.65,
            # 数据
            "sql": 0.6, "spark": 0.7, "pandas": 0.6, "scikit-learn": 0.7,
            "statistics": 0.55, "ab testing": 0.55,
            # 产品
            "product strategy": 0.5, "user research": 0.5, "prd": 0.4,
            "agile": 0.4, "figma": 0.35, "data analysis": 0.5,
        }
    
    def load_weights(self, path: str):
        """加载预训练权重"""
        with open(path) as f:
            self.weights = json.load(f)
    
    def _skill_overlap(self, candidate_skills: list, job_skills: list) -> float:
        """技能重叠率（带权重）"""
        c_set = set(s.lower().strip() for s in candidate_skills if s)
        j_set = set(s.lower().strip() for s in job_skills if s)
        
        if not j_set:
            return 0.5
        
        weighted_match = 0
        total_weight = 0
        for js in j_set:
            w = self.keywords.get(js, 0.5)
            total_weight += w
            if js in c_set:
                weighted_match += w
        
        return weighted_match / max(total_weight, 1)
    
    def _experience_fit(self, c_exp: int, j_min: int = 0, j_max: int = 20) -> float:
        """经验匹配度"""
        if j_min <= c_exp <= j_max:
            return 1.0
        diff = min(abs(c_exp - j_min), abs(c_exp - j_max))
        return max(0.0, 1.0 - diff / 10)
    
    def _education_score(self, edu: str) -> float:
        """教育背景评分"""
        edu_lower = str(edu).lower()
        if "博士" in edu_lower or "phd" in edu_lower:
            return 1.0
        if "硕士" in edu_lower or "master" in edu_lower:
            return 0.85
        if "985" in edu_lower or "211" in edu_lower or "top" in edu_lower:
            return 0.8
        return 0.5
    
    def predict(self, candidate: dict, job: dict) -> float:
        """预测匹配分数 [0, 1]"""
        # 技能匹配 (权重 0.5)
        c_skills = candidate.get("skills", [])
        if isinstance(c_skills, str):
            c_skills = c_skills.split(",")
        j_skills = job.get("required_skills", job.get("skills", []))
        if isinstance(j_skills, str):
            j_skills = j_skills.split(",")
        skill_score = self._skill_overlap(c_skills, j_skills)
        
        # 经验匹配 (权重 0.25)
        c_exp = candidate.get("years_experience", 0) or 0
        j_min = job.get("min_years_experience", 0) or 0
        j_max = job.get("max_years_experience", 20) or 20
        exp_score = self._experience_fit(c_exp, j_min, j_max)
        
        # 教育匹配 (权重 0.15)
        edu = candidate.get("education", "")
        edu_score = self._education_score(edu)
        
        # 技能数量 (权重 0.1)
        skill_count = min(len(c_skills) / 10.0, 1.0)
        
        # 加权求和
        if self.weights:
            score = (
                self.weights.get("skill_weight", 0.5) * skill_score +
                self.weights.get("exp_weight", 0.25) * exp_score +
                self.weights.get("edu_weight", 0.15) * edu_score +
                self.weights.get("count_weight", 0.1) * skill_count
            )
        else:
            score = 0.5 * skill_score + 0.25 * exp_score + 0.15 * edu_score + 0.1 * skill_count
        
        return round(min(1.0, max(0.0, score)), 4)


# ── 测试 ──
if __name__ == "__main__":
    predictor = LightweightPredictor()
    
    tests = [
        ("高匹配", 
         {"current_role": "算法工程师", "years_experience": 5, "skills": ["Python", "PyTorch", "NLP", "Transformer", "LLM"], "education": "清华大学·985"},
         {"title": "高级算法工程师", "min_years_experience": 3, "required_skills": "Python,PyTorch,NLP,LLM,RAG,Deep Learning"}),
        ("低匹配",
         {"current_role": "产品经理", "years_experience": 2, "skills": ["Excel", "PPT", "Figma"], "education": "普通本科"},
         {"title": "高级算法工程师", "min_years_experience": 3, "required_skills": "Python,PyTorch,NLP,LLM,RAG,Deep Learning"}),
    ]
    
    print("轻量级 ML 预测器测试:")
    for label, cand, job in tests:
        score = predictor.predict(cand, job)
        print(f"  {label}: {score:.3f}")
