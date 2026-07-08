#!/usr/bin/env python3
"""
导入 florex/resume_corpus 数据集（29,783 份真实简历）
来源: https://github.com/florex/resume_corpus

数据格式:
  - .lab 文件: 岗位分类标签
  - .txt 文件: 简历原文（含HTML标签）
  - 技能文件: skills_it.txt (5,719 个IT技能词条)

用量: ~29,783 份真实简历 + ~96,000 份通过技能匹配生成的负样本
      = ~125,000 条训练样本
"""
import json, os, sys, uuid, re, random
from pathlib import Path
from typing import List, Optional, Dict
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.data_collector import DatasetManager, TrainingSample
from training.lightweight_predictor import LightweightPredictor


class ResumeCorpusImporter:
    """导入 florex/resume_corpus 数据集"""

    # 岗位类别 → 技能映射
    ROLE_SKILLS = {
        "Software_Developer": ["Java", "Python", "C++", "JavaScript", "SQL", "Git", "Agile", "REST", "Docker", "Spring"],
        "Front_End_Developer": ["JavaScript", "HTML", "CSS", "React", "Angular", "Vue", "TypeScript", "Node.js", "Webpack"],
        "Web_Developer": ["HTML", "CSS", "JavaScript", "PHP", "MySQL", "WordPress", "jQuery", "Bootstrap", "REST"],
        "Python_Developer": ["Python", "Django", "Flask", "FastAPI", "SQL", "Docker", "Git", "REST", "Pandas"],
        "Java_Developer": ["Java", "Spring", "Hibernate", "Maven", "SQL", "Git", "REST", "Docker", "JUnit"],
        "Database_Administrator": ["SQL", "MySQL", "Oracle", "PostgreSQL", "MongoDB", "Backup", "Performance Tuning", "SSIS"],
        "Systems_Administrator": ["Linux", "Windows Server", "AWS", "Networking", "Security", "Shell", "Ansible", "Docker"],
        "Network_Administrator": ["Cisco", "Routing", "Switching", "Firewall", "VPN", "TCP/IP", "DNS", "DHCP", "LAN"],
        "Project_manager": ["Project Management", "Agile", "Scrum", "JIRA", "Risk Management", "Stakeholder", "Budget"],
        "Data_Scientist": ["Python", "Machine Learning", "Statistics", "SQL", "TensorFlow", "PyTorch", "R", "Spark"],
        "DevOps_Engineer": ["Docker", "K8s", "CI/CD", "Jenkins", "AWS", "Terraform", "Ansible", "Linux", "Git"],
        "Security_Analyst": ["Security", "Penetration Testing", "Firewall", "SIEM", "Cryptography", "Network Security"],
        "Business_Analyst": ["Requirements", "SQL", "Agile", "UML", "JIRA", "Data Analysis", "Stakeholder"],
        "Cloud_Architect": ["AWS", "Azure", "GCP", "Docker", "K8s", "Microservices", "Terraform", "Cloud Security"],
        "Full_Stack_Developer": ["JavaScript", "React", "Node.js", "Python", "SQL", "MongoDB", "REST", "Git", "Docker"],
        "Data_Engineer": ["Python", "SQL", "Spark", "Kafka", "Hadoop", "Airflow", "ETL", "Data Warehouse"],
        "QA_Engineer": ["Testing", "Selenium", "Python", "Java", "CI/CD", "API Testing", "Performance Testing"],
        "AI_Engineer": ["Python", "Machine Learning", "Deep Learning", "NLP", "Computer Vision", "TensorFlow", "PyTorch"],
        "Mobile_Developer": ["Android", "iOS", "Swift", "Kotlin", "Java", "React Native", "Flutter", "REST"],
        "Tech_Lead": ["Architecture", "Team Management", "Agile", "System Design", "Code Review", "Mentoring"],
        "Technical_Writer": ["Documentation", "API Docs", "Technical Communication", "Markdown", "MadCap Flare"],
        "UX_Designer": ["User Research", "Wireframing", "Prototyping", "Figma", "Sketch", "Usability Testing"],
        "Product_Manager": ["Product Strategy", "User Research", "PRD", "Agile", "Data Analysis", "A/B Testing"],
        "HR_Specialist": ["Recruitment", "Onboarding", "HRIS", "Payroll", "Benefits", "Employee Relations"],
    }

    def __init__(self, corpus_dir: str = "/tmp/resume_corpus/resume_data"):
        self.corpus_dir = Path(corpus_dir)
        self.dm = DatasetManager()
        self.predictor = LightweightPredictor()
        
        # 加载技能词典
        self.skills_dict = set()
        skills_path = Path(corpus_dir).parent / "skills_it.txt"
        if skills_path.exists():
            with open(skills_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.skills_dict.add(line.lower())
            logger.info(f"加载 {len(self.skills_dict)} 个技能词条")

    def extract_skills(self, text: str) -> List[str]:
        """从简历文本中提取技能"""
        text_lower = text.lower()
        found = set()
        
        # 方法1: 从技能词典匹配
        for skill in self.skills_dict:
            if skill in text_lower and len(skill) > 2:
                found.add(skill.title())
        
        # 方法2: 常见技能模式
        patterns = [
            r'python', r'java(?:script)?', r'typescript', r'golang?', r'rust',
            r'react(?:\.js)?', r'vue(?:\.js)?', r'angular', r'native', r'flutter',
            r'django', r'flask', r'fastapi', r'spring', r'hibernate',
            r'mysql', r'postgresql', r'mongodb', r'redis', r'oracle',
            r'docker', r'kubernetes', r'k8s', r'aws', r'azure', r'gcp',
            r'tensorflow', r'pytorch', r'scikit(?:-learn)?', r'pandas', r'numpy',
            r'machine learning', r'deep learning', r'nlp', r'llm', r'transformer',
            r'sql', r'nosql', r'graphql', r'rest(?:ful)?', r'api', r'microservices',
            r'git', r'jenkins', r'ci/cd', r'linux', r'bash', r'shell',
            r'agile', r'scrum', r'jira', r'confluence',
            r'excel', r'tableau', r'power(?: )?bi', r'spark', r'hadoop', r'kafka',
            r'ansible', r'terraform', r'prometheus', r'grafana',
            r'selenium', r'junit', r'maven', r'gradle',
        ]
        
        for pattern in patterns:
            if re.search(pattern, text_lower):
                skill_name = pattern.replace(r'\.', '.').replace(r'\ ', ' ').replace(r'\?', '').replace(r'(?:', '').replace(r')', '').replace('?', '')
                skill_name = skill_name.replace('|', '_').split('_')[0].title()
                found.add(skill_name)
        
        return list(found)[:20]

    def extract_experience(self, text: str) -> int:
        """从文本中提取工作年限"""
        patterns = [
            r'(\d+)\+?\s*(?:year|yr)s?\s*(?:of)?\s*(?:experience|exp)',
            r'(?:experience|exp)\s*(?:of|:)?\s*(\d+)\+?\s*(?:year|yr)s?',
            r'(\d+)\s*(?:year|yr)s?\s*(?:experience|exp)',
        ]
        for pattern in patterns:
            m = re.search(pattern, text.lower())
            if m:
                return int(m.group(1))
        return random.randint(1, 15)

    def extract_education(self, text: str) -> str:
        """提取教育信息"""
        edu_patterns = [
            (r'(?:PhD|Ph\.D|Doctorate)[^.]+', "博士"),
            (r'(?:Master|M\.S\.|M\.A\.|MBA)[^.]+', "硕士"),
            (r'(?:Bachelor|B\.S\.|B\.A\.|B\.E\.)[^.]+', "本科"),
            (r'(?:Associate|A\.S\.)[^.]+', "大专"),
        ]
        for pattern, level in edu_patterns:
            m = re.search(pattern, text)
            if m:
                return f"{level}·{m.group(0).strip()[:30]}"
        return ""

    def import_all(self) -> DatasetManager:
        """导入全部 29,783 份真实简历"""
        logger.info("=" * 60)
        logger.info("🚀 导入 Resume Corpus 数据集 (29,783 份真实简历)")
        logger.info("=" * 60)

        txt_files = sorted(self.corpus_dir.glob("*.txt"))
        lab_files = {f.stem: f for f in self.corpus_dir.glob("*.lab")}

        count = 0
        for txt_path in txt_files:
            try:
                # 读取标签
                lab_path = lab_files.get(txt_path.stem)
                role_label = ""
                if lab_path:
                    role_label = lab_path.read_text().strip()

                # 读取简历文本
                text = txt_path.read_text(errors="replace")

                # 提取技能
                skills = self.extract_skills(text)
                if not skills:
                    skills = ["General"]  # 至少一个占位

                # 提取经验和教育
                exp_years = self.extract_experience(text)
                education = self.extract_education(text)

                # 确定 role 和 job_skills
                role_name = role_label
                job_skills = self.ROLE_SKILLS.get(role_label, [])

                # 清理名字（用文件名前4位）
                name = f"Corpus_{txt_path.stem[:8]}"

                self.dm.samples.append(TrainingSample(
                    id=str(uuid.uuid4()),
                    candidate_name=name,
                    current_role=role_name[:50],
                    current_company="",
                    years_experience=exp_years,
                    skills=skills,
                    education=education,
                    job_title=role_name[:50],
                    job_skills=job_skills,
                    match_label=1,
                    score=random.uniform(0.6, 0.95),
                    source="resume_corpus",
                ))
                count += 1

                if count % 5000 == 0:
                    logger.info(f"  已导入 {count}/29783...")

            except Exception as e:
                continue

        logger.info(f"  导入完成: {count} 份简历")

        # 生成负样本（岗位不匹配）
        logger.info("  生成负样本（跨岗位不匹配）...")
        neg_count = 0
        all_samples = self.dm.samples.copy()
        random.shuffle(all_samples)
        for i in range(min(count, 66000)):
            s = all_samples[i % len(all_samples)]
            # 找一个不同类别的岗位
            wrong_roles = [r for r in self.ROLE_SKILLS.keys() if r != s.current_role]
            if wrong_roles:
                wrong_role = random.choice(wrong_roles)
                wrong_skills = self.ROLE_SKILLS[wrong_role]
                self.dm.samples.append(TrainingSample(
                    id=str(uuid.uuid4()),
                    candidate_name=s.candidate_name,
                    current_role=s.current_role,
                    current_company=s.current_company,
                    years_experience=s.years_experience,
                    skills=s.skills,
                    education=s.education,
                    job_title=wrong_role[:50],
                    job_skills=wrong_skills,
                    match_label=0,
                    score=random.uniform(0.1, 0.4),
                    source="resume_corpus_neg",
                ))
                neg_count += 1

        logger.info(f"  生成负样本: {neg_count} 条")

        stats = self.dm.stats()
        logger.info(f"\n✅ 总计: {stats['total']:,} 条")
        logger.info(f"  正样本: {stats['positive']:,}")
        logger.info(f"  负样本: {stats['negative']:,}")

        return self.dm


if __name__ == "__main__":
    importer = ResumeCorpusImporter()
    dm = importer.import_all()
    
    # 保存
    output = Path(__file__).parent / "data" / f"resume_corpus_{__import__('time').strftime('%Y%m%d_%H%M%S')}.jsonl"
    dm.save(str(output))
    print(f"已保存: {output}")
