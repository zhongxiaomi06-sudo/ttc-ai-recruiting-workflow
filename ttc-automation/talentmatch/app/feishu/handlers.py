"""Feishu bot message handlers — extracted from old main.py"""
from __future__ import annotations
import json
import os
import time
import re
from typing import Optional, Dict, List, Any
from loguru import logger
from openai import OpenAI

from app.config import settings
from storage import get_storage

import threading

# Conversation context store (in-memory)
_conversations: Dict[str, dict] = {}
_conversations_lock = threading.Lock()

AI_SYSTEM_PROMPT = """你是猎头简历助手「小猎」，帮助猎头分析简历、匹配岗位、回答招聘相关问题。

你的核心能力：
1. 📄 简历分析：解析简历中的技能、经验、项目，给出专业评估
2. 🎯 岗位匹配：比较候选人与岗位的匹配度，给出推荐
3. 📊 市场洞察：分析技术栈的行业趋势、薪资水平
4. 💡 招聘建议：提供面试问题、评估建议、谈薪策略

回复风格：专业简洁，用短段落和要点，使用中文。不确定的信息要标注出来。"""

HELP_TEXT = """🤖 猎头简历助手 · 命令列表

📄 简历处理:
  发送PDF/Word → 自动解析入库
  发送图片 → OCR识别解析
  /batch → 进入批量模式
  /done → 开始批量解析

🎯 岗位匹配:
  /match → 输入JD匹配候选人
  /search <关键词> → 搜索人才库

📊 查看:
  /stats → 查看系统统计
  /jobs → 查看活跃岗位
  /candidates → 查看最近入库人才

💬 其他:
  /feedback → 提交反馈
  /help → 显示此帮助

💡 提示: 直接发简历文件即可自动解析！"""


def get_context(chat_id: str) -> dict:
    """Get or create conversation context for a chat"""
    if chat_id not in _conversations:
        _conversations[chat_id] = {"mode": "", "history": [], "files": [], "context": {}}
    ctx = _conversations[chat_id]
    ctx["last_activity"] = time.time()
    return ctx


def cleanup_stale_contexts(max_age: int = 3600):
    """Remove conversation contexts older than max_age seconds"""
    now = time.time()
    stale = [k for k, v in _conversations.items()
             if now - v.get("last_activity", 0) > max_age]
    for k in stale:
        del _conversations[k]


async def handle_file_message(feishu, message_id, chat_id, user_id, chat_type,
                              resume_pipeline):
    content = json.loads(message.get("content", "{}"))
    file_key = content.get("file_key", "")
    file_name = content.get("file_name", "resume.pdf")

    feishu.reply_message(message_id, f"📥 收到文件: {file_name}\n🔍 正在解析...")

    file_path = feishu.download_file(message_id, file_key, file_name)
    if not file_path:
        feishu.reply_message(message_id, "❌ 文件下载失败，请重试")
        return

    ctx = get_context(chat_id)
    if ctx.get("mode") == "batch":
        batch = ctx.setdefault("files", [])
        batch.append(file_path)
        feishu.reply_message(message_id, f"📦 已加入批量队列 ({len(batch)} 份)，发送 /done 开始解析")
        return

    result = resume_pipeline.process_file(file_path, chat_id=chat_id, owner_id=user_id)
    if result.get("status") == "ok":
        logger.info(f"Processed: {result['name']} ({result['candidate_id']})")
    else:
        feishu.reply_message(message_id, f"❌ 解析失败: {result.get('error', '未知错误')[:200]}")


async def handle_image_message(feishu, message_id, chat_id, user_id,
                               resume_pipeline):
    content = json.loads(message.get("content", "{}"))
    image_key = content.get("image_key", "")

    feishu.reply_message(message_id, "🖼️ 收到图片，正在OCR识别...")

    file_path = feishu.download_image(message_id, image_key)
    if not file_path:
        feishu.reply_message(message_id, "❌ 图片下载失败")
        return

    result = resume_pipeline.process_file(file_path, chat_id=chat_id, owner_id=user_id)
    if result.get("status") == "ok":
        logger.info(f"OCR processed: {result['name']}")
    else:
        feishu.reply_message(message_id, f"❌ OCR解析失败: {result.get('error', '')[:200]}")


async def handle_text_message(feishu, message_id, chat_id, user_id, chat_type,
                              match_pipeline, resume_pipeline):
    content = json.loads(message.get("content", "{}"))
    text = content.get("text", "").strip()
    text = re.sub(r'@_user_\d+', '', text).strip()

    if not text:
        return

    if text.startswith("/"):
        await handle_command(feishu, text, message_id, chat_id, user_id,
                             match_pipeline, resume_pipeline)
        return

    ctx = get_context(chat_id)

    if ctx.get("mode") == "waiting_jd":
        _conversations[chat_id] = {"mode": "", "history": [], "files": [], "context": {},
                                   "last_activity": time.time()}
        feishu.reply_message(message_id, "🔍 正在匹配候选人...")
        match_pipeline.match_jd(text, chat_id=chat_id, source="feishu")
        return

    if ctx.get("mode") == "waiting_feedback":
        entity_id = ctx.get("context", {}).get("entity_id", "")
        get_storage().save_feedback("candidate", entity_id, "text", text, user_id)
        _conversations[chat_id] = {"mode": "", "history": [], "files": [], "context": {},
                                   "last_activity": time.time()}
        feishu.reply_message(message_id, "✅ 反馈已记录，谢谢！系统会根据反馈持续优化。")
        return

    await handle_ai_conversation(feishu, text, message_id, chat_id, user_id)


