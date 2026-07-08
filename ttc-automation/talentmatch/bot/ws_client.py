"""飞书长连接客户端 — 接收飞书事件 + 轮询消息作为 fallback
使用 lark-oapi SDK 建立 WebSocket 连接。
同时包含轮询机制，确保事件订阅未配通时也能收到消息。

运行: python3 -m bot.ws_client
"""
from __future__ import annotations
import json
import os
import sys
import time
import traceback
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import lark_oapi as lark
import requests
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level:^8}</level> | <level>{message}</level>")


class FeishuWSBridge:
    """飞书长连接客户端 — 支持 WebSocket + 消息轮询双通道"""

    def __init__(self):
        self.app_id = os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        self._feishu = None
        self._last_msg_id = None
        self._user_open_id = None
        self._chat_id = None
        self._sender_id = ""
        self._lock = threading.Lock()
        self._processed_msg_ids = set()
        self._processed_msg_ids_max = 10000

    @property
    def feishu(self):
        if self._feishu is None:
            from bot.feishu_client import FeishuClient
            self._feishu = FeishuClient()
        return self._feishu

    def _get_token(self):
        """Get tenant access token"""
        r = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret}
        )
        return r.json().get("tenant_access_token", "")

    def _poll_messages(self):
        """Poll for new messages every 10 seconds as WebSocket fallback."""
        logger.info("[POLL] 轮询线程已启动（10秒间隔）")
        last_check = int(time.time() * 1000)

        while self._running:
            try:
                time.sleep(10)
                token = self._get_token()
                if not token:
                    continue

                # Get recent messages from the user's chat
                if not self._chat_id:
                    # Known chat_id from bot's P2P chat with user
                    # Bot must have sent at least one message to create this chat
                    # Try hardcoded one first, fall back to listing
                    self._chat_id = "oc_838672c68f577fb378835b9c4c084bb0"
                    # Verify by getting recent messages
                    try:
                        v = requests.get(
                            f"https://open.feishu.cn/open-apis/im/v1/messages",
                            headers={"Authorization": f"Bearer {token}"},
                            params={
                                "container_id_type": "chat",
                                "container_id": self._chat_id,
                                "page_size": 1,
                                "sort_type": "ByCreateTimeDesc"
                            }
                        )
                        if v.json().get("code") != 0:
                            self._chat_id = None
                    except requests.RequestException:
                        self._chat_id = None

                if self._chat_id:
                    r = requests.get(
                        f"https://open.feishu.cn/open-apis/im/v1/messages",
                        headers={"Authorization": f"Bearer {token}"},
                        params={
                            "container_id_type": "chat",
                            "container_id": self._chat_id,
                            "page_size": 5,
                            "sort_type": "ByCreateTimeDesc"
                        }
                    )
                    items = r.json().get("data", {}).get("items", [])
                    for msg in items:
                        msg_id = msg.get("message_id", "")
                        create_time = int(msg.get("create_time", "0"))
                        sender_type = msg.get("sender", {}).get("sender_type", "")
                        
                        # Only process messages from users (not from bot itself)
                        if sender_type == "app" or create_time <= last_check:
                            continue
                        
                        # Dedup by message_id (avoid handling same msg from both WS and poll)
                        if hasattr(self, '_processed_msg_ids') and msg_id in self._processed_msg_ids:
                            continue
                        
                        msg_type = msg.get("msg_type", "")
                        content_raw = msg.get("body", {}).get("content", "{}")
                        
                        logger.info(f"[POLL] 新消息: {msg_type} id={msg_id[:16]}...")
                        self._process_message(msg_type, content_raw, msg_id, msg.get("chat_id", ""))
                        
                        # Track processed msg_id (keep last 50)
                        if not hasattr(self, '_processed_msg_ids'):
                            self._processed_msg_ids = set()
                        self._processed_msg_ids.add(msg_id)
                        if len(self._processed_msg_ids) > 50:
                            self._processed_msg_ids = set(list(self._processed_msg_ids)[-50:])

                    last_check = int(time.time() * 1000)

            except Exception as e:
                logger.error(f"[POLL] 轮询错误: {e}")
                time.sleep(30)

    def _process_message(self, msg_type: str, content_raw: str, message_id: str, chat_id: str):
        """处理收到的消息 — 转发到 main.py webhook 统一处理"""
        try:
            # 构建与飞书 Webhook 事件相同格式的 payload
            payload = {
                "header": {"event_type": "im.message.receive_v1"},
                "event": {
                    "message": {
                        "message_id": message_id,
                        "message_type": msg_type,
                        "chat_id": chat_id,
                        "content": content_raw
                    },
                    "sender": {
                        "sender_id": {"open_id": self._sender_id or "", "user_id": ""}
                    }
                }
            }
            
            # 转发到 main.py 的 webhook 端点
            resp = requests.post(
                "https://yorkteam.cn/webhook/event",
                json=payload,
                timeout=60
            )
            result = resp.json()
            logger.info(f"[WS_FWD] {msg_type} -> webhook: {result.get('code', 'ok')}")
            
            # 检测 LLM 不可用时的降级
            first_msg = msg_type == "text"
            if first_msg:
                content = json.loads(content_raw) if isinstance(content_raw, str) and content_raw.startswith('{') else {}
                text = content.get('text', content_raw) if isinstance(content, dict) else content_raw
                if '收到' in str(text)[:10]:
                    pass  # webhook 已处理
            
        except requests.exceptions.ConnectionError:
            logger.error("[WS] main.py webhook 不可用 (8878 端口未响应)")
            self.feishu.reply_message(message_id, '⚠️ 后台服务暂不可用，请稍后再试')
        except Exception as e:
            logger.error(f"[WS_FWD] 处理失败: {e}")
            # 不需要给用户发重复错误，webhook 端已经处理

    def handle_message(self, data: lark_oapi.im.v1.P2ImMessageReceiveV1) -> None:
        """Handle WebSocket event"""
        try:
            event = data.event
            if not event or not event.message:
                return
            message = event.message
            sender = event.sender
            msg_id = message.message_id or ""
            msg_type = message.message_type or ""
            content_raw = message.content or "{}"
            chat_id = message.chat_id or ""
            logger.info(f"[WS] 事件消息: {msg_type} id={msg_id[:16]}...")
            self._process_message(msg_type, content_raw, msg_id, chat_id)
        except Exception as e:
            logger.error(f"[WS] handle error: {e}")

    def start(self):
        """Start with WebSocket + polling thread"""
        if not self.app_id or not self.app_secret:
            logger.error("FEISHU_APP_ID / APP_SECRET not configured!")
            return

        self._running = True
        logger.info(f"Starting Feishu client (app_id={self.app_id[:8]}...)")
        
        # 启动时检测应用状态
        try:
            token = self._get_token()
            if token:
                r = requests.get("https://open.feishu.cn/open-apis/bot/v3/info",
                    headers={"Authorization": f"Bearer {token}"})
                status = r.json().get("bot", {}).get("activate_status", "unknown")
                status_map = {2: "审核中", 3: "已发布"}
                logger.info(f"App activate_status: {status} ({status_map.get(status, '未知')})")
                
                # 如果已发布，检测 chat_id 有效性
                if status == 3:
                    try:
                        v = requests.get("https://open.feishu.cn/open-apis/im/v1/messages",
                            headers={"Authorization": f"Bearer {token}"},
                            params={"container_id_type": "chat", "container_id": self._chat_id or "oc_838672c68f577fb378835b9c4c084bb0", "page_size": 1, "sort_type": "ByCreateTimeDesc"})
                        if v.json().get("code") == 0:
                            self._chat_id = self._chat_id or "oc_838672c68f577fb378835b9c4c084bb0"
                            logger.info(f"Chat verified: {self._chat_id}")
                    except (requests.RequestException, json.JSONDecodeError):
                        pass
        except Exception as e:
            logger.warning(f"App status check failed: {e}")

        # Start polling thread as fallback
        poll_thread = threading.Thread(target=self._poll_messages, daemon=True)
        poll_thread.start()

        # Start WebSocket
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self.handle_message)
            .build()
        )

        cli = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        logger.info("✅ 客户端就绪！10秒轮询已启动，等待事件...")
        try:
            cli.start()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"WS error: {e}")
        finally:
            self._running = False


def main():
    bridge = FeishuWSBridge()
    bridge.start()


if __name__ == "__main__":
    main()
