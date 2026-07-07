import re
import time
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import requests

from .config import WEB_READER_CONFIG, FILE_READER_CONFIG

logger = logging.getLogger(__name__)

# ChatGPT / OpenAI share links need a real browser to render the conversation.
CHATGPT_SHARE_RE = re.compile(r"https?://(chatgpt\.com|chat\.openai\.com)/share/", re.I)


def is_chatgpt_share(url: str) -> bool:
    return bool(CHATGPT_SHARE_RE.search(url))


def fetch_static(url: str, timeout: int = 20) -> Optional[str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning(f"Static fetch failed for {url}: {e}")
        return None


def fetch_with_firecrawl(url: str, timeout: int = 45) -> Optional[Dict[str, Any]]:
    api_key = WEB_READER_CONFIG.get("firecrawl_api_key")
    if not api_key:
        return None

    base_url = WEB_READER_CONFIG.get("firecrawl_base_url", "https://api.firecrawl.dev").rstrip("/")
    endpoint = f"{base_url}/v2/scrape"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"url": url, "formats": ["markdown", "html"]}
    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Firecrawl fetch failed for %s: %s", url, e)
        return None

    body = data.get("data", data) if isinstance(data, dict) else {}
    if not isinstance(body, dict):
        return None
    markdown = body.get("markdown") or ""
    html = body.get("html") or ""
    text = markdown.strip() or (html_to_text(html) if html else "")
    if not text.strip():
        return None
    metadata = body.get("metadata") or {}
    return {
        "title": metadata.get("title", ""),
        "raw_text": text,
        "markdown": markdown or text,
        "dom_text": html_to_text(html) if html else text,
        "script_payload": {"firecrawl": {"metadata": metadata}},
        "method": "firecrawl",
    }


def fetch_with_crawl4ai(url: str) -> Optional[Dict[str, Any]]:
    if not WEB_READER_CONFIG.get("crawl4ai_enabled"):
        return None
    try:
        import asyncio
        from crawl4ai import AsyncWebCrawler
    except Exception as e:
        logger.warning("Crawl4AI not available: %s", e)
        return None

    async def _run() -> Any:
        async with AsyncWebCrawler() as crawler:
            return await crawler.arun(url=url)

    try:
        result = asyncio.run(_run())
    except Exception as e:
        logger.warning("Crawl4AI fetch failed for %s: %s", url, e)
        return None

    markdown = getattr(result, "markdown", "") or ""
    html = getattr(result, "html", "") or ""
    text = markdown.strip() or (html_to_text(html) if html else "")
    if not text.strip():
        return None
    return {
        "title": getattr(result, "title", "") or "",
        "raw_text": text,
        "markdown": markdown or text,
        "dom_text": html_to_text(html) if html else text,
        "script_payload": {"crawl4ai": {"success": getattr(result, "success", None)}},
        "method": "crawl4ai",
    }


def fetch_with_playwright(url: str, wait_seconds: int = 3, chatgpt: bool = False) -> Optional[str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright not installed, skipping browser fallback")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)

            if chatgpt:
                # ChatGPT share pages render the conversation from JSON; wait for it.
                try:
                    page.wait_for_selector(
                        "main, article, [data-testid='conversation-turn']",
                        timeout=15000,
                    )
                except Exception as e:
                    logger.warning(f"ChatGPT content selector wait timed out: {e}")

            if wait_seconds:
                time.sleep(wait_seconds)

            # Prefer <main>, then <article>, then <body>.
            for selector in ("main", "article", "body"):
                loc = page.locator(selector).first
                try:
                    if loc.is_visible():
                        text = loc.inner_text()
                        if text.strip():
                            break
                except Exception:
                    continue
            else:
                text = ""

            browser.close()
            return text
    except Exception as e:
        logger.warning(f"Playwright fetch failed for {url}: {e}")
        return None


def html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text("\n", strip=True)
    except ImportError:
        # 极简兜底
        text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.I)
        text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def clean_chatgpt_text(text: str) -> str:
    """Remove common boilerplate from ChatGPT share-page text extraction."""
    lines = text.splitlines()
    skip_prefixes = (
        "Skip to content",
        "Chat history",
        "New chat",
        "Search chats",
        "Images",
        "Apps",
        "Deep research",
        "See plans and pricing",
        "Settings",
        "Help",
        "Get responses tailored to you",
        "Log in to get answers",
        "Log in",
        "Sign up for free",
        "ChatGPT",
        "This is a copy of a shared ChatGPT conversation",
        "Report conversation",
        "Uploaded a file",
        "Uploaded an image",
        "Voice",
        "ChatGPT is AI and can make mistakes.",
        "We use cookies",
        "Cookies help this site",
        "Manage your cookie preferences",
        "Learn more about our cookie policy",
        "Reject non-essential",
        "Accept all",
    )
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(p) or stripped == p for p in skip_prefixes):
            continue
        cleaned.append(stripped)
    return "\n\n".join(cleaned)


