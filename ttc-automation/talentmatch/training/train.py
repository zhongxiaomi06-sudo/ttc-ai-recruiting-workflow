#!/usr/bin/env python3
"""
简历匹配模型训练流水线
==========================
第一步：生成/收集数据
第二步：特征工程
第三步：模型训练（XGBoost / Logistic Regression / BERT）
第四步：评估
第五步：导出模型，集成到现有匹配引擎

用法:
  python3 training/train.py                    # 默认流水线
  python3 training/train.py --model xgboost    # 指定模型
  python3 training/train.py --samples 100000   # 生成更多数据
  python3 training/train.py --load data.jsonl  # 从已有数据训练
"""
import argparse, json, os, sys, time, logging
from pathlib import Path
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def phase_generate_data(args):
    """Phase 1: 数据生成"""
    from training.data_collector import DatasetManager, SyntheticDataGenerator
    
    dm = DatasetManager()
    
    logger.info("=" * 60)
    logger.info("Phase 1: 生成合成数据集")
    logger.info("=" * 60)
    
    n = args.samples
    logger.info(f"生成 {n:,} 条训练样本...")
    start = time.time()
    dm.generate_synthetic(n)
    elapsed = time.time() - start
    
    stats = dm.stats()
    logger.info(f"生成完成！耗时 {elapsed:.1f}s")
    logger.info(f"  总样本: {stats['total']:,}")
    logger.info(f"  正样本: {stats['positive']:,} ({stats['pos_ratio']*100:.1f}%)")
    logger.info(f"  负样本: {stats['negative']:,}")
    
    path = dm.save()
    logger.info(f"  已保存到: {path}")
    return dm


def phase_feature_engineering(dm, args):
    """Phase 2: 特征工程"""
    from training.feature_engineering import FeatureExtractor
    
    logger.info("=" * 60)
    logger.info("Phase 2: 特征工程")
    logger.info("=" * 60)
    
    train, test = dm.train_test_split(0.8)
    logger.info(f"训练集: {len(train):,} | 测试集: {len(test):,}")
    
    # 转成 dict 格式给 feature extractor
    def to_dict(samples):
        candidates, jobs = [], []
        for s in samples:
            candidates.append({
                "current_role": s.current_role,
                "current_company": s.current_company,
                "years_experience": s.years_experience,
                "skills": s.skills,
                "education": s.education,
            })
            jobs.append({
                "title": s.job_title,
                "skills": s.job_skills,
            })
        return candidates, jobs
    
    train_c, train_j = to_dict(train)
    test_c, test_j = to_dict(test)
    
    extractor = FeatureExtractor(use_embedding=args.embedding)
    logger.info("Fitting feature extractor...")
    extractor.fit(train_c, train_j)
    
    logger.info("Transforming features...")
    X_train = extractor.transform(train_c, train_j)
    X_test = extractor.transform(test_c, test_j)
    y_train = np.array([s.match_label for s in train])
    y_test = np.array([s.match_label for s in test])
    
    logger.info(f"特征维度: {X_train.shape[1]}")
    logger.info(f"训练集: {X_train.shape} | 测试集: {X_test.shape}")
    
    return X_train, X_test, y_train, y_test, extractor


