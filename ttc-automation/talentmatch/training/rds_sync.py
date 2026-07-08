#!/usr/bin/env python3
"""
RDS 数据同步工具
将训练数据从本地 JSONL 同步到阿里云 RDS

用法:
  python3 training/rds_sync.py                         # 交互式配置
  RDS_HOST=xxx python3 training/rds_sync.py --push     # 推送到 RDS
  RDS_HOST=xxx python3 training/rds_sync.py --pull     # 从 RDS 拉取
"""
import json, os, sys, time, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.aliyun_rds import AliyunRDS
from training.data_collector import DatasetManager


class RDSSync:
    """RDS 数据同步管理器"""
    
    def __init__(self):
        self.rds = AliyunRDS()
        self.dm = DatasetManager()
    
    def push_training_data(self, jsonl_path: str = None, batch: int = 1000):
        """推送训练数据到 RDS"""
        if not self.rds.is_configured():
            logger.error("RDS 未配置！请在 .env 中设置 RDS_HOST")
            return False
        
        # 加载数据
        if jsonl_path and os.path.exists(jsonl_path):
            self.dm.load(jsonl_path)
        else:
            # 找最新的数据集
            data_dir = Path(__file__).parent / "data"
            jsonl_files = sorted(data_dir.glob("dataset_*.jsonl"), reverse=True)
            if jsonl_files:
                path = str(jsonl_files[0])
                self.dm.load(path)
                logger.info(f"加载最新数据集: {path}")
            else:
                # 生成 50K
                logger.info("未找到现有数据集，生成 50K 合成数据...")
                self.dm.generate_synthetic(50000)
        
        stats = self.dm.stats()
        logger.info(f"准备推送: {stats['total']:,} 条 ({stats['positive']:,} 正 / {stats['negative']:,} 负)")
        
        # 连接到 RDS
        try:
            self.rds.connect()
            self.rds.init_schema()
        except Exception as e:
            logger.error(f"RDS 连接失败: {e}")
            return False
        
        # 推送
        samples_dict = [s.__dict__ if hasattr(s, '__dict__') else s for s in self.dm.samples]
        self.rds.bulk_insert_training_data(samples_dict, batch)
        
        logger.info("✅ 数据推送完成")
        return True
    
    def pull_training_data(self, limit: int = 10000):
        """从 RDS 拉取训练数据"""
        if not self.rds.is_configured():
            logger.error("RDS 未配置")
            return None
        
        try:
            conn = self.rds.connect()
            cursor = conn.cursor()
            
            if self.rds.type == "mysql":
                cursor.execute(
                    "SELECT id, candidate_name, current_role, current_company, "
                    "years_experience, skills, education, job_title, job_skills, "
                    "match_label, score, source "
                    "FROM training_samples LIMIT %s", (limit,)
                )
            else:
                cursor.execute(
                    "SELECT id, candidate_name, current_role, current_company, "
                    "years_experience, skills, education, job_title, job_skills, "
                    "match_label, score, source "
                    "FROM training_samples LIMIT %s", (limit,)
                )
            
            rows = cursor.fetchall()
            cursor.close()
            
            logger.info(f"从 RDS 拉取 {len(rows)} 条数据")
            return rows
            
        except Exception as e:
            logger.error(f"拉取失败: {e}")
            return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="推送数据到 RDS")
    parser.add_argument("--pull", action="store_true", help="从 RDS 拉取数据")
    parser.add_argument("--file", type=str, default="", help="指定 JSONL 文件路径")
    parser.add_argument("--samples", type=int, default=0, help="要生成的样本数")
    parser.add_argument("--batch", type=int, default=1000, help="批量大小")
    args = parser.parse_args()
    
    sync = RDSSync()
    
    if args.push:
        sync.push_training_data(args.file or None, args.batch)
    elif args.pull:
        sync.pull_training_data(limit=args.samples or 10000)
    else:
        print("请指定 --push 或 --pull")
        print("\n推送训练数据到 RDS:")
        print("  RDS_HOST=rm-xxxx.mysql.rds.aliyuncs.com \\")
        print("  python3 training/rds_sync.py --push --samples 100000")
        print("\n从 RDS 拉取:")
        print("  RDS_HOST=rm-xxxx.mysql.rds.aliyuncs.com \\")
        print("  python3 training/rds_sync.py --pull --samples 10000")
