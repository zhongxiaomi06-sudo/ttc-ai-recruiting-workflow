"""
数据集收集器 - 从各平台下载/合成训练数据集
路线：
  Phase 1: 合成数据集（200K Resume Screening）— 立即可用
  Phase 2: Kaggle 公开数据集 — 需要 kaggle API
  Phase 3: 开源比赛数据集（讯飞）
  Phase 4: 自有 TTC 简历数据
"""
import json, os, csv, uuid, random, re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.path.dirname(__file__)) / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── 数据模式 ──

@dataclass
class TrainingSample:
    """统一训练样本格式"""
    id: str
    candidate_name: str
    current_role: str
    current_company: str
    years_experience: int
    skills: List[str]
    education: str
    job_title: str          # 目标岗位
    job_skills: List[str]   # 岗位要求技能
    match_label: int         # 1=匹配, 0=不匹配
    score: float             # 匹配分数 (0-1)
    source: str              # 数据集来源

# ── Phase 1: 合成大规模数据集 ──

class SyntheticDataGenerator:
    """
    生成 200K 规模的合成招聘数据
    基于真实招聘模式，模拟技能、经验、行业分布
    """

    ROLES = [
        ("算法工程师", "AI", ["Python","PyTorch","TensorFlow","NLP","CV","Transformer","LLM","RAG","Deep Learning","MLOps"]),
        ("后端开发", "Engineering", ["Python","Java","Go","Kafka","Redis","MySQL","Docker","K8s","gRPC","Microservices"]),
        ("前端开发", "Engineering", ["JavaScript","TypeScript","React","Vue","CSS","HTML","Webpack","Next.js","Node.js"]),
        ("数据科学家", "Data", ["Python","SQL","Machine Learning","Statistics","A/B Testing","Spark","Pandas","Scikit-learn"]),
        ("产品经理", "Product", ["Product Strategy","User Research","A/B Testing","PRD","Agile","Data Analysis","Figma"]),
        ("数据分析师", "Data", ["SQL","Excel","Python","Tableau","Power BI","Statistics","Data Visualization"]),
        ("运维工程师", "Engineering", ["Linux","Docker","K8s","CI/CD","Ansible","Terraform","Prometheus","AWS"]),
        ("安全工程师", "Security", ["Penetration Testing","Network Security","Cryptography","SIEM","SOC","Python"]),
        ("测试开发", "Engineering", ["Python","Java","Selenium","API Testing","CI/CD","Performance Testing"]),
        ("AI产品经理", "Product", ["AI/ML","Product Strategy","NLP","Computer Vision","PRD","User Research","Agile"]),
    ]

    COMPANIES = [
        ("字节跳动", "Tier1"), ("腾讯", "Tier1"), ("阿里巴巴", "Tier1"),
        ("美团", "Tier1.5"), ("快手", "Tier1.5"), ("小红书", "Tier1.5"),
        ("百度", "Tier1"), ("京东", "Tier1"), ("拼多多", "Tier1.5"),
        ("网易", "Tier2"), ("B站", "Tier2"), ("知乎", "Tier2"),
        ("携程", "Tier2"), ("滴滴", "Tier2"), ("菜鸟网络", "Tier2"),
        ("爱奇艺", "Tier3"), ("58同城", "Tier3"), ("转转", "Tier3"),
        ("Shopee", "Tier1.5"), ("Shein", "Tier2"),
        ("小型创业公司", "Startup"), ("中型企业", "Mid"),
    ]

    UNIVERSITIES = [
        ("清华大学", "985"), ("北京大学", "985"), ("浙江大学", "985"),
        ("上海交通大学", "985"), ("复旦大学", "985"), ("南京大学", "985"),
        ("武汉大学", "985"), ("华中科技大学", "985"), ("中山大学", "985"),
        ("北京理工大学", "985"), ("华南理工大学", "985"), ("电子科技大学", "985"),
        ("北京邮电大学", "211"), ("西安电子科技大学", "211"), ("南京邮电大学", "211"),
        ("重庆大学", "211"), ("武汉理工大学", "211"), ("华东理工大学", "211"),
        ("杭州电子科技大学", "双非"), ("深圳大学", "双非"), 
    ]

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def _pick_skills(self, role_skills: List[str], skill_count: int) -> List[str]:
        """从角色技能池中选技能，加上一些通用技能"""
        selected = self.rng.sample(role_skills, min(skill_count, len(role_skills)))
        common = ["Git", "Linux", "Docker", "English"]
        extra = self.rng.sample(common, self.rng.randint(0, 2))
        return list(set(selected + extra))

    def generate_sample(self, role_idx: int = None, for_job: bool = False) -> TrainingSample:
        """生成一条训练样本"""
        if role_idx is None:
            role_idx = self.rng.randint(0, len(self.ROLES) - 1)
        
        role, category, skills = self.ROLES[role_idx]
        company, tier = self.rng.choice(self.COMPANIES)
        
        exp_years = self.rng.randint(1, 12)
        match_label = 1 if self.rng.random() > 0.4 else 0  # 60% 匹配
        
        # 技能匹配度：匹配样本技能重叠多，不匹配样本技能重叠少
        if match_label == 1:
            candidate_skills = self._pick_skills(skills, self.rng.randint(3, len(skills)))
            job_skills = self._pick_skills(skills, self.rng.randint(3, min(7, len(skills))))
            # 确保有重叠
            overlap = self.rng.randint(2, min(len(candidate_skills), len(job_skills)))
            candidate_skills = job_skills[:overlap] + [s for s in candidate_skills if s not in job_skills]
        else:
            job_skills = self._pick_skills(skills, self.rng.randint(3, 7))
            # 选择完全不相关的技能
            other_idx = (role_idx + self.rng.randint(2, len(self.ROLES) - 1)) % len(self.ROLES)
            candidate_skills = self._pick_skills(self.ROLES[other_idx][2], self.rng.randint(2, 5))
            if self.rng.random() < 0.3:
                # 仍给少量重叠来增加难度
                job_skills = job_skills[:1] + self._pick_skills(self.ROLES[other_idx][2], 3)

        uni, uni_tier = self.rng.choice(self.UNIVERSITIES)
        
        # 匹配分数 = 技能重叠 + 经验适配 + 公司层级
        matched = set(candidate_skills) & set(job_skills)
        score = len(matched) / max(len(job_skills), 1) * 0.6
        exp_ok = 1.0 if exp_years >= 2 else max(0, exp_years / 2)
        score += exp_ok * 0.2
        if tier in ("Tier1", "Tier1.5"):
            score += 0.1
        score = min(1.0, max(0.0, score))
        if match_label == 0:
            score = min(score, 0.4)  # 不匹配样本分数 < 0.4
        
        return TrainingSample(
            id=str(uuid.uuid4()),
            candidate_name=f"候选人{self.rng.randint(1000,9999)}",
            current_role=role,
            current_company=company,
            years_experience=exp_years,
            education=f"{uni} · {uni_tier}",
            skills=candidate_skills,
            job_title=role,
            job_skills=job_skills,
            match_label=match_label,
            score=round(score, 4),
            source="synthetic"
        )

    def generate_dataset(self, n_samples: int = 50000) -> List[TrainingSample]:
        """生成大规模合成数据集"""
        samples = []
        for i in range(n_samples):
            samples.append(self.generate_sample())
            if (i + 1) % 10000 == 0:
                logger.info(f"Generated {i+1}/{n_samples} samples")
        return samples


