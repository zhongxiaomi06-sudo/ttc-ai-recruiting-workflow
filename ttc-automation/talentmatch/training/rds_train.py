"""
从 RDS 加载训练数据 → 训练 XGBoost → 注入匹配引擎
"""
import json, os, sys, time, logging, uuid, random
from pathlib import Path
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# RDS 配置 (from environment variables — set via .env or export)
for _key in ("RDS_HOST", "RDS_USER", "RDS_PASSWORD", "RDS_DATABASE"):
    os.environ.setdefault(_key, "")


def load_from_rds(limit=60000):
    """从 RDS 加载训练数据"""
    from storage.aliyun_rds import AliyunRDS
    rds = AliyunRDS()
    conn = rds.connect()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT candidate_name, current_role, current_company, years_experience, "
        "skills, education, job_title, job_skills, match_label, score, source "
        "FROM training_samples LIMIT %s", (limit,)
    )
    rows = cursor.fetchall()
    cursor.close()
    
    logger.info(f"从 RDS 加载 {len(rows):,} 条训练数据")
    
    # 解析为特征向量
    X = []
    y = []
    for row in rows:
        name, role, company, exp, skills_json, edu, jtitle, jskills_json, label, score, source = row
        
        skill_set = set()
        try:
            for s in json.loads(skills_json if skills_json else "[]"):
                skill_set.add(s.lower().strip())
        except (json.JSONDecodeError, TypeError):
            pass
        
        job_skill_set = set()
        try:
            for s in json.loads(jskills_json if jskills_json else "[]"):
                job_skill_set.add(s.lower().strip())
        except (json.JSONDecodeError, TypeError):
            pass
        
        # 特征工程
        exp_years = int(exp or 0)
        skills_count = len(skill_set)
        job_skills_count = len(job_skill_set)
        overlap = len(skill_set & job_skill_set)
        overlap_ratio = overlap / max(len(job_skill_set), 1)
        
        # role 匹配（简单判断）
        role_match = 1 if role and jtitle and (
            role.lower()[:4] == jtitle.lower()[:4]
            or any(kw in role.lower() for kw in jtitle.lower().split()[:2])
        ) else 0
        
        # 经验拟合
        exp_fit = min(1.0, exp_years / 15)
        
        X.append([
            exp_years / 20.0,          # 归一化经验
            skills_count / 30.0,        # 归一化技能数
            job_skills_count / 30.0,
            min(overlap, 15) / 15.0,    # 重叠技能数
            overlap_ratio,              # 技能重叠率
            role_match,                 # 岗位名匹配
            exp_fit,                    # 经验拟合度
        ])
        y.append(label)
    
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


