"""Feishu notification helper using the local lark-cli.

Set TTC_FEISHU_NOTIFY_ENABLED=true and TTC_FEISHU_CHAT_ID=oc_xxx in .env.
The bot must be a member of the chat.
"""

import json
import os
import subprocess
from typing import Optional


def _chat_id() -> Optional[str]:
    return os.getenv("TTC_FEISHU_CHAT_ID")


def _enabled() -> bool:
    return os.getenv("TTC_FEISHU_NOTIFY_ENABLED", "").lower() == "true" and bool(_chat_id())


def send_text(text: str) -> dict:
    if not _enabled():
        return {"ok": False, "message": "Feishu notification disabled"}

    chat_id = _chat_id()
    cmd = [
        "lark-cli",
        "im", "+messages-send",
        "--as", "bot",
        "--chat-id", chat_id,
        "--msg-type", "text",
        "--text", text,
        "--json",
    ]
    try:
        # lark-cli may print update notices; suppress known env vars
        env = os.environ.copy()
        env["LARKSUITE_CLI_NO_UPDATE_NOTIFIER"] = "1"
        env["LARKSUITE_CLI_NO_SKILLS_NOTIFIER"] = "1"
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr or result.stdout}
        return {"ok": True, "response": json.loads(result.stdout)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def notify_new_task(task: dict, mission: dict) -> dict:
    task_type_map = {
        "phone_call": "📞 新电话任务",
        "client_review": "🔍 顾问审核任务",
        "problem_solve": "⚠️ 异常处理任务",
    }
    label = task_type_map.get(task.get("task_type"), "新任务")
    text = f"{label}\nMission: {mission.get('id', '')[:18]}\n任务: {task.get('id', '')[:18]}\n打开: http://127.0.0.1:8766/human/task/{task.get('id', '')}"
    return send_text(text)


def notify_mission_update(mission: dict) -> dict:
    text = f"📋 Mission 状态更新\nID: {mission.get('id', '')[:18]}\n状态: {mission.get('status')}"
    return send_text(text)