# ── 数据集管理器 ──

class DatasetManager:
    """
    统一数据集管理
    - 合成数据生成
    - CSV/JSON 导入导出
    - 训练/验证集划分
    """

    def __init__(self):
        self.samples: List[TrainingSample] = []

    def generate_synthetic(self, n: int = 50000) -> int:
        """生成合成数据集"""
        gen = SyntheticDataGenerator()
        self.samples = gen.generate_dataset(n)
        return len(self.samples)

    def from_csv(self, path: str) -> int:
        """从 CSV 导入结构化数据"""
        count = 0
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        sample = TrainingSample(
                            id=row.get("id", str(uuid.uuid4())),
                            candidate_name=row.get("candidate_name", row.get("name", "")),
                            current_role=row.get("current_role", row.get("role", "")),
                            current_company=row.get("current_company", row.get("company", "")),
                            years_experience=int(row.get("years_experience", row.get("experience", 0))),
                            skills=json.loads(row.get("skills", "[]")) if isinstance(row.get("skills"), str) else row.get("skills", "").split(","),
                            education=row.get("education", ""),
                            job_title=row.get("job_title", ""),
                            job_skills=json.loads(row.get("job_skills", "[]")) if isinstance(row.get("job_skills"), str) else [],
                            match_label=int(row.get("match_label", row.get("label", 0))),
                            score=float(row.get("score", 0.0)),
                            source=row.get("source", "csv"),
                        )
                        self.samples.append(sample)
                        count += 1
                    except Exception as e:
                        logger.warning(f"Skipping row: {e}")
        except Exception as e:
            logger.error(f"CSV import failed: {e}")
        return count

    def save(self, path: str = None) -> str:
        """保存为 JSON Lines 格式"""
        if path is None:
            path = str(DATA_DIR / f"dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
        with open(path, 'w') as f:
            for s in self.samples:
                f.write(json.dumps(asdict(s), ensure_ascii=False) + '\n')
        logger.info(f"Saved {len(self.samples)} samples to {path}")
        return path

    def load(self, path: str) -> int:
        """从 JSON Lines 加载"""
        with open(path, 'r') as f:
            for line in f:
                if line.strip():
                    self.samples.append(TrainingSample(**json.loads(line)))
        return len(self.samples)

    def train_test_split(self, ratio: float = 0.8):
        """划分训练/测试集"""
        self.rng = random.Random(42)
        self.rng.shuffle(self.samples)
        split = int(len(self.samples) * ratio)
        return self.samples[:split], self.samples[split:]
    
    def stats(self) -> dict:
        """数据集统计"""
        if not self.samples:
            return {"total": 0}
        labels = [s.match_label for s in self.samples]
        return {
            "total": len(self.samples),
            "positive": sum(labels),
            "negative": len(labels) - sum(labels),
            "pos_ratio": round(sum(labels) / len(labels), 3),
            "sources": list(set(s.source for s in self.samples)),
            "avg_score": round(sum(s.score for s in self.samples) / len(self.samples), 4),
        }


# ── 独立运行 ──

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    dm = DatasetManager()
    
    print("=" * 60)
    print("Phase 1: 生成合成数据集")
    print("=" * 60)
    
    # 小规模测试：5000条
    n = dm.generate_synthetic(5000)
    print(f"生成 {n} 条样本")
    print(f"统计: {dm.stats()}")
    
    # 保存
    path = dm.save()
    print(f"已保存到: {path}")
    
    print("\n✅ Phase 1 完成！")
    print(f"   运行 python3 training/train.py 开始训练")