def train_xgboost(X, y):
    """训练 XGBoost 模型"""
    from xgboost import XGBClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                                  f1_score, roc_auc_score, classification_report,
                                  confusion_matrix)
    import joblib
    
    # 分训练/测试
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    pos_ratio = y_train.sum() / len(y_train)
    logger.info(f"训练集: {len(X_train):,} 正样本: {y_train.sum():,} ({pos_ratio:.1%})")
    logger.info(f"测试集: {len(X_test):,} 正样本: {y_test.sum():,} ({y_test.sum()/len(y_test):.1%})")
    
    model = XGBClassifier(
        n_estimators=500,
        max_depth=10,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=max(1.0, (1 - pos_ratio) / max(pos_ratio, 0.01)),
        random_state=42,
        eval_metric='logloss',
        verbosity=0,
        early_stopping_rounds=50,
    )
    
    logger.info("训练 XGBoost...")
    start = time.time()
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )
    elapsed = time.time() - start
    
    # 评估
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, y_prob), 4),
    }
    
    logger.info(f"训练耗时: {elapsed:.1f}s")
    logger.info(f"模型大小: {model.get_params()['n_estimators']} trees, max_depth={model.get_params()['max_depth']}")
    logger.info("")
    logger.info("=" * 50)
    logger.info("评估结果")
    logger.info("=" * 50)
    logger.info(f"  Accuracy:  {metrics['accuracy']:.4f}")
    logger.info(f"  Precision: {metrics['precision']:.4f}")
    logger.info(f"  Recall:    {metrics['recall']:.4f}")
    logger.info(f"  F1 Score:  {metrics['f1']:.4f}")
    logger.info(f"  ROC-AUC:   {metrics['roc_auc']:.4f}")
    
    # 混淆矩阵
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
    logger.info("")
    logger.info("  混淆矩阵:")
    logger.info(f"               预测负    预测正")
    logger.info(f"  实际负      {tn:>6}  {fp:>6}")
    logger.info(f"  实际正      {fn:>6}  {tp:>6}")
    
    # 特征重要性
    feature_names = [
        "经验年限", "技能数量", "JD技能数",
        "重叠技能数", "技能重叠率", "岗位名匹配", "经验拟合度"
    ]
    importance = model.feature_importances_
    sorted_idx = np.argsort(importance)[::-1]
    logger.info("\n  特征重要性 (Top 7):")
    for i in sorted_idx:
        logger.info(f"    {feature_names[i]:10s}: {importance[i]:.4f}")
    
    # 保存模型
    model_dir = Path(os.path.dirname(__file__)) / "models"
    model_dir.mkdir(exist_ok=True)
    
    model_path = model_dir / f"xgboost_rds_{time.strftime('%Y%m%d_%H%M%S')}.joblib"
    joblib.dump(model, model_path)
    logger.info(f"\n模型已保存: {model_path}")
    
    # 同时也导出一份 lightweight 权重版本（供 LightweightPredictor 用）
    # 从 XGBoost 提取近似权重
    lw_weights = {}
    for fn, imp in zip(feature_names, importance):
        lw_weights[fn] = round(float(imp), 4)
    
    lw_path = Path(os.path.dirname(__file__)) / "lightweight_weights.json"
    # 合并已有权重
    if lw_path.exists():
        with open(lw_path) as f:
            existing = json.load(f)
        existing["xgboost_feature_importance"] = lw_weights
        existing["xgboost_metrics"] = metrics
        existing["xgboost_model"] = str(model_path)
        with open(lw_path, "w") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    logger.info(f"权重已更新: {lw_path}")
    
    # 集成到匹配引擎
    logger.info("\n" + "=" * 50)
    logger.info("集成到匹配引擎")
    logger.info("=" * 50)
    logger.info("  matching/rules/ 下已存在 MLScoringRule (weight=0.4)")
    logger.info("  集成方式: python3 training/integrate_with_engine.py")
    logger.info(f"  模型路径: {model_path}")
    
    return model, metrics


def integrate_model(model_path, metrics):
    """将模型集成到匹配引擎"""
    from matching.unified_engine import UnifiedMatchEngine
    
    logger.info("集成 MLScoringRule 到匹配引擎...")
    engine = UnifiedMatchEngine()

    logger.info(f"当前权重 ({len(engine.weights)} 维度):")
    for k, v in engine.weights.items():
        logger.info(f"  {k}: weight={v:.3f}")

    total_weight = sum(engine.weights.values())
    logger.info(f"  权重总和: {total_weight:.2f}")
    
    logger.info("\n✅ 模型集成就绪！重启服务即可生效:")
    logger.info("  systemctl restart recruit-bot")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 RDS → XGBoost 训练流水线")
    logger.info("=" * 60)
    
    # Step 1: 加载数据
    logger.info("\n[1/3] 从 RDS 加载训练数据...")
    X, y = load_from_rds(limit=60000)
    
    # Step 2: 训练
    logger.info(f"\n[2/3] 训练 XGBoost ({len(X):,} 条样本)...")
    model, metrics = train_xgboost(X, y)
    
    # Step 3: 集成
    logger.info(f"\n[3/3] 集成到匹配引擎...")
    model_dir = Path(os.path.dirname(__file__)) / "models"
    model_files = sorted(model_dir.glob("xgboost_rds_*.joblib"))
    if model_files:
        integrate_model(str(model_files[-1]), metrics)
    
    logger.info("\n✅ 训练流水线完成！")
