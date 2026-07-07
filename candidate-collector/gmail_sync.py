from __future__ import annotations

import argparse
import email
import fcntl
import hashlib
import imaplib
import json
import os
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from email.header import decode_header
from email.message import Message
from pathlib import Path
from typing import Any

import fitz


ROOT = Path(__file__).resolve().parent
DOWNLOAD_DIR = ROOT / "data" / "gmail-attachments"
STATE_PATH = ROOT / "data" / "gmail-state.json"
LOCK_PATH = ROOT / "data" / "gmail-sync.lock"
KEYCHAIN_ACCOUNT = "ttc-candidate-collector"
EMAIL_SERVICE = "TTC_GMAIL_EMAIL"
PASSWORD_SERVICE = "TTC_GMAIL_APP_PASSWORD"
API_BASE = "http://127.0.0.1:8765"
DEFAULT_QUERY = (
    "after:2026/07/06 has:attachment "
    "{filename:pdf filename:doc filename:docx}"
)
RESUME_TERMS = re.compile(
    r"(简历|应聘|候选|人选|求职|人才|面试|推荐|resume|\bcv\b|candidate|application|curriculum)",
    re.I,
)
TARGET_ROLE_TERMS = re.compile(
    r"(新消费|消费品牌|品牌策略|品牌增长|品牌定位|战略咨询|消费战略|投后|"
    r"品牌孵化|品类策略|消费者洞察|consumer strategy|brand strategy|portfolio operation)",
    re.I,
)
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
SYNC_LOCK = threading.Lock()
LAST_STATUS: dict[str, Any] = {
    "state": "not_started",
    "message": "尚未同步",
    "downloaded": 0,
    "imported": 0,
    "skipped": 0,
    "errors": [],
}


def keychain_get(service: str) -> str:
    try:
        result = subprocess.run(
            [
                "security", "find-generic-password",
                "-a", KEYCHAIN_ACCOUNT, "-s", service, "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Gmail 尚未配置，请先运行 gmail_setup.py") from exc
    return result.stdout.strip()


def decode_text_header(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for part, charset in decode_header(value):
        if isinstance(part, bytes):
            parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(part)
    return "".join(parts)


def safe_filename(value: str) -> str:
    value = decode_text_header(value)
    value = value.replace("\\", "_").replace("/", "_").replace("\x00", "")
    while ".." in value:
        value = value.replace("..", "_")
    value = re.sub(r"[\r\n\t]+", " ", value).strip(" .")
    value = re.sub(r"\s+", " ", value)
    return value[:150] or "attachment"


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"attachment_hashes": [], "message_ids": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"attachment_hashes": [], "message_ids": []}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STATE_PATH)


def extract_word_text(path: Path) -> str:
    try:
        result = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(path)],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return ""
    return result.stdout.decode("utf-8", errors="replace").strip()