def phase_train_model(X_train, y_train, X_test, y_test, args):
    """Phase 3: 模型训练"""
    logger.info("=" * 60)
    logger.info("Phase 3: 模型训练")
    logger.info("=" * 60)
    
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                                  f1_score, roc_auc_score, classification_report)
    
    model_name = args.model
    
    if model_name == "lr":
        logger.info("训练 Logistic Regression...")
        model = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
    elif model_name == "rf":
        logger.info("训练 Random Forest...")
        model = RandomForestClassifier(
            n_estimators=200, max_depth=15, 
            min_samples_leaf=5, class_weight='balanced',
            n_jobs=-1, random_state=42
        )
    elif model_name == "xgboost":
        try:
            from xgboost import XGBClassifier
            logger.info("训练 XGBoost...")
            model = XGBClassifier(
                n_estimators=300, max_depth=8, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                scale_pos_weight=1.5, random_state=42,
                eval_metric='logloss', use_label_encoder=False,
                verbosity=0
            )
        except ImportError:
            logger.warning("XGBoost not installed, falling back to Random Forest")
            model = RandomForestClassifier(n_estimators=200, n_jobs=-1, random_state=42)
    else:
        raise ValueError(f"Unknown model: {model_name}")
    
    start = time.time()
    model.fit(X_train, y_train)
    elapsed = time.time() - start
    
    # 评估
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else y_pred
    
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else 0.0,
    }
    
    logger.info(f"训练耗时: {elapsed:.1f}s")
    logger.info(f"模型: {model_name}")
    logger.info(f"  Accuracy:  {metrics['accuracy']:.4f}")
    logger.info(f"  Precision: {metrics['precision']:.4f}")
    logger.info(f"  Recall:    {metrics['recall']:.4f}")
    logger.info(f"  F1:        {metrics['f1']:.4f}")
    logger.info(f"  ROC-AUC:   {metrics['roc_auc']:.4f}")
    
    # Save model
    model_path = Path(os.path.dirname(__file__)) / "models"
    model_path.mkdir(exist_ok=True)
    
    import joblib
    output = model_path / f"{model_name}_{time.strftime('%Y%m%d')}.joblib"
    joblib.dump(model, output)
    logger.info(f"模型已保存到: {output}")
    
    return model, metrics


def phase_integrate(metrics):
    """Phase 4: 集成到现有匹配引擎"""
    logger.info("=" * 60)
    logger.info("Phase 4: 模型集成")
    logger.info("=" * 60)
    
    logger.info("评分对比:")
    logger.info(f"  当前规则引擎: 基于规则匹配 (SkillRule + ExperienceRule + CompanyRule)")
    logger.info(f"  新 ML 模型:   F1={metrics['f1']:.4f}, ROC-AUC={metrics['roc_auc']:.4f}")
    
    # 建议：混合使用
    logger.info("")
    logger.info("推荐集成方案: 混合打分")
    logger.info("  final_score = 0.4 * ml_score + 0.6 * rule_based_score")
    logger.info("  这样兼顾 ML 的泛化能力和规则的可解释性")
    
    logger.info("")
    logger.info("集成方式: 在 matching/engine.py 中添加 MLScoringRule")
    logger.info("  参考: training/integrate_with_engine.py")


def main():
    parser = argparse.ArgumentParser(description="简历匹配模型训练流水线")
    parser.add_argument("--model", choices=["lr", "rf", "xgboost"], default="xgboost",
                        help="模型类型 (default: xgboost)")
    parser.add_argument("--samples", type=int, default=50000,
                        help="合成数据样本数 (default: 50000)")
    parser.add_argument("--load", type=str, default="",
                        help="从已有 JSONL 数据集加载")
    parser.add_argument("--embedding", action="store_true",
                        help="使用 Sentence-BERT 语义向量")
    parser.add_argument("--skip-generate", action="store_true",
                        help="跳过数据生成（使用 --load）")
    parser.add_argument("--skip-train", action="store_true",
                        help="跳过训练，只生成数据")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info(f"🚀 简历匹配模型训练流水线")
    logger.info(f"   模型: {args.model}")
    logger.info(f"   样本: {args.samples:,}")
    logger.info(f"   语义向量: {'开启' if args.embedding else '关闭'}")
    logger.info("=" * 60)
    
    # Phase 1: 数据
    if args.load:
        from training.data_collector import DatasetManager
        dm = DatasetManager()
        dm.load(args.load)
        stats = dm.stats()
        logger.info(f"加载数据集: {stats['total']:,} 条")
    else:
        dm = phase_generate_data(args)
    
    if args.skip_train:
        logger.info("跳过训练（--skip-train）")
        return
    
    # Phase 2: 特征
    X_train, X_test, y_train, y_test, extractor = phase_feature_engineering(dm, args)
    
    # Phase 3: 训练
    model, metrics = phase_train_model(X_train, y_train, X_test, y_test, args)
    
    # Phase 4: 集成
    phase_integrate(metrics)
    
    logger.info("")
    logger.info("✅ 训练流水线完成！")
    logger.info(f"   运行 python3 training/evaluate.py 查看详细评估")


if __name__ == "__main__":
    main()
