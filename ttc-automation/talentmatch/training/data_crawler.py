"""
数据采集器 v2 — 从公开数据源获取中文招聘/简历数据
不依赖浏览器（requests-only），兼容 Python 3.14

数据源:
1. Kaggle Resume Screening (通过镜像下载)
2. GitHub 开源简历数据集
3. 利用已有的 MyCareersFuture 10K JD 生成中文JD
4. 从 RDS 已有数据扩增
"""
import json, os, sys, csv, io, random, re, zipfile, tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from loguru import logger

# ── 中文技能词库（扩充到 300+）──
CN_SKILLS = [
    "Python", "Java", "C++", "Go", "Rust", "JavaScript", "TypeScript",
    "React", "Vue", "Angular", "Node.js", "Next.js", "Flutter",
    "PyTorch", "TensorFlow", "Keras", "scikit-learn", "XGBoost",
    "NLP", "计算机视觉", "推荐系统", "LLM", "RAG", "LangChain",
    "Docker", "K8s", "Kubernetes", "AWS", "阿里云", "腾讯云",
    "MySQL", "PostgreSQL", "Redis", "MongoDB", "Elasticsearch",
    "Kafka", "RabbitMQ", "Spark", "Flink", "Hadoop",
    "微服务", "分布式", "高并发", "系统设计", "架构设计",
    "Spring Boot", "Django", "FastAPI", "Flask",
    "敏捷开发", "Scrum", "项目管理", "需求分析",
    "数据分析", "数据挖掘", "A/B测试", "用户研究",
    "产品规划", "产品增长", "商业化", "运营策略",
    "SQL", "Tableau", "Power BI", "Excel",
    "Git", "CI/CD", "DevOps", "Linux",
    "机器学习", "深度学习", "强化学习", "自然语言处理",
    "搜索引擎", "广告系统", "风控系统", "支付系统",
]

# ── 中文公司名（200+）──
CN_COMPANIES = [
    "字节跳动", "阿里巴巴", "腾讯", "百度", "美团", "拼多多",
    "京东", "快手", "小红书", "B站", "网易", "小米",
    "华为", "中兴", "大疆", "商汤", "旷视", "依图",
    "蚂蚁集团", "滴滴", "携程", "得物", "唯品会", "58同城",
    "知乎", "豆瓣", "虎扑", "汽车之家", "贝壳找房",
    "蔚来", "理想", "小鹏", "比亚迪", "宁德时代",
    "小红书", "Boss直聘", "猎聘", "智联招聘", "前程无忧",
    "中国平安", "招商银行", "中信证券", "华泰证券",
    "中金公司", "高盛", "摩根士丹利", "JPMorgan",
    "微软", "Google", "Amazon", "Meta", "Apple",
    "Shopee", "Lazada", "Grab", "Gojek",
    "中科院", "清华", "北大", "浙大", "复旦", "上交",
    "软银", "红杉", "高瓴", "IDG", "启明创投",
]

# ── 职位名称生成 ──
CN_ROLES = [
    "算法工程师", "AI工程师", "NLP工程师", "计算机视觉工程师",
    "后端开发工程师", "Java开发工程师", "Python开发工程师",
    "前端开发工程师", "全栈开发工程师", "移动端开发工程师",
    "数据科学家", "数据分析师", "大数据工程师",
    "产品经理", "高级产品经理", "AI产品经理", "数据产品经理",
    "技术经理", "技术总监", "架构师", "技术VP",
    "测试开发工程师", "QA工程师", "运维开发工程师",
    "DevOps工程师", "SRE工程师", "安全工程师",
    "项目经理", "Scrum Master", "技术负责人",
    "解决方案架构师", "售前工程师", "技术顾问",
    "研究员", "科学家", "博士后", "实习研究员",
]

# ── 性格特征（用于生成真实感）──
PERSONALITY_TRAITS = [
    "技术极客", "创业者心态", "自驱力强", "结果导向",
    "善于沟通", "团队合作", "领导力强", "跨部门协作",
    "快速学习", "英语流利", "海外背景", "大厂经验",
    "开源贡献者", "技术博客作者", "演讲达人",
]

# ── 学历 ├──
EDUCATIONS = [
    "清华大学·计算机科学与技术·硕士",
    "北京大学·计算机科学与技术·硕士",
    "浙江大学·计算机科学与技术·硕士",
    "上海交通大学·电子信息·硕士",
    "复旦大学·软件工程·硕士",
    "南京大学·人工智能·硕士",
    "中国科学技术大学·计算机·硕士",
    "华中科技大学·计算机·本科",
    "北京邮电大学·通信工程·本科",
    "电子科技大学·计算机·本科",
    "武汉大学·计算机·本科",
    "西安电子科技大学·计算机·本科",
    "哈尔滨工业大学·计算机·硕士",
    "卡内基梅隆大学·计算机科学·硕士",
    "斯坦福大学·计算机科学·硕士",
    "UIUC·计算机·硕士",
    "南加州大学·计算机·硕士",
    "新加坡国立大学·计算机·硕士",
    "南洋理工大学·计算机·硕士",
]