def _record(
    *,
    url: str,
    title: str,
    text: str,
    markdown: str,
    method: str,
    content_type_guess: str,
    error: str = "",
    error_reason: str = "",
    dom_text: str = "",
    script_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    status = "succeeded" if text.strip() and not error else ("empty" if not text.strip() else "failed")
    return {
        "source_type": "web_page",
        "source_url": url,
        "title": title,
        "raw_text": text,
        "markdown": markdown or text,
        "dom_text": dom_text or text,
        "script_payload": script_payload or {},
        "read_status": status,
        "content_type_guess": content_type_guess,
        "error_reason": error_reason,
        "error": error,
        "read_method": method,
        "method": method,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def read_file(path: str) -> Dict[str, Any]:
    """读取本地文件：优先 MarkItDown，失败时返回 needs_human 诊断。"""
    file_path = Path(path).expanduser()
    content_type_guess = "candidate" if file_path.suffix.lower() in {".pdf", ".doc", ".docx"} else "unknown"
    if not file_path.exists() or not file_path.is_file():
        return _record(
            url=str(file_path),
            title=file_path.name,
            text="",
            markdown="",
            method="file_missing",
            content_type_guess=content_type_guess,
            error=f"文件不存在：{file_path}",
            error_reason="file_missing",
        )

    if FILE_READER_CONFIG.get("prefer") == "markitdown":
        try:
            from markitdown import MarkItDown
            result = MarkItDown().convert(str(file_path))
            text = getattr(result, "text_content", "") or str(result)
            if text.strip():
                return _record(
                    url=str(file_path),
                    title=file_path.name,
                    text=text,
                    markdown=text,
                    method="markitdown",
                    content_type_guess=content_type_guess,
                    script_payload={"file": {"suffix": file_path.suffix}},
                )
        except Exception as e:
            logger.warning("MarkItDown failed for %s: %s", file_path, e)

    try:
        text = file_path.read_text(encoding="utf-8")
        return _record(
            url=str(file_path),
            title=file_path.name,
            text=text,
            markdown=text,
            method="plain_text_file",
            content_type_guess=content_type_guess,
        )
    except Exception as e:
        return _record(
            url=str(file_path),
            title=file_path.name,
            text="",
            markdown="",
            method="file_failed",
            content_type_guess=content_type_guess,
            error=f"文件读取失败：{e}",
            error_reason="unsupported_file",
        )


def read_url(url: str) -> Dict[str, Any]:
    """读取任意 URL：先静态 fetch，ChatGPT share link / 动态页用 Playwright 兜底。"""
    logger.info(f"Reading URL: {url}")
    chatgpt = is_chatgpt_share(url)
    content_type_guess = "chat" if chatgpt else "unknown"

    if chatgpt:
        # ChatGPT share pages only expose the shell in static HTML.
        text = fetch_with_playwright(url, chatgpt=True)
        method = "playwright"
    else:
        tool_result = None
        prefer = WEB_READER_CONFIG.get("prefer", "auto")
        if prefer in {"auto", "firecrawl"}:
            tool_result = fetch_with_firecrawl(url)
        if tool_result is None and prefer in {"auto", "crawl4ai"}:
            tool_result = fetch_with_crawl4ai(url)
        if tool_result is not None:
            return _record(
                url=url,
                title=tool_result.get("title", ""),
                text=tool_result.get("raw_text", ""),
                markdown=tool_result.get("markdown", ""),
                dom_text=tool_result.get("dom_text", ""),
                script_payload=tool_result.get("script_payload", {}),
                method=tool_result.get("method", "external_reader"),
                content_type_guess=content_type_guess,
            )

        html = fetch_static(url)
        method = "requests"
        if html is None:
            html = fetch_with_playwright(url)
            method = "playwright"
        text = html_to_text(html) if html else ""

    if not text:
        return _record(
            url=url,
            title="",
            text="",
            markdown="",
            method="failed",
            content_type_guess=content_type_guess,
            error="无法读取页面（成熟工具、静态读取和 Playwright 均失败）",
            error_reason="empty_content",
        )

    title = ""
    if method == "requests" and html:
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        if title_match:
            title = title_match.group(1).strip()
    else:
        # For Playwright, derive title from first heading or page title.
        first_line = text.splitlines()[0] if text else ""
        title = first_line.strip() if first_line else ""

    if chatgpt:
        text = clean_chatgpt_text(text)
    if not text.strip():
        return _record(
            url=url,
            title=title,
            text="",
            markdown="",
            method=method,
            content_type_guess=content_type_guess,
            error="页面读取成功但正文为空",
            error_reason="empty_content",
        )

    return _record(
        url=url,
        title=title,
        text=text,
        markdown=text,
        method=method,
        content_type_guess=content_type_guess,
    )
