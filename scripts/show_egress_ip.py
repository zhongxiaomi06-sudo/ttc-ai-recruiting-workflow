#!/usr/bin/env python3
"""打印 RDS 实际看到的本机出口 IP（用于配置阿里云白名单）。

curl ifconfig.me 不准——本机 HTTP 走 VPN，而 MySQL 连 RDS 走直连，两者出口不同。
最准的是直接问 RDS：MySQL 的 USER() 返回 'user@客户端IP'。

用法（需先配好 .env 的 RDS_* 凭据）：
    cd ttc的交易系统
    candidate-collector/.venv/bin/python scripts/show_egress_ip.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "candidate-collector"))

from cloud_sync.client import get_conn
from cloud_sync.config import rds_configured


def main() -> int:
    if not rds_configured():
        print("错误：RDS 未配置（.env 里要有 RDS_HOST/RDS_USER/RDS_PASSWORD）")
        return 1
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT USER()")
            u = cur.fetchone()[0]
    ip = u.split("@", 1)[1] if "@" in u else u
    print(f"RDS 看到的本机出口 IP: {ip}")
    print("→ 把这条加进阿里云 RDS 白名单即可（白名单是按连数据库的出口 IP 放行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
