"""
阿里云 RDS 数据库连接模块
存储大规模训练数据 + 生产数据
数据库类型: MySQL 或 PostgreSQL (由用户配置)

使用方式:
  1. 在 .env 中配置 RDS_* 变量
  2. python3 -c "from storage.aliyun_rds import AliyunRDS; db = AliyunRDS(); db.test_connection()"
"""
import json, os, time, uuid, logging
from typing import Optional, List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class AliyunRDS:
    """
    阿里云 RDS 连接管理器
    支持 MySQL 和 PostgreSQL
    
    配置方式 (环境变量):
      RDS_TYPE=mysql|postgresql
      RDS_HOST=<内网地址>
      RDS_PORT=3306|5432
      RDS_USER=<your-rds-user>
      RDS_PASSWORD=<your-rds-password>
      RDS_DATABASE=recruit_bot
      RDS_INSTANCE_ID=<your-instance-id>
    """
    
    def __init__(self):
        self.type = os.getenv("RDS_TYPE", "mysql")
        self.host = os.getenv("RDS_HOST", "")
        self.port = int(os.getenv("RDS_PORT", "3306"))
        self.user = os.getenv("RDS_USER", "<your-rds-user>")
        self.password = os.getenv("RDS_PASSWORD", "<your-rds-password>")
        self.database = os.getenv("RDS_DATABASE", "recruit_bot")
        self.instance_id = os.getenv("RDS_INSTANCE_ID", "<your-instance-id>")
        self._conn = None
        self._available = False
    
    def is_configured(self) -> bool:
        """检查是否配置了 RDS"""
        return bool(self.host and self.password)
    
    def connect(self):
        """建立数据库连接"""
        if self._conn:
            return self._conn
        
        if self.type == "mysql":
            try:
                import pymysql
                self._conn = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    charset='utf8mb4',
                    connect_timeout=5,
                )
                self._available = True
                logger.info(f"RDS MySQL 连接成功: {self.host}:{self.port}/{self.database}")
            except ImportError:
                logger.warning("pymysql 未安装，尝试 mysql-connector-python")
                try:
                    import mysql.connector
                    self._conn = mysql.connector.connect(
                        host=self.host,
                        port=self.port,
                        user=self.user,
                        password=self.password,
                        database=self.database,
                    )
                    self._available = True
                except ImportError:
                    logger.error("请安装: pip install pymysql")
                    raise
            except Exception as e:
                logger.error(f"RDS 连接失败: {e}")
                raise
        else:
            # PostgreSQL
            try:
                import psycopg2
                self._conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    dbname=self.database,
                    connect_timeout=5,
                )
                self._available = True
                logger.info(f"RDS PostgreSQL 连接成功: {self.host}:{self.port}/{self.database}")
            except ImportError:
                logger.error("请安装: pip install psycopg2-binary")
                raise
            except Exception as e:
                logger.error(f"RDS 连接失败: {e}")
                raise
        
        return self._conn
    
    def test_connection(self) -> dict:
        """测试连接并返回状态"""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT 1" if self.type == "mysql" else "SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            return {"status": "ok", "result": result, "type": self.type}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def init_schema(self):
        """初始化数据库表结构"""
        conn = self.connect()
        cursor = conn.cursor()
        
        if self.type == "mysql":
            # 候选人表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(128),
                    current_role VARCHAR(256),
                    current_company VARCHAR(256),
                    years_experience INT DEFAULT 0,
                    skills JSON,
                    education VARCHAR(256),
                    ats_score FLOAT DEFAULT 0,
                    source VARCHAR(64),
                    owner_id VARCHAR(64),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # 岗位表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(256),
                    company VARCHAR(256),
                    required_skills JSON,
                    min_experience INT DEFAULT 0,
                    max_experience INT DEFAULT 20,
                    education VARCHAR(128),
                    salary_min INT DEFAULT 0,
                    salary_max INT DEFAULT 0,
                    description TEXT,
                    status VARCHAR(32) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # 匹配结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id VARCHAR(64) PRIMARY KEY,
                    candidate_id VARCHAR(64),
                    job_id VARCHAR(64),
                    overall_score FLOAT DEFAULT 0,
                    skill_score FLOAT DEFAULT 0,
                    experience_score FLOAT DEFAULT 0,
                    education_score FLOAT DEFAULT 0,
                    project_score FLOAT DEFAULT 0,
                    signal_score FLOAT DEFAULT 0,
                    matched_skills JSON,
                    missing_skills JSON,
                    recommendation VARCHAR(32),
                    explanation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_candidate (candidate_id),
                    INDEX idx_job (job_id),
                    INDEX idx_score (overall_score)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # 训练数据表 (200K+ 大规模数据)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS training_samples (
                    id VARCHAR(64) PRIMARY KEY,
                    candidate_name VARCHAR(128),
                    current_role VARCHAR(256),
                    current_company VARCHAR(256),
                    years_experience INT DEFAULT 0,
                    skills JSON,
                    education VARCHAR(256),
                    job_title VARCHAR(256),
                    job_skills JSON,
                    match_label INT DEFAULT 0,
                    score FLOAT DEFAULT 0,
                    source VARCHAR(64),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_source (source),
                    INDEX idx_label (match_label)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # 隐式反馈表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS implicit_feedback (
                    id VARCHAR(64) PRIMARY KEY,
                    candidate_id VARCHAR(64),
                    feedback_type VARCHAR(32),
                    dwell_seconds INT DEFAULT 0,
                    click_count INT DEFAULT 0,
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_candidate (candidate_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        else:
            # PostgreSQL schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(128),
                    current_role VARCHAR(256),
                    current_company VARCHAR(256),
                    years_experience INT DEFAULT 0,
                    skills JSONB,
                    education VARCHAR(256),
                    ats_score FLOAT DEFAULT 0,
                    source VARCHAR(64),
                    owner_id VARCHAR(64),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # (similar for other tables)
        
        conn.commit()
        cursor.close()
        self.close()
        logger.info("RDS Schema 初始化完成")
    
    def bulk_insert_training_data(self, samples: list, batch_size: int = 1000):
        """批量插入训练数据 (用于 200K 数据迁移)"""
        if not samples:
            return 0
        
        conn = self.connect()
        cursor = conn.cursor()
        count = 0
        
        for i in range(0, len(samples), batch_size):
            batch = samples[i:i+batch_size]
            values = []
            for s in batch:
                sid = s.get("id", str(uuid.uuid4()))
                name = s.get("candidate_name", "")
                role = s.get("current_role", "")
                company = s.get("current_company", "")
                exp = s.get("years_experience", 0)
                skills = json.dumps(s.get("skills", []), ensure_ascii=False)
                edu = s.get("education", "")
                jt = s.get("job_title", "")
                js = json.dumps(s.get("job_skills", []), ensure_ascii=False)
                label = s.get("match_label", 0)
                score = s.get("score", 0.5)
                source = s.get("source", "synthetic")
                values.append((sid, name, role, company, exp, skills, edu, jt, js, label, score, source))
            
            if self.type == "mysql":
                cursor.executemany(
                    "INSERT IGNORE INTO training_samples "
                    "(id, candidate_name, current_role, current_company, years_experience, "
                    "skills, education, job_title, job_skills, match_label, score, source) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    values
                )
            else:
                # PostgreSQL
                from psycopg2.extras import execute_values
                execute_values(cursor,
                    "INSERT INTO training_samples "
                    "(id, candidate_name, current_role, current_company, years_experience, "
                    "skills, education, job_title, job_skills, match_label, score, source) "
                    "VALUES %s ON CONFLICT (id) DO NOTHING",
                    values
                )
            
            conn.commit()
            count += len(batch)
            if (i // batch_size) % 10 == 0:
                logger.info(f"  已写入 {count}/{len(samples)} 条...")
        
        cursor.close()
        self.close()
        logger.info(f"批量插入完成: {count} 条")
        return count
    
    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None


# ── 独立测试 ──
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    db = AliyunRDS()
    if not db.is_configured():
        print("⚠️ RDS 未配置，请在 .env 中设置 RDS_HOST")
        print("  例如:")
        print("    RDS_TYPE=mysql")
        print("    RDS_HOST=rm-xxxxx.mysql.rds.aliyuncs.com")
        print("    RDS_PORT=3306")
        print("    RDS_USER=<your-rds-user>")
        print("    RDS_PASSWORD=<your-rds-password>")
        print("    RDS_DATABASE=recruit_bot")
        print("    RDS_INSTANCE_ID=<your-instance-id>")
        print()
        print("💡 请从阿里云 DMS 控制台获取内网地址和端口")
        sys.exit(1)
    
    result = db.test_connection()
    print(f"连接测试: {result}")
    
    if result["status"] == "ok":
        db.init_schema()
        print("Schema 初始化完成")