async def handle_command(feishu, text, message_id, chat_id, user_id,
                         match_pipeline, resume_pipeline):
    cmd = text.split()[0].lower()
    args = text[len(cmd):].strip()

    if cmd in ("/help", "/帮助"):
        feishu.reply_message(message_id, HELP_TEXT)

    elif cmd == "/batch":
        _conversations[chat_id] = {"mode": "batch", "files": [],
                                   "history": [], "context": {},
                                   "last_activity": time.time()}
        feishu.reply_message(message_id, "📦 批量模式已开启！\n请逐个发送简历文件，发送 /done 开始解析")

    elif cmd == "/done":
        ctx = get_context(chat_id)
        files = ctx.get("files", [])
        if not files:
            feishu.reply_message(message_id, "⚠️ 批量队列为空，请先发送简历文件")
            return
        feishu.reply_message(message_id, f"🚀 开始批量解析 {len(files)} 份简历...")
        result = resume_pipeline.process_batch(files, chat_id=chat_id, owner_id=user_id)
        _conversations[chat_id] = {"mode": "", "history": [], "files": [], "context": {},
                                   "last_activity": time.time()}

    elif cmd == "/match":
        _conversations[chat_id] = {"mode": "waiting_jd", "history": [], "files": [],
                                   "context": {}, "last_activity": time.time()}
        feishu.reply_message(message_id, "📝 请发送职位描述（JD）文本")

    elif cmd == "/search":
        if not args:
            feishu.reply_message(message_id, "⚠️ 请输入搜索关键词，例如: /search Python 后端")
            return
        results = get_storage().search_candidates(args, limit=10)
        if not results:
            feishu.reply_message(message_id, f"未找到匹配「{args}」的候选人")
            return
        lines = [f"• {c.get('name', '')} - {c.get('current_role', '')} @ {c.get('current_company', '')}"
                 f" (匹配分: {c.get('ats_score', 0)})"
                 for c in results]
        feishu.reply_message(message_id, f"🔍 搜索「{args}」结果:\n" + "\n".join(lines))

    elif cmd == "/stats":
        stats = get_storage().get_stats()
        feishu.reply_message(message_id,
                             f"📊 系统统计\n"
                             f"👤 候选人: {stats['candidates']} 人\n"
                             f"💼 活跃岗位: {stats['active_jobs']} 个\n"
                             f"🎯 匹配记录: {stats['matches']} 条\n"
                             f"💬 反馈: {stats['feedback']} 条")

    elif cmd == "/jobs":
        jobs = get_storage().list_jobs(limit=10)
        if not jobs:
            feishu.reply_message(message_id, "暂无活跃岗位")
            return
        lines = [f"• {j.get('title', '')} @ {j.get('company', '')} ({j.get('industry', '')})"
                 for j in jobs]
        feishu.reply_message(message_id, "💼 活跃岗位:\n" + "\n".join(lines))

    elif cmd == "/candidates":
        cands = get_storage().list_candidates(limit=10)
        if not cands:
            feishu.reply_message(message_id, "人才库暂无数据")
            return
        lines = [f"• {c.get('name', '')} - {c.get('current_role', '')} @ {c.get('current_company', '')}"
                 for c in cands]
        feishu.reply_message(message_id, "👤 最近入库:\n" + "\n".join(lines))

    elif cmd == "/feedback":
        _conversations[chat_id] = {"mode": "waiting_feedback", "history": [], "files": [],
                                   "context": {"entity_id": args}, "last_activity": time.time()}
        feishu.reply_message(message_id, "📝 请描述你的反馈，系统会据此持续优化")

    else:
        feishu.reply_message(message_id, f"未知命令: {cmd}\n输入 /help 查看帮助")


async def handle_ai_conversation(feishu, text: str, message_id: str,
                                 chat_id: str, user_id: str):
    feishu.reply_message(message_id, "🤔 思考中...")

    try:
        client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

        ctx = get_context(chat_id)
        history = ctx.get("history", [])

        messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}]
        for h in history[-6:]:
            messages.append(h)
        messages.append({"role": "user", "content": text})

        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
        )
        reply = resp.choices[0].message.content

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": reply})
        ctx["history"] = history[-20:]
        ctx["mode"] = ""

        feishu.reply_message(message_id, reply)

    except Exception as e:
        logger.error(f"AI conversation error: {e}")
        feishu.reply_message(message_id, f"❌ AI回复失败: {str(e)[:100]}")
