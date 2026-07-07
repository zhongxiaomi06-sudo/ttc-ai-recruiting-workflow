"""Link Reader Agent for TTC Daemon.

Reads content from various link types:
- ChatGPT share links (via Playwright, because direct fetch is blocked).
- Generic public web pages (requests + BeautifulSoup, with Playwright fallback).
- PDF files (download + pdfminer).

All raw snapshots are saved under data/links/<hash>/ for auditability.
"""

import asyncio
import hashlib
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).resolve().parent / "data" / "links"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _snapshot_dir(url: str) -> Path:
    d = DATA_DIR / _url_hash(url)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_meta(url: str, data: dict[str, Any]) -> None:
    d = _snapshot_dir(url)
    meta_path = d / "meta.json"
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_raw_html(url: str, html: str) -> None:
    d = _snapshot_dir(url)
    (d / "raw.html").write_text(html, encoding="utf-8")


def _save_text(url: str, text: str, suffix: str = "extracted.txt") -> None:
    d = _snapshot_dir(url)
    (d / suffix).write_text(text, encoding="utf-8")


def _requests_get(url: str, timeout: int = 20) -> requests.Response:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    return requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)


def _extract_article_text(soup: BeautifulSoup) -> str:
    # Try common article containers
    for selector in ["article", "main", "[role='main']", ".post-content", ".entry-content", ".content"]:
        el = soup.select_one(selector)
        if el and len(el.get_text(strip=True)) > 200:
            return el.get_text(separator="\n", strip=True)
    # Fallback to body, removing nav/footer/script/style
    body = soup.body
    if body:
        for tag in body.find_all(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return body.get_text(separator="\n", strip=True)
    return soup.get_text(separator="\n", strip=True)


def is_chatgpt_share_url(url: str) -> bool:
    return bool(re.search(r"chatgpt\.com/share/|chat\.openai\.com/share/", url))


def is_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.lower().endswith(".pdf")


async def read_chatgpt_share(url: str) -> dict[str, Any]:
    """Use Playwright to render a ChatGPT share page and extract conversation turns."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright not installed. Run: playwright install") from exc

    messages = []
    raw_html = ""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait for conversation turns to appear
            await page.wait_for_selector('[data-testid="conversation-turn"]', timeout=30000)
            # Allow dynamic content to settle
            await asyncio.sleep(2)
            raw_html = await page.content()
            turns = await page.query_selector_all('[data-testid="conversation-turn"]')
            for turn in turns:
                role_el = await turn.query_selector('[data-message-author-role]')
                role = await role_el.get_attribute("data-message-author-role") if role_el else "unknown"
                text = await turn.inner_text()
                if text.strip():
                    messages.append({"role": role, "text": text.strip()})
        finally:
            await browser.close()

    _save_raw_html(url, raw_html)
    markdown = "\n\n---\n\n".join(f"**{m['role']}**:\n{m['text']}" for m in messages)
    _save_text(url, markdown, "extracted.md")
    result = {
        "source_type": "chatgpt_share",
        "source_url": url,
        "title": "ChatGPT Share Conversation",
        "messages": messages,
        "markdown": markdown,
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "access_basis": "public_share_page",
    }
    _save_meta(url, result)
    return result


def read_pdf(url: str) -> dict[str, Any]:
    from pdfminer.high_level import extract_text

    resp = _requests_get(url, timeout=30)
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name
    text = extract_text(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    _save_text(url, text, "extracted.txt")
    result = {
        "source_type": "pdf",
        "source_url": url,
        "title": Path(urlparse(url).path).name,
        "text": text,
        "markdown": text,
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "access_basis": "public",
    }
    _save_meta(url, result)
    return result


def read_generic_http(url: str) -> dict[str, Any]:
    resp = _requests_get(url)
    resp.raise_for_status()
    raw_html = resp.text
    _save_raw_html(url, raw_html)
    soup = BeautifulSoup(raw_html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    text = _extract_article_text(soup)
    _save_text(url, text, "extracted.txt")
    result = {
        "source_type": "web_page",
        "source_url": url,
        "title": title,
        "text": text,
        "markdown": text,
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "access_basis": "public",
    }
    _save_meta(url, result)
    return result


async def read_generic_playwright(url: str) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright not installed. Run: playwright install") from exc

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
            raw_html = await page.content()
            title = await page.title()
            text = await page.inner_text("body")
        finally:
            await browser.close()

    _save_raw_html(url, raw_html)
    _save_text(url, text, "extracted.txt")
    result = {
        "source_type": "web_page_playwright",
        "source_url": url,
        "title": title,
        "text": text,
        "markdown": text,
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "access_basis": "public",
    }
    _save_meta(url, result)
    return result


async def read_link(url: str, use_playwright: bool = False) -> dict[str, Any]:
    """Route URL to the appropriate reader."""
    if is_chatgpt_share_url(url):
        return await read_chatgpt_share(url)
    if is_pdf_url(url):
        return read_pdf(url)
    if use_playwright:
        return await read_generic_playwright(url)
    try:
        return read_generic_http(url)
    except Exception as exc:
        # Fallback to Playwright if static fetch fails
        return await read_generic_playwright(url)


if __name__ == "__main__":
    # Quick manual test
    test_url = "https://chatgpt.com/share/6a4c68e9-6bb0-83ec-a5d1-878879a09705"
    res = asyncio.run(read_link(test_url))
    print(json.dumps(res, ensure_ascii=False, indent=2))
