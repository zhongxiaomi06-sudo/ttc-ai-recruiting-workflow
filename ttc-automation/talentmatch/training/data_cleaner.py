"""
DeepSeek 数据清洗脚本
读取 candidates 表中 skills/education/experience 为空或质量差的记录，
用 DeepSeek API 从 raw_text 或 name/role 推断结构化字段并写入数据库。

用法:
  python3 training/data_cleaner.py                    # 默认清洗所有脏数据
  python3 training/data_cleaner.py --limit 100        # 只洗 100 条，用于测试
  python3 training/data_cleaner.py --dry-run          # 只看不改
"""
import json, os, sys, time, re, sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from loguru import logger

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DASHSCOPE_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
# DashScope 兼容端点
DASHSCOPE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

DB_PATH = os.environ.get("DB_PATH", "/opt/recruit-bot/data/sqlite/recruit.db")

SYSTEM_PROMPT = """你是一个简历解析专家。从候选人的原始信息中提取结构化的简历数据。
只返回 JSON，不要任何解释。

输入格式：候选人的 name、current_role、raw_text 等信息
输出格式：
{
  "skills": ["技能1", "技能2", ...],
  "education": "最高学历及学校",
  "years_experience": 数字,
  "summary": "一句话简介"
}

技能列表用中文或英文均可，提取最重要的 3-8 个。
education 格式：学校·专业·学历（如 "北京大学·计算机·硕士"）
years_experience 从 raw_text 或经历推断，没有则写 0。
summary 用 20 字以内中文描述。"""


def call_deepseek(name: str, role: str, raw_text: str) -> dict:
    """调用 DeepSeek(或DashScope) API 提取结构化字段"""
    prompt = f"候选人信息：\n姓名：{name}\n当前职位：{role}\n原始文本：{raw_text[:2000]}"
    
    # 优先 DeepSeek，降级到 DashScope
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    
    for attempt in range(2):
        try:
            resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                # 提取 JSON
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            elif resp.status_code == 401:
                # Key 无效，尝试 DashScope
                dash_payload = {
                    "model": "qwen-plus",
                    "input": {"messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]},
                    "parameters": {"temperature": 0.1, "max_tokens": 500},
                }
                dash_headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
                resp2 = requests.post(DASHSCOPE_URL, headers=dash_headers, json=dash_payload, timeout=30)
                if resp2.status_code == 200:
                    text = resp2.json()["output"]["text"]
                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed: {e}")
            time.sleep(2)
    
    return {"skills": [], "education": "", "years_experience": 0, "summary": ""}


def get_dirty_candidates(conn, limit=None):
    """获取需要清洗的候选人（skills 为空或数据质量差）"""
    query = """
        SELECT id, name, current_role, current_company, raw_text, 
               years_experience, skills, education, source
        FROM candidates 
        WHERE (skills IS NULL OR skills = '[]' OR skills = '' 
               OR education IS NULL OR education = '' OR education = '[]'
               OR years_experience IS NULL OR years_experience = 0)
        ORDER BY 
            CASE WHEN source = 'original' THEN 0 ELSE 1 END,
            years_experience DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    
    rows = conn.execute(query).fetchall()
    cols = ["id", "name", "current_role", "current_company", "raw_text", 
            "years_experience", "skills", "education", "source"]
    return [dict(zip(cols, r)) for r in rows]


def update_candidate(conn, cid: str, data: dict):
    """更新清洗后的数据到数据库"""
    skills_json = json.dumps(data.get("skills", []), ensure_ascii=False)
    edu = data.get("education", "")
    exp = int(data.get("years_experience", 0) or 0)
    summary = data.get("summary", "")
    
    conn.execute(
        """UPDATE candidates 
           SET skills=?, education=?, years_experience=?, 
               summary=?, updated_at=datetime('now')
           WHERE id=?""",
        (skills_json, edu, exp, summary, cid)
    )
    conn.commit()


def clean(limit=None, dry_run=False):
    """主清洗流程"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    candidates = get_dirty_candidates(conn, limit)
    logger.info(f"找到 {len(candidates)} 条待清洗记录")
    
    stats = {"total": len(candidates), "success": 0, "failed": 0, "skipped": 0}
    
    for i, c in enumerate(candidates):
        name = c["name"] or c.get("current_role", "") or "未知"
        role = c.get("current_role", "")
        raw_text = c.get("raw_text", "") or ""
        
        # 跳过完全没有信息的记录
        if not raw_text and not role:
            stats["skipped"] += 1
            continue
        
        if dry_run:
            logger.info(f"[{i+1}/{len(candidates)}] (dry-run) {name}: skills={c['skills']}, edu={c['education']}")
            continue
        
        try:
            result = call_deepseek(name, role, raw_text)
            if result:
                update_candidate(conn, c["id"], result)
                stats["success"] += 1
                logger.info(f"[{i+1}/{len(candidates)}] ✅ {name}: {len(result.get('skills',[]))} skills, edu={result.get('education','')[:20]}")
            else:
                stats["failed"] += 1
        except Exception as e:
            stats["failed"] += 1
            logger.error(f"[{i+1}/{len(candidates)}] ❌ {name}: {e}")
        
        # API 限流：每 3 秒一条
        if (i + 1) % 5 == 0:
            conn.commit()
            logger.info(f"  进度: {i+1}/{len(candidates)}, 成功{stats['success']}, 失败{stats['failed']}, 跳过{stats['skipped']}")
        time.sleep(3)
    
    conn.commit()
    conn.close()
    
    logger.info(f"清洗完成: {stats}")
    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="只清洗前 N 条")
    parser.add_argument("--dry-run", action="store_true", help="只看不改")
    args = parser.parse_args()
    
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")
    
    if args.dry_run:
        logger.warning("DRY RUN 模式 — 不会修改数据库")
    
    logger.info(f"DeepSeek 数据清洗开始 (limit={args.limit or 'all'})")
    logger.info(f"DB: {DB_PATH}")
    
    stats = clean(limit=args.limit, dry_run=args.dry_run)
    
    logger.info(f"清洗结束: 总{stats['total']} | 成功{stats['success']} | 失败{stats['failed']} | 跳过{stats['skipped']}")
