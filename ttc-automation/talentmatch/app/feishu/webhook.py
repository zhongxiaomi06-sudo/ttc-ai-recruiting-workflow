"""Feishu webhook routes — event subscription + card actions"""
from __future__ import annotations
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from loguru import logger

from storage import get_storage
from .handlers import (
    handle_file_message, handle_image_message, handle_text_message,
    handle_ai_conversation,
)

router = APIRouter(prefix="/webhook", tags=["feishu"])


async def _handle_post_message(feishu, message_id, chat_id, user_id, chat_type,
                                match_pipeline, resume_pipeline):
    """Handle rich-text post messages by extracting text"""
    content = json.loads(message.get("content", "{}"))
    text_parts = []
    for line in content.get("content", []):
        for elem in line:
            if elem.get("tag") == "text":
                text_parts.append(elem.get("text", ""))
    text = " ".join(text_parts).strip()
    if text:
        wrapped = {"content": json.dumps({"text": text})}
        await handle_text_message(feishu, wrapped, message_id, chat_id, user_id,
                                   chat_type, match_pipeline, resume_pipeline)


async def _handle_audio_message(feishu, message_id, chat_id, user_id):
    feishu.reply_message(message_id, "🎤 语音消息功能开发中，敬请期待！")


@router.post("/event")
async def webhook_event(request: Request):
    body = await request.json()

    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body["challenge"]})

    header = body.get("header", {})
    event = body.get("event", {})
    event_type = header.get("event_type", "")

    if event_type != "im.message.receive_v1":
        return JSONResponse({"code": 0})

    message = event.get("message", {})
    sender = event.get("sender", {})
    message_id = message.get("message_id", "")
    chat_id = message.get("chat_id", "")
    chat_type = message.get("chat_type", "")
    msg_type = message.get("message_type", "")
    user_id = sender.get("sender_id", {}).get("open_id", "")

    from app import get_pipelines
    pl = get_pipelines()
    feishu = pl.get("feishu")
    resume_pipeline = pl.get("resume_pipeline")
    match_pipeline = pl.get("match_pipeline")

    if not feishu:
        logger.error("Feishu client not initialized")
        return JSONResponse({"code": 500, "message": "Feishu client not ready"})

    if msg_type == "file":
        await handle_file_message(feishu, message_id, chat_id,
                                   user_id, chat_type, resume_pipeline)
    elif msg_type == "image":
        await handle_image_message(feishu, message_id, chat_id,
                                    user_id, resume_pipeline)
    elif msg_type == "text":
        await handle_text_message(feishu, message_id, chat_id,
                                   user_id, chat_type, match_pipeline,
                                   resume_pipeline)
    elif msg_type == "post":
        await _handle_post_message(feishu, message_id, chat_id,
                                    user_id, chat_type, match_pipeline,
                                    resume_pipeline)
    elif msg_type == "audio":
        await _handle_audio_message(feishu, message_id, chat_id, user_id)
    else:
        logger.warning(f"Unhandled message type: {msg_type}")

    return JSONResponse({"code": 0})


@router.post("/card")
async def card_action(request: Request):
    body = await request.json()
    action = body.get("action", {})
    value = action.get("value", {})
    action_type = value.get("action", "")
    entity_id = value.get("candidate_id", "")
    user_id = body.get("open_id", "")

    if action_type == "like":
        get_storage().save_feedback("candidate", entity_id, "like", "", user_id)
    elif action_type == "dislike":
        get_storage().save_feedback("candidate", entity_id, "dislike", "", user_id)
    elif action_type == "raw":
        candidate = get_storage().get_candidate(entity_id)
        if candidate and candidate.get("raw_text"):
            return JSONResponse({
                "content": {"text": candidate["raw_text"][:2000]},
                "msg_type": "text",
            })

    return JSONResponse({"code": 0})
