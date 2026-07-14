#!/usr/bin/env python3
"""
通过 TTC TalentStore API 批量导入 FA 候选人至飞书人才库。

用法：
    export TTC_JWT_TOKEN=eyJhbGci...
    uv run python scripts/bulk_import_ttc_fa_to_feishu.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

TTC_API_BASE = "https://api.ttcadvisory.com"
TTC_WEB_BASE = "https://app.ttcadvisory.com"
IMPORT_API = "http://127.0.0.1:8765/api/import-browser-capture"


def _headers(token: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
        "accept": "application/json, text/plain, */*",
        "origin": "https://app.ttcadvisory.com",
        "referer": "https://app.ttcadvisory.com/",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        ),
    }


def search_ttc_talent(keyword: str, token: str, page: int = 1, page_size: int = 100) -> list[dict[str, Any]]:
    url = f"{TTC_API_BASE}/api/talent_store/v1/search"
    payload = {
        "keyword": keyword,
        "page_size": page_size,
        "current_page": page,
        "filter": {
            "locations": ["不限"],
            "degree": ["不限"],
            "university_category": ["不限"],
            "overseas_experience": ["不限"],
            "age_range": ["", ""],
            "has_system_tag_gulu": False,
            "has_system_tag_ttc": False,
            "has_mobile": False,
            "has_raw_resume": False,
        },
        "colors": "",
        "names": [],
        "companies": [],
        "titles": [],
        "keyword_type": 2,
        "company_type": 2,
    }
    resp = requests.post(url, headers=_headers(token), json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        return []
    nested = data.get("data") or {}
    if not isinstance(nested, dict):
        return []
    items = nested.get("person_leads_items", []) or []
    return items


def is_rd_candidate(item: dict[str, Any]) -> bool:
    """Filter out noise and keep real R&D / engineering profiles."""
    title = (item.get("job_title") or "").lower()
    tags = [str(t).lower() for t in (item.get("tags") or item.get("system_tags") or []) if t]
    text_to_check = title + " " + " ".join(tags)
    keywords = [
        "研发", "工程师", "技术", "算法", "开发", "架构师", "程序员",
        "前端", "后端", "全栈", "客户端", "测试", "运维", "大数据",
        "人工智能", "机器学习", "深度学习", "nlp", "cv",
    ]
    return any(k in text_to_check for k in keywords)


def build_candidate_text(item: dict[str, Any]) -> str:
    """把 TTC search item 转成 parser 易读的文本。"""
    lines = []
    name = item.get("cn_name") or item.get("en_name") or "未知"
    lines.append(name)
    lines.append(f"年龄: {item.get('age') or '未知'}")
    lines.append(f"学历: {item.get('degree') or '未知'}")
    lines.append(f"当前职位: {item.get('job_title') or '未知'}")
    lines.append(f"地点: {item.get('locations_display') or item.get('locations') or '未知'}")

    work = item.get("work_information") or []
    if work:
        lines.append("工作经历:")
        for w in work:
            lines.append(
                f"{w.get('company', '')} | {w.get('job_title', '')} | "
                f"{w.get('start_time', '')} 至 {w.get('end_time', '')}"
            )
            for key in ("formatted_company",):
                if w.get(key) and w.get(key) != w.get("company"):
                    lines.append(f"  ({key}: {w.get(key)})")

    edu = item.get("education_information") or []
    if edu:
        lines.append("教育经历:")
        for e in edu:
            lines.append(
                f"{e.get('school', '')} | {e.get('degree', '')} | {e.get('major', '')} | "
                f"{e.get('start_time', '')} 至 {e.get('end_time', '')}"
            )

    tags = item.get("tags") or item.get("system_tags") or []
    if tags:
        lines.append(f"标签: {', '.join(str(t) for t in tags if t)}")

    return "\n".join(lines)


def import_to_feishu(person_leads_id: str, name: str, text: str, token: str) -> dict[str, Any]:
    url = f"{TTC_WEB_BASE}/app/talent/{person_leads_id}"
    payload = {
        "url": url,
        "title": name,
        "heading": name,
        "text": text,
        "platform": "ttc",
        "source_type": "browser_capture",
        "skip_duplicates": True,
        "check_feishu_exists": False,
    }
    try:
        resp = requests.post(IMPORT_API, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def main() -> int:
    token = os.environ.get("TTC_JWT_TOKEN", "")
    if not token:
        # Try repo .env
        env_path = REPO_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("TTC_JWT_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        print("错误：未配置 TTC_JWT_TOKEN", file=sys.stderr)
        return 1

    keyword = "研发"
    max_import = 200
    print(f"[1/3] 搜索 TTC 关键词：{keyword}，最多导入 {max_import} 人")
    all_items: list[dict[str, Any]] = []
    page = 1
    while True:
        items = search_ttc_talent(keyword, token, page=page, page_size=100)
        print(f"  第 {page} 页返回 {len(items)} 条")
        if not items:
            break
        all_items.extend(items)
        if len(items) < 100:
            break
        if len(all_items) >= max_import * 3:
            break
        page += 1

    # 去重 + 过滤真实研发岗位
    def is_rd(item: dict[str, Any]) -> bool:
        keywords = [
            "研发", "工程师", "技术", "算法", "开发", "架构师", "程序员",
            "前端", "后端", "全栈", "客户端", "测试", "运维", "大数据",
            "人工智能", "机器学习", "深度学习", "nlp", "cv",
        ]
        # Check current job title
        title = (item.get("job_title") or "").lower()
        if any(k in title for k in keywords):
            return True
        # Check work history titles
        for w in item.get("work_information") or []:
            wt = (w.get("job_title") or "").lower()
            if any(k in wt for k in keywords):
                return True
        # Check tags
        for t in item.get("tags") or item.get("system_tags") or []:
            if any(k in str(t).lower() for k in keywords):
                return True
        return False

    seen: dict[str, dict[str, Any]] = {}
    for item in all_items:
        if not is_rd(item):
            continue
        pid = item.get("person_leads_id")
        if pid:
            seen[str(pid)] = item
    items = list(seen.values())[:max_import]
    print(f"[2/3] 去重并过滤真实研发岗位后共 {len(items)} 个候选人，开始导入飞书...")

    created = 0
    skipped = 0
    failed = 0
    for idx, item in enumerate(items, 1):
        pid = item.get("person_leads_id")
        name = item.get("cn_name") or item.get("en_name") or "未知"
        print(f"  {idx}/{len(items)} {name} ...", end=" ", flush=True)
        text = build_candidate_text(item)
        result = import_to_feishu(str(pid), name, text, token)
        action = result.get("action", "")
        if result.get("ok") and action == "created":
            created += 1
            print("created", flush=True)
        elif result.get("ok") and "duplicate" in action:
            skipped += 1
            print("skipped", flush=True)
        else:
            failed += 1
            print(f"failed: {result.get('error', action)}", flush=True)
        if idx < len(items):
            time.sleep(0.3)

    print(f"\n[3/3] 完成：导入 {created} / 跳过 {skipped} / 失败 {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