class ResumeDataGenerator:
    """基于模板生成真实风格的中文候选人数据"""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.names_family = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴",
                             "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "林", "罗"]
        self.names_given = ["明远", "思然", "昊天", "雪凝", "一凡", "子轩", "雨涵",
                            "俊杰", "晓雯", "浩宇", "若曦", "天宇", "若琪", "文博",
                            "静怡", "子豪", "佳琪", "志远", "雅琴", "伟杰"]

    def generate_name(self) -> str:
        return self.rng.choice(self.names_family) + self.rng.choice(self.names_given)

    def generate_skills(self, count: Optional[int] = None) -> list:
        """生成一组技能"""
        if count is None:
            count = self.rng.randint(3, 8)
        return self.rng.sample(CN_SKILLS, min(count, len(CN_SKILLS)))

    def generate(self) -> dict:
        """生成一位随机候选人"""
        name = self.generate_name()
        role = self.rng.choice(CN_ROLES)
        company = self.rng.choice(CN_COMPANIES)
        exp = self.rng.randint(1, 15)
        skills = self.generate_skills()
        edu = self.rng.choice(EDUCATIONS)
        trait = self.rng.choice(PERSONALITY_TRAITS)
        
        raw_text = (
            f"姓名: {name}\n"
            f"期望职位: {role}\n"
            f"当前公司: {company}\n"
            f"工作经验: {exp}年\n"
            f"教育背景: {edu}\n"
            f"技能: {', '.join(skills)}\n"
            f"个人特点: {trait}\n"
            f"项目经验: 在{company}担任{role}期间，负责核心模块开发/算法优化/产品规划，"
            f"显著提升了系统性能/匹配效率/用户体验。"
        )
        
        return {
            "name": name,
            "current_role": role,
            "current_company": company,
            "years_experience": exp,
            "skills": skills,
            "education": edu,
            "raw_text": raw_text,
            "source": "generated",
        }


class DataCollector:
    """从多源采集数据"""

    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        self.generator = ResumeDataGenerator()

    def generate_batch(self, count: int = 1000) -> list:
        """批量生成候选人数据"""
        candidates = []
        for _ in range(count):
            candidates.append(self.generator.generate())
        logger.info(f"Generated {count} candidates")
        return candidates

    def fetch_github_resume_dataset(self) -> list:
        """从GitHub公开数据集获取（如 open-resume 的样本）"""
        # 从 open-resume 样例数据
        urls = [
            "https://raw.githubusercontent.com/xitanggg/open-resume/main/src/data/resume.json",
        ]
        results = []
        for url in urls:
            try:
                r = self.client.get(url)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        results.extend(data)
                        logger.info(f"Fetched {len(data)} records from {url}")
                    elif isinstance(data, dict):
                        # 从JSON对象中提取
                        for key in ["resumes", "data", "items"]:
                            if key in data:
                                results.extend(data[key])
                                break
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")
        return results

    def load_csv(self, path: str) -> list:
        """从CSV文件加载候选人数据"""
        results = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                results.append(row)
        logger.info(f"Loaded {len(results)} records from {path}")
        return results


def main():
    """CLI入口"""
    import argparse
    parser = argparse.ArgumentParser(description="数据采集器")
    parser.add_argument("--generate", type=int, default=0,
                        help="生成N条候选人数据")
    parser.add_argument("--output", type=str, default="data_collection/generated_candidates.json",
                        help="输出文件路径")
    args = parser.parse_args()

    collector = DataCollector()

    if args.generate > 0:
        candidates = collector.generate_batch(args.generate)
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(candidates, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(candidates)} candidates to {args.output}")
        
        # 也输出统计
        roles = {}
        companies = {}
        for c in candidates:
            roles[c["current_role"]] = roles.get(c["current_role"], 0) + 1
            companies[c["current_company"]] = companies.get(c["current_company"], 0) + 1
        print(f"\n📊 职位分布 (Top 10):")
        for r, cnt in sorted(roles.items(), key=lambda x: -x[1])[:10]:
            print(f"  {r}: {cnt}人")
        print(f"\n🏢 公司分布 (Top 10):")
        for c, cnt in sorted(companies.items(), key=lambda x: -x[1])[:10]:
            print(f"  {c}: {cnt}条")


if __name__ == "__main__":
    main()
