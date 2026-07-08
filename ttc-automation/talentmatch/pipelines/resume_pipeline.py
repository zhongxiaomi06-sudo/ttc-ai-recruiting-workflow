"""Resume processing pipeline: file → extract → parse → store → notify
v2: better batch progress, per-file card control, smarter error handling"""
from __future__ import annotations
import os
import json
import time
from typing import List, Optional
from loguru import logger

from resume_parser.parser import ResumeParser
from storage.db import Storage
from bot.feishu_client import FeishuClient


class ResumePipeline:
    """End-to-end resume processing pipeline"""

    def __init__(self, storage: Storage, feishu: Optional[FeishuClient] = None,
                 api_key: Optional[str] = None, model: str = "deepseek-chat"):
        self.storage = storage
        self.feishu = feishu
        self.parser = ResumeParser(api_key=api_key, model=model)

    def process_file(self, file_path: str, chat_id: str = "", message_id: str = "",
                     owner_id: str = "", send_card: bool = True) -> dict:
        """Process a single resume file"""
        logger.info(f"Processing: {file_path}")

        try:
            result = self.parser.parse_file(file_path)
            data = result.model_dump()
            data["owner_id"] = owner_id
            cid = self.storage.save_candidate(data)

            # Send card only if requested (batch mode sends summary instead)
            if self.feishu and chat_id and send_card:
                # Use progress card for batch, resume card for single
                card = FeishuClient.build_resume_card(data)
                self.feishu.send_card(chat_id, card)

            return {"status": "ok", "candidate_id": cid,
                    "name": result.candidate_name,
                    "current_role": result.current_role,
                    "current_company": result.current_company,
                    "ats_score": result.ats_score,
                    "candidate": data}

        except Exception as e:
            logger.error(f"Pipeline error for {file_path}: {e}")
            error_msg = str(e)[:200]
            # Friendly error hints
            if 'API key' in error_msg or '401' in error_msg:
                hint = 'LLM密钥问题，已启用规则提取'
            elif 'timeout' in error_msg.lower():
                hint = '解析超时，文件可能过大'
            elif 'No such' in error_msg or 'not found' in error_msg.lower():
                hint = '文件无法读取，请检查格式'
            else:
                hint = error_msg[:100]
            if self.feishu and chat_id:
                self.feishu.send_text(chat_id, f"⚠️ {os.path.basename(file_path)}: {hint}")
            return {"status": "error", "file": file_path, "error": error_msg}

    def process_batch(self, file_paths: List[str], chat_id: str = "",
                      message_id: str = "", owner_id: str = "") -> dict:
        """Process multiple resume files with per-file progress updates"""
        total = len(file_paths)
        results = {"ok": [], "error": [], "processed": 0}
        
        if total == 0:
            return results

        # Send initial progress
        if self.feishu and chat_id:
            card = FeishuClient.build_progress_card(
                task_id="batch", status="queued",
                progress=0.0, completed=0, total=total,
                message=f"开始批量解析 {total} 份简历..."
            )
            self.feishu.send_card(chat_id, card)

        for i, fp in enumerate(file_paths):
            logger.info(f"Batch [{i+1}/{total}]: {fp}")
            
            # Send per-file progress update (every file, not every 5)
            progress = (i + 1) / total
            if self.feishu and chat_id:
                self.feishu.send_text(chat_id, f"📄 [{i+1}/{total}] 解析中: {os.path.basename(fp)}...")

            # Process without per-file card (batch sends summary)
            result = self.process_file(fp, chat_id="", owner_id=owner_id, send_card=False)
            
            if result.get("status") == "ok":
                results["ok"].append(result)
            else:
                results["error"].append(result)
            
            results["processed"] = i + 1

        # Send summary
        if self.feishu and chat_id:
            ok_count = len(results["ok"])
            fail_count = len(results["error"])
            
            # Build list of parsed names
            names = []
            for r in results["ok"][:5]:
                name = r.get("name", "")
                role = r.get("current_role", "")
                ats = r.get("ats_score", 0)
                n = f"{name} ({role})" if name and role else name or "未知"
                ats_emoji = "🟢" if ats >= 70 else "🟡" if ats >= 50 else "🔴"
                names.append(f"  {ats_emoji} {n}")
            
            summary_lines = [
                f"📊 **批量解析完成**\n",
                f"├ ✅ 成功: {ok_count} 份"
            ]
            if fail_count > 0:
                summary_lines.append(f"└ ❌ 失败: {fail_count} 份")
            
            summary = "\n".join(summary_lines)
            self.feishu.send_text(chat_id, summary)
            
            # Show name list
            if names:
                name_list = "\n".join(names)
                extra = f"\n  ...还有 {ok_count - len(names)} 份" if ok_count > len(names) else ""
                self.feishu.send_text(chat_id, f"📋 **候选人名单:**\n{name_list}{extra}")
            
            # Send top 2 candidate cards
            for r in results["ok"][:2]:
                if r.get("candidate"):
                    card = FeishuClient.build_resume_card(r["candidate"])
                    self.feishu.send_card(chat_id, card)
            
            # Final tip
            if ok_count > 0:
                self.feishu.send_text(chat_id, "💡 点击上方卡片可操作：👍准确 / 👎偏差 / ⭐关注 / 📤推荐")

        return results
