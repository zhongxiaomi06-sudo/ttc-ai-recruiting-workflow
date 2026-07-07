"""Web Enrichment Agent：用公开网络信息补全候选人画像。

复用成熟工具：
- GitHub REST API：项目、语言、贡献
- 公开个人主页/博客：Crawl4AI / Firecrawl / requests 兜底
- 脉脉/LinkedIn 等：需要登录态时返回 evidence 占位，不硬爬
"""
import json
import logging
import re
from typing import Dict, Any, Optional

import requests

from ..config import WEB_READER_CONFIG
from ..link_reader import read_url

logger = logging.getLogger(__name__)


def _extract_github_username(text: str) -> Optional[str]:
    m = re.search(r"github\.com/([A-Za-z0-9_-]{1,39})", text)
    return m.group(1) if m else None


def _fetch_github_user(username: str) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(f"https://api.github.com/users/{username}", timeout=15)
        if resp.status_code == 200:
            return resp.json()
        logger.warning("GitHub user %s fetch failed: %s", username, resp.status_code)
    except Exception as e:
        logger.warning("GitHub user %s error: %s", username, e)
    return None


def _fetch_github_repos(username: str, limit: int = 5) -> list:
    try:
        resp = requests.get(
            f"https://api.github.com/users/{username}/repos",
            params={"sort": "updated", "per_page": limit},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning("GitHub repos %s error: %s", username, e)
    return []


def _read_public_page(url: str) -> Optional[str]:
    if not url.startswith(("http://", "https://")):
        return None
    try:
        record = read_url(url)
        return record.get("raw_text", "")
    except Exception as e:
        logger.warning("Public page read failed %s: %s", url, e)
        return None


def enrich(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """基于已有候选人的 source_url / raw_profile 做全网补全。"""
    enriched = dict(candidate)
    profile = enriched.get("raw_profile", {}) or {}
    evidence = []

    # 1. GitHub 补全
    text_sources = [
        str(profile.get("source_url", "")),
        str(profile.get("summary", "")),
        str(profile.get("raw_text", "")),
    ]
    all_text = "\n".join(text_sources)
    gh_user = _extract_github_username(all_text)
    if gh_user:
        gh_profile = _fetch_github_user(gh_user)
        if gh_profile:
            evidence.append({
                "field": "github_profile",
                "source_url": gh_profile.get("html_url", ""),
                "raw_text": json.dumps(gh_profile, ensure_ascii=False),
                "confidence": "中",
                "access_basis": "public_github_api",
            })
            repos = _fetch_github_repos(gh_user)
            if repos:
                evidence.append({
                    "field": "github_repos",
                    "source_url": gh_profile.get("html_url", ""),
                    "raw_text": ", ".join(r.get("full_name", "") for r in repos),
                    "confidence": "中",
                    "access_basis": "public_github_api",
                })

    # 2. 公开个人主页/博客
    source_url = profile.get("source_url", "")
    if source_url and not source_url.startswith(("https://github.com", "http://github.com")):
        page_text = _read_public_page(source_url)
        if page_text:
            evidence.append({
                "field": "public_page",
                "source_url": source_url,
                "raw_text": page_text[:2000],
                "confidence": "低",
                "access_basis": "public_web_page",
            })

    enriched.setdefault("enriched_profile", {}).update({
        "github_username": gh_user,
        "evidence": evidence,
        "sources_checked": ["github", "public_page"],
    })
    enriched.setdefault("evidence", []).extend(evidence)
    return enriched
