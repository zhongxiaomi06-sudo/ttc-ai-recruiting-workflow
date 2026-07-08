#!/usr/bin/env python3
"""
模型评估与可视化
加载训练好的模型，在测试集上做详细评估
"""
import json, os, sys, logging
from pathlib import Path
import numpy as np
import joblib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def evaluate_model(model_path: str, data_path: str = None):
    """评估训练好的模型"""
    from training.data_collector import DatasetManager
    from training.feature_engineering import FeatureExtractor
    
    # 加载数据
    dm = DatasetManager()
    if data_path:
        dm.load(data_path)
    else:
        # 使用最新生成的数据
        data_dir = Path(os.path.dirname(__file__)) / "data"
        jsonls = sorted(data_dir.glob("*.jsonl"))
        if jsonls:
            dm.load(str(jsonls[-1]))
            logger.info(f"Loaded: {jsonls[-1].name}")
        else:
            logger.warning("No data found, generating 10000 samples...")
            dm.generate_synthetic(10000)
    
    # 特征
    train, test = dm.train_test_split(0.8)
    def to_dict(samples):
        candidates, jobs = [], []
        for s in samples:
            candidates.append({"current_role": s.current_role, "current_company": s.current_company, "years_experience": s.years_experience, "skills": s.skills, "education": s.education})
            jobs.append({"title": s.job_title, "skills": s.job_skills})
        return candidates, jobs
    
    test_c, test_j = to_dict(test)
    extractor = FeatureExtractor()
    train_c, train_j = to_dict(train)
    extractor.fit(train_c, train_j)
    X_test = extractor.transform(test_c, test_j)
    y_test = np.array([s.match_label for s in test])
    
    # 加载模型
    model = joblib.load(model_path)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else y_pred
    
    from sklearn.metrics import (classification_report, confusion_matrix, roc_curve,
                                  precision_recall_curve, accuracy_score, f1_score)
    
    logger.info(f"\n评估报告: {os.path.basename(model_path)}")
    logger.info(f"测试样本: {len(test)}")
    logger.info(f"\n{classification_report(y_test, y_pred, target_names=['不匹配', '匹配'])}")
    
    # 混淆矩阵
    cm = confusion_matrix(y_test, y_pred)
    logger.info(f"混淆矩阵:")
    logger.info(f"  TN={cm[0,0]}  FP={cm[0,1]}")
    logger.info(f"  FN={cm[1,0]}  TP={cm[1,1]}")
    
    # 错误分析
    errors = []
    for i in range(len(test)):
        if y_pred[i] != y_test[i]:
            s = test[i]
            errors.append({
                "name": s.candidate_name,
                "role": s.current_role,
                "job": s.job_title,
                "true": int(y_test[i]),
                "pred": int(y_pred[i]),
                "prob": float(y_prob[i]),
                "skill_overlap": len(set(s.skills) & set(s.job_skills)),
            })
    
    logger.info(f"\n误分类样本: {len(errors)}")
    if errors:
        logger.info(f"  False Positive (误匹配): {sum(1 for e in errors if e['true']==0)}")
        logger.info(f"  False Negative (漏匹配): {sum(1 for e in errors if e['true']==1)}")
        
        # 显示前几个错误样本
        for e in errors[:5]:
            logger.info(f"  {e['name']} | {e['role']} -> {e['job']} | 真实={e['true']} 预测={e['prob']:.3f}")
    
    return {
        "accuracy": accuracy_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
        "errors": len(errors),
        "total": len(test),
    }


def list_models():
    """列出所有训练好的模型"""
    model_dir = Path(os.path.dirname(__file__)) / "models"
    models = sorted(model_dir.glob("*.joblib"))
    if not models:
        logger.info("没有找到训练好的模型")
        return
    
    logger.info("\n已保存的模型:")
    for m in models:
        size = os.path.getsize(m) / 1024
        logger.info(f"  {m.name} ({size:.0f} KB)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, help="模型文件路径")
    parser.add_argument("--data", type=str, default="", help="数据集路径")
    parser.add_argument("--list", action="store_true", help="列出所有模型")
    args = parser.parse_args()
    
    if args.list:
        list_models()
    elif args.model:
        evaluate_model(args.model, args.data)
    else:
        # 自动评估最新模型
        model_dir = Path(os.path.dirname(__file__)) / "models"
        models = sorted(model_dir.glob("*.joblib"))
        if models:
            list_models()
            logger.info(f"\n评估最新模型: {models[-1].name}")
            evaluate_model(str(models[-1]), args.data)
        else:
            logger.info("没有模型可评估。先运行: python3 training/train.py")
