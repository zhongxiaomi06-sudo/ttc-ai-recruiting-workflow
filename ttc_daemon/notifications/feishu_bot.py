"""Feishu Bot 通知：新的人类任务生成时推送给猎头/顾问。"""
import json
import logging
from typing import Any, Dict, Optional

import requests

from ..config import FEISHU_BOT_CONFIG

logger = logging.getLogger(__name__)


def _webhook_url() -> Optional[str]:
    return FEISHU_BOT_CONFIG.get("webhook_url", "") or None


def notify_new_task(task: Dict[str, Any], dashboard_url: str = "") -> bool:
    """发送新任务通知到飞书群机器人。"""
    url = _webhook_url()
    if not url:
        return False

    payload = task.get("payload", "{}")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    task_type_labels = {
        "call": "📞 打电话",
        "review": "🔍 审核",
        "compliance": "🛡️ 合规",
        "jd_clarify": "❓ JD 澄清",
        "source_help": "🔎 寻访协助",
        "read_failed": "❌ 读取失败",
        "login_required": "🔐 登录受限",
        "classify_uncertain": "📂 分类不确定",
    }
    label = task_type_labels.get(task.get("task_type"), "📝 新任务")
    task_url = dashboard_url.rstrip("/") + task.get("html_url", f"/human/task/{task['id']}")

    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{label}：{task.get('role', '猎头')}"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"任务 ID：**{task['id']}**\n类型：**{task.get('task_type', '')}**\n状态：**{task.get('status', '')}**",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "打开任务页"},
                            "url": task_url,
                            "type": "primary",
                        }
                    ],
                },
            ],
        },
    }

    try:
        resp = requests.post(url, json=card, timeout=15)
        resp.raise_for_status()
        logger.info("Feishu bot notified for task %s", task["id"])
        return True
    except Exception as e:
        logger.warning("Feishu bot notify failed: %s", e)
        return False


def notify_problem(task: Dict[str, Any], problem: str, dashboard_url: str = "") -> bool:
    """发送异常任务通知。"""
    url = _webhook_url()
    if not url:
        return False

    task_url = dashboard_url.rstrip("/") + task.get("html_url", f"/human/task/{task['id']}")
    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "⚠️ AI 遇到异常，需要人介入"},
                "template": "red",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"问题：{problem[:200]}\n任务 ID：{task['id']}",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "处理异常"},
                            "url": task_url,
                            "type": "danger",
                        }
                    ],
                },
            ],
        },
    }

    try:
        resp = requests.post(url, json=card, timeout=15)
        resp.raise_for_status()
        logger.info("Feishu problem notified for task %s", task["id"])
        return True
    except Exception as e:
        logger.warning("Feishu problem notify failed: %s", e)
        return False
