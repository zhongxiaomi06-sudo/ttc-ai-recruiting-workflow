import sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pymysql, sqlite3

import os
rds = pymysql.connect(
    host=os.environ.get("RDS_HOST", ""),
    user=os.environ.get("RDS_USER", ""),
    password=os.environ.get("RDS_PASSWORD", ""),
    database=os.environ.get("RDS_DATABASE", "recruit_bot"),
    connect_timeout=5
)
cur = rds.cursor()
cur.execute("SELECT id, name, raw_text, skills, years_experience, education, current_role, current_company, source FROM candidates WHERE source = %s OR source IS NULL ORDER BY created_at DESC LIMIT 8000", ("generated",))
rows = cur.fetchall()
print(f"Fetched {len(rows)} from RDS")

sqlite = sqlite3.connect(os.environ.get("DB_PATH", os.environ.get("DEPLOY_PATH", "/opt/talentmatch") + "/data/sqlite/recruit.db"))
sqlite.execute("PRAGMA journal_mode=WAL")

inserted = 0
for r in rows:
    try:
        cid = r[0]; name = r[1] or ""; raw = r[2] or ""
        skills = r[3] if isinstance(r[3], str) else json.dumps(r[3] or [])
        exp = r[4] or 0; edu = r[5] or ""; role = r[6] or ""; company = r[7] or ""
        src = r[8] or "rds_sync"
        exist = sqlite.execute("SELECT id FROM candidates WHERE id=?", (cid,)).fetchone()
        if exist: continue
        sqlite.execute("INSERT INTO candidates (id,name,raw_text,skills,years_experience,education,current_role,current_company,source) VALUES (?,?,?,?,?,?,?,?,?)", (cid,name,raw,skills,exp,edu,role,company,src))
        inserted += 1
    except (sqlite3.Error, json.JSONDecodeError, TypeError): pass

sqlite.commit()
t = sqlite.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
sqlite.close(); rds.close()
print(f"Inserted {inserted} into SQLite. Total: {t}")
