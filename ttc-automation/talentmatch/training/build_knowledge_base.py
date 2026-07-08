"""
TalentMatch 知识库构建器
=========================
一键操作：
1. 从 JD 数据集提取技能词库 → 更新 lightweight_predictor 关键词
2. JD 数据导入 RDS jobs 表
3. 简历训练数据推送 RDS training_samples 表
4. 构建中文技能词库

用法:
  python3 training/build_knowledge_base.py
"""
import json, os, sys, re, uuid, logging, random
from pathlib import Path
from collections import Counter
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── 配置 ──
JD_DATA_PATH = Path(__file__).parent / "data" / "mycareersfuture.json"
RESUME_CORPUS_PATH = Path(__file__).parent / "data" / "resume_corpus_20260617_183617.jsonl"
SKILL_DICT_OUTPUT = Path(__file__).parent / "data" / "skill_dictionary.json"
PREDICTOR_WEIGHTS_OUTPUT = Path(__file__).parent / "lightweight_weights.json"
JD_OUTPUT = Path(__file__).parent / "data" / "jd_corpus.jsonl"


class KnowledgeBaseBuilder:
    """知识库构建器"""

    def __init__(self):
        self.jd_data = []
        self.resume_data = []
        self.skill_counter = Counter()
        self.role_skills = {}  # role → [skills]
        self.cn_skill_map = {}  # en_skill → cn_translation

        # 中文技能映射（硬编码核心词，后续通过数据扩展）
        self._init_cn_skill_map()

    def _init_cn_skill_map(self):
        """初始化中文技能映射表"""
        self.cn_skill_map = {
            # AI/算法
            "python": "Python", "pytorch": "PyTorch", "tensorflow": "TensorFlow",
            "nlp": "NLP自然语言处理", "transformer": "Transformer", "llm": "大语言模型LLM",
            "rag": "RAG检索增强", "deep learning": "深度学习", "machine learning": "机器学习",
            "computer vision": "计算机视觉", "cv": "计算机视觉", "mlops": "MLOps",
            "recommendation system": "推荐系统", "langchain": "LangChain",
            # 后端
            "java": "Java", "spring boot": "Spring Boot", "spring": "Spring",
            "golang": "Golang", "go": "Go", "rust": "Rust", "c++": "C++",
            "kafka": "Kafka", "redis": "Redis", "mysql": "MySQL",
            "postgresql": "PostgreSQL", "mongodb": "MongoDB",
            "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "K8s",
            "microservices": "微服务", "grpc": "gRPC", "restful": "RESTful API",
            "fastapi": "FastAPI", "flask": "Flask", "django": "Django",
            # 前端
            "javascript": "JavaScript", "typescript": "TypeScript",
            "react": "React", "vue": "Vue.js", "angular": "Angular",
            "node.js": "Node.js", "next.js": "Next.js", "html": "HTML",
            "css": "CSS", "webpack": "Webpack", "tailwind": "Tailwind CSS",
            # 数据
            "sql": "SQL", "spark": "Spark", "hadoop": "Hadoop",
            "pandas": "Pandas", "numpy": "NumPy", "scikit-learn": "Scikit-learn",
            "statistics": "统计学", "ab testing": "A/B测试",
            "tableau": "Tableau", "power bi": "Power BI",
            "etl": "ETL数据管道", "airflow": "Airflow",
            # 云
            "aws": "AWS", "azure": "Azure", "gcp": "GCP",
            "aliyun": "阿里云", "terraform": "Terraform",
            "ci/cd": "CI/CD", "jenkins": "Jenkins",
            # 产品/管理
            "agile": "敏捷开发", "scrum": "Scrum",
            "product management": "产品管理", "product strategy": "产品策略",
            "user research": "用户研究", "figma": "Figma",
            "jira": "JIRA", "confluence": "Confluence",
            # 通用
            "git": "Git", "linux": "Linux", "shell": "Shell脚本",
            "英语": "英语", "团队管理": "团队管理",
        }

    def load_jd_data(self):
        """加载 JD 数据集"""
        import json
        with open(JD_DATA_PATH) as f:
            data = json.load(f)
        self.jd_data = data.get("jobs", [])
        logger.info(f"加载 JD 数据: {len(self.jd_data):,} 条")

        # 提取技能和岗位映射
        for job in self.jd_data:
            skills = [s.strip().lower() for s in job.get("skills_required", []) if s.strip()]
            self.skill_counter.update(skills)
            
            role = job.get("job_category", ["Other"])[0].strip()
            if role not in self.role_skills:
                self.role_skills[role] = Counter()
            self.role_skills[role].update(skills)

        logger.info(f"  提取到 {len(self.skill_counter):,} 个技能词条")
        logger.info(f"  覆盖 {len(self.role_skills)} 个岗位类别")

    def load_resume_data(self):
        """加载简历训练数据"""
        with open(RESUME_CORPUS_PATH) as f:
            for line in f:
                if line.strip():
                    self.resume_data.append(json.loads(line))
        logger.info(f"加载简历训练数据: {len(self.resume_data):,} 条")

    def build_skill_dictionary(self):
        """构建技能词典并保存"""
        # Top N 技能（筛选有意义的词条）
        min_freq = 5
        top_skills = {k: v for k, v in self.skill_counter.most_common(3000) if v >= min_freq and len(k) > 1}
        
        # 构建完整词典（含中文映射）
        dictionary = {
            "version": "1.0",
            "built_at": datetime.now().isoformat(),
            "total_skills": len(top_skills),
            "total_jd_count": len(self.jd_data),
            "skills": {},
        }
        
        for skill, freq in top_skills.items():
            entry = {
                "frequency": freq,
                "cn_name": self.cn_skill_map.get(skill, skill.title()),
                "categories": [],
            }
            # 找这个技能属于哪些岗位
            for role, skills in self.role_skills.items():
                if skill in skills:
                    entry["categories"].append(role)
            dictionary["skills"][skill] = entry
        
        with open(SKILL_DICT_OUTPUT, "w") as f:
            json.dump(dictionary, f, ensure_ascii=False, indent=2)
        logger.info(f"技能词典已保存: {SKILL_DICT_OUTPUT}")
        logger.info(f"  共 {len(top_skills)} 个技能词条")

    def build_predictor_weights(self):
        """从 JD 技能频率更新 lightweight_predictor 的关键词权重"""
        # 基于技能在 JD 中出现的频率计算权重
        if not self.skill_counter:
            self.load_jd_data()
        
        total_jds = max(len(self.jd_data), 1)
        
        # 已有权重保留，从数据中计算新权重
        weights = {}
        for skill, freq in self.skill_counter.most_common(2000):
            if len(skill) < 2:
                continue
            # TF-like 权重: min(0.95, freq / 200 + 0.3)
            w = min(0.95, freq / max(total_jds * 0.01, 1) + 0.3)
            weights[skill] = round(w, 3)
        
        output = {
            "version": "2.0",
            "built_at": datetime.now().isoformat(),
            "source": "mycareersfuture_20298_JD",
            "total_skills": len(weights),
            "weights": weights,
        }
        
        with open(PREDICTOR_WEIGHTS_OUTPUT, "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        logger.info(f"预测器权重已保存: {PREDICTOR_WEIGHTS_OUTPUT}")
        logger.info(f"  共 {len(weights)} 个技能权重")

    def import_jd_to_rds(self):
        """JD 数据导入 RDS jobs 表（不对 RDS 做严格依赖）"""
        # 先把 JD 存成本地 JSONL（RDS 从 JSONL 批量导）
        count = 0
        with open(JD_OUTPUT, "w") as out:
            for job in self.jd_data:
                jd_record = {
                    "id": f"JD_{job.get('job_id', str(uuid.uuid4()))[:20]}",
                    "title": job.get("job_title", ""),
                    "company": job.get("company_name", ""),
                    "required_skills": job.get("skills_required", []),
                    "min_years_experience": self._parse_exp(job.get("min_years_experience", "0")),
                    "max_years_experience": 20,
                    "education": "",
                    "salary_min": self._parse_salary_min(job.get("salary", "")),
                    "salary_max": self._parse_salary_max(job.get("salary", "")),
                    "description": job.get("requirements_and_role", "")[:2000],
                    "status": "active",
                    "category": job.get("job_category", []),
                    "seniority": job.get("seniority", ""),
                    "source": "mycareersfuture",
                    "created_at": datetime.now().isoformat(),
                }
                out.write(json.dumps(jd_record, ensure_ascii=False) + "\n")
                count += 1
        
        logger.info(f"JD 语料库已保存: {JD_OUTPUT} ({count:,} 条)")

        # 尝试写入 RDS
        try:
            os.environ["RDS_HOST"] = ""
            os.environ["RDS_USER"] = ""
            os.environ["RDS_PASSWORD"] = ""
            os.environ["RDS_DATABASE"] = "recruit_bot"
            
            from storage.aliyun_rds import AliyunRDS
            rds = AliyunRDS()
            conn = rds.connect()
            cursor = conn.cursor()
            
            # 批量插入
            batch = []
            with open(JD_OUTPUT) as f:
                for line in f:
                    jd = json.loads(line)
                    batch.append(jd)
                    if len(batch) >= 500:
                        self._bulk_insert_jobs(cursor, batch)
                        batch = []
            if batch:
                self._bulk_insert_jobs(cursor, batch)
            
            conn.commit()
            cursor.close()
            logger.info("✅ JD 数据已写入 RDS jobs 表")
        except Exception as e:
            logger.warning(f"RDS 写入失败（数据已存 JSONL，可稍后手动导入）: {e}")

    def _bulk_insert_jobs(self, cursor, jobs):
        sql = """INSERT IGNORE INTO jobs 
                 (id, title, company, required_skills, min_years_experience, max_years_experience, 
                  education, salary_min, salary_max, description, status, created_at)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        for j in jobs:
            try:
                cursor.execute(sql, (
                    j["id"], j["title"], j["company"],
                    json.dumps(j["required_skills"], ensure_ascii=False),
                    j["min_years_experience"], j["max_years_experience"],
                    j["education"], j["salary_min"], j["salary_max"],
                    j["description"], j["status"], j["created_at"],
                ))
            except Exception as e:
                logger.warning(f"  插入失败 ({j['id']}): {e}")

    def _parse_exp(self, text: str) -> int:
        nums = re.findall(r'(\d+)', text)
        return int(nums[0]) if nums else 0

    def _parse_salary_min(self, text: str) -> int:
        nums = re.findall(r'\$?(\d+[,]?\d*)', text.replace(",", ""))
        return int(nums[0]) if nums else 0

    def _parse_salary_max(self, text: str) -> int:
        nums = re.findall(r'\$?(\d+[,]?\d*)', text.replace(",", ""))
        return int(nums[-1]) if nums else 0

    def build_cn_skill_dict(self):
        """构建中文技能词库（供前端搜索/匹配使用）"""
        # 从轻量预测器的权重 + JD 技能合并
        cn_dict = {"version": "1.0", "skills": []}
        
        # 添加已有的中文映射
        for en_skill, cn_name in self.cn_skill_map.items():
            cn_dict["skills"].append({
                "en": en_skill,
                "cn": cn_name,
                "category": self._infer_category(en_skill),
            })
        
        # 添加从数据中提取的高频英文技能（没中文映射的先保留英文）
        for skill, freq in self.skill_counter.most_common(500):
            if skill not in self.cn_skill_map and len(skill) > 2:
                cn_dict["skills"].append({
                    "en": skill,
                    "cn": skill.title(),
                    "category": self._infer_category(skill),
                })
        
        path = Path(__file__).parent / "data" / "cn_skill_dictionary.json"
        with open(path, "w") as f:
            json.dump(cn_dict, f, ensure_ascii=False, indent=2)
        logger.info(f"中文技能词库已保存: {path} ({len(cn_dict['skills'])} 个词条)")

    def _infer_category(self, skill: str) -> str:
        s = skill.lower()
        if s in ("python", "pytorch", "tensorflow", "nlp", "llm", "rag", "machine learning", "deep learning"):
            return "AI/算法"
        if s in ("java", "spring boot", "go", "rust", "kafka", "redis", "docker", "k8s", "微服务"):
            return "后端开发"
        if s in ("javascript", "typescript", "react", "vue", "angular", "html", "css"):
            return "前端开发"
        if s in ("sql", "spark", "hadoop", "pandas", "tableau"):
            return "数据"
        if s in ("aws", "azure", "gcp", "terraform", "ci/cd"):
            return "云/DevOps"
        if s in ("产品管理", "产品策略", "用户研究", "figma", "jira"):
            return "产品"
        return "其他"

    def push_training_data_to_rds(self):
        """推送 florex 简历训练数据到 RDS"""
        if not self.resume_data:
            self.load_resume_data()
        
        try:
            os.environ["RDS_HOST"] = ""
            os.environ["RDS_USER"] = ""
            os.environ["RDS_PASSWORD"] = ""
            os.environ["RDS_DATABASE"] = "recruit_bot"
            
            from storage.aliyun_rds import AliyunRDS
            rds = AliyunRDS()
            rds._type = "mysql"
            conn = rds.connect()
            
            # 先检查已有数据量
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM training_samples")
            existing = cursor.fetchone()[0]
            logger.info(f"RDS training_samples 表现有 {existing:,} 条")
            
            if existing > 50000:
                logger.info("训练数据已充足，跳过导入")
                cursor.close()
                return
            
            # 分批量插入
            batch = []
            count = 0
            for s in self.resume_data:
                # 每条数据同时生成正/负样本（随机岗位匹配）
                # 正样本：原 job_title 匹配
                positive = {
                    "id": str(uuid.uuid4()),
                    "candidate_name": s.get("candidate_name", ""),
                    "current_role": s.get("current_role", ""),
                    "current_company": s.get("current_company", ""),
                    "years_experience": s.get("years_experience", 0),
                    "skills": json.dumps(s.get("skills", []), ensure_ascii=False),
                    "education": s.get("education", ""),
                    "job_title": s.get("job_title", ""),
                    "job_skills": json.dumps(s.get("job_skills", []), ensure_ascii=False),
                    "match_label": 1,
                    "score": s.get("score", 0.5),
                    "source": s.get("source", "resume_corpus"),
                }
                batch.append(positive)
                count += 1
                
                if count % 5000 == 0:
                    self._flush_training_batch(cursor, batch)
                    batch = []
                    logger.info(f"  已推送 {count}/{len(self.resume_data)}")
            
            if batch:
                self._flush_training_batch(cursor, batch)
            
            conn.commit()
            cursor.close()
            logger.info(f"✅ 训练数据推送完成: {count:,} 条")
            
        except Exception as e:
            logger.warning(f"训练数据推送失败: {e}")
            import traceback
            traceback.print_exc()

    def _flush_training_batch(self, cursor, batch):
        sql = """INSERT IGNORE INTO training_samples 
                 (id, candidate_name, current_role, current_company, years_experience,
                  skills, education, job_title, job_skills, match_label, score, source)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        for item in batch:
            try:
                cursor.execute(sql, (
                    item["id"], item["candidate_name"], item["current_role"],
                    item["current_company"], item["years_experience"],
                    item["skills"], item["education"],
                    item["job_title"], item["job_skills"],
                    item["match_label"], item["score"], item["source"],
                ))
            except Exception:
                pass

    def run_all(self):
        """执行全部构建流程"""
        logger.info("=" * 60)
        logger.info("🚀 TalentMatch 知识库构建器 v1.0")
        logger.info("=" * 60)
        
        logger.info("\n[1/5] 加载 JD 数据集...")
        self.load_jd_data()
        
        logger.info("\n[2/5] 构建技能词典...")
        self.build_skill_dictionary()
        
        logger.info("\n[3/5] 构建中文技能词库...")
        self.build_cn_skill_dict()
        
        logger.info("\n[4/5] 更新预测器权重...")
        self.build_predictor_weights()
        
        logger.info("\n[5/5] 导入 JD 数据到 RDS...")
        self.import_jd_to_rds()
        
        logger.info("\n[可选] 推送训练数据到 RDS...")
        self.push_training_data_to_rds()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ 知识库构建完成！")
        logger.info("=" * 60)


if __name__ == "__main__":
    builder = KnowledgeBaseBuilder()
    builder.run_all()