def no_proxy_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def import_attachment(path: Path, source_url: str) -> dict[str, Any]:
    opener = no_proxy_opener()
    if path.suffix.lower() == ".pdf":
        url = API_BASE + "/api/import-file?" + urllib.parse.urlencode({
            "filename": path.name,
            "platform": "Gmail",
            "source_type": "gmail_imap_attachment",
            "source_url": source_url,
        })
        request = urllib.request.Request(
            url,
            data=path.read_bytes(),
            headers={"Content-Type": "application/pdf"},
            method="POST",
        )
    else:
        text = extract_word_text(path)
        if len(text) < 20:
            raise RuntimeError("Word 文件没有提取到足够文字")
        body = json.dumps({
            "text": text,
            "title": path.name,
            "url": source_url,
        }, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            API_BASE + "/api/import-text",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def message_bytes(fetch_result: list[Any]) -> bytes:
    for item in fetch_result:
        if isinstance(item, tuple) and isinstance(item[1], bytes):
            return item[1]
    return b""


def attachment_parts(message: Message):
    for part in message.walk():
        filename = part.get_filename()
        if not filename:
            continue
        name = safe_filename(filename)
        if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        payload = part.get_payload(decode=True)
        if payload:
            yield name, payload


def is_target_resume(subject: str, filename: str, payload: bytes) -> bool:
    search_text = subject + " " + filename
    if TARGET_ROLE_TERMS.search(search_text):
        return True
    if Path(filename).suffix.lower() == ".pdf":
        try:
            document = fitz.open(stream=payload, filetype="pdf")
            extracted = "\n".join(page.get_text("text") for page in list(document)[:2])
            return bool(TARGET_ROLE_TERMS.search(extracted[:20000]))
        except Exception:
            return False
    return False


def sync_gmail(limit: int = 25, query: str = DEFAULT_QUERY) -> dict[str, Any]:
    global LAST_STATUS
    if not SYNC_LOCK.acquire(blocking=False):
        return {**LAST_STATUS, "state": "busy", "message": "已有 Gmail 同步正在运行"}
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = LOCK_PATH.open("a+")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_handle.close()
        SYNC_LOCK.release()
        return {**LAST_STATUS, "state": "busy", "message": "另一个进程正在同步 Gmail"}
    status: dict[str, Any] = {
        "state": "running",
        "message": "正在读取 Gmail",
        "downloaded": 0,
        "imported": 0,
        "skipped": 0,
        "errors": [],
    }
    LAST_STATUS = status
    connection: imaplib.IMAP4_SSL | None = None
    try:
        gmail_address = keychain_get(EMAIL_SERVICE)
        app_password = keychain_get(PASSWORD_SERVICE)
        connection = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
        connection.login(gmail_address, app_password)
        result, _ = connection.select("INBOX", readonly=True)
        if result != "OK":
            raise RuntimeError("无法以只读方式打开 Gmail 收件箱")
        result, data = connection.uid("SEARCH", None, "X-GM-RAW", f'"{query}"')
        if result != "OK":
            raise RuntimeError("Gmail 简历搜索失败")
        uids = data[0].split()[-limit:]
        state = load_state()
        known_hashes = set(state.get("attachment_hashes", []))
        known_messages = set(state.get("message_ids", []))
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

        for uid in reversed(uids):
            size_result, size_data = connection.uid("FETCH", uid, "(RFC822.SIZE)")
            size_blob = b" ".join(
                item if isinstance(item, bytes) else item[0]
                for item in size_data
                if isinstance(item, (bytes, tuple))
            )
            size_match = re.search(rb"RFC822\.SIZE\s+(\d+)", size_blob)
            if size_result == "OK" and size_match and int(size_match.group(1)) > 16 * 1024 * 1024:
                status["skipped"] += 1
                status["errors"].append("跳过超过16MB的邮件 UID " + uid.decode(errors="ignore"))
                continue
            result, fetched = connection.uid("FETCH", uid, "(BODY.PEEK[])")
            if result != "OK":
                status["errors"].append("邮件读取失败 UID " + uid.decode(errors="ignore"))
                continue
            raw = message_bytes(fetched)
            if not raw:
                continue
            message = email.message_from_bytes(raw)
            message_id = (message.get("Message-ID") or uid.decode(errors="ignore")).strip()
            subject = decode_text_header(message.get("Subject"))
            source_url = "gmail://message/" + urllib.parse.quote(message_id, safe="")
            parts = list(attachment_parts(message))
            relevance_text = subject + " " + " ".join(filename for filename, _ in parts)
            if not RESUME_TERMS.search(relevance_text):
                status["skipped"] += len(parts) or 1
                continue
            target_parts = [
                (filename, payload)
                for filename, payload in parts
                if is_target_resume(subject, filename, payload)
            ]
            if not target_parts:
                status["skipped"] += len(parts) or 1
                continue
            found_attachment = False
            for filename, payload in target_parts:
                found_attachment = True
                digest = hashlib.sha256(payload).hexdigest()
                if digest in known_hashes:
                    status["skipped"] += 1
                    continue
                path = DOWNLOAD_DIR / (digest[:12] + "_" + filename)
                path.write_bytes(payload)
                status["downloaded"] += 1
                try:
                    import_attachment(path, source_url)
                    status["imported"] += 1
                    known_hashes.add(digest)
                except Exception as exc:
                    status["errors"].append(subject[:80] + " / " + filename + "：" + str(exc))
            if found_attachment:
                known_messages.add(message_id)
            state["attachment_hashes"] = sorted(known_hashes)
            state["message_ids"] = sorted(known_messages)[-5000:]
            save_state(state)

        status["state"] = "completed"
        status["message"] = (
            f"同步完成：下载 {status['downloaded']}，入库 {status['imported']}，"
            f"跳过重复 {status['skipped']}，错误 {len(status['errors'])}"
        )
        return status
    except Exception as exc:
        status["state"] = "failed"
        status["message"] = str(exc)
        status["errors"].append(str(exc))
        return status
    finally:
        if connection is not None:
            try:
                connection.logout()
            except Exception:
                pass
        LAST_STATUS = status
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()
        SYNC_LOCK.release()


def watch_loop(interval_seconds: int = 300) -> None:
    time.sleep(10)
    while True:
        sync_gmail()
        time.sleep(max(60, interval_seconds))


def start_watcher(interval_seconds: int = 300) -> threading.Thread:
    thread = threading.Thread(
        target=watch_loop,
        args=(interval_seconds,),
        name="gmail-resume-sync",
        daemon=True,
    )
    thread.start()
    return thread


def main() -> int:
    parser = argparse.ArgumentParser(description="只读同步 Gmail 简历附件")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args()
    if args.watch:
        while True:
            result = sync_gmail(limit=args.limit, query=args.query)
            print(json.dumps(result, ensure_ascii=False))
            time.sleep(max(60, args.interval))
    result = sync_gmail(limit=args.limit, query=args.query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
