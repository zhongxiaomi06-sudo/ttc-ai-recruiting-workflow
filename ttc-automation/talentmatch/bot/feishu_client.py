"""Feishu API client - handles auth, messaging, file download, cards"""
from __future__ import annotations
import json
import os
import time
import hashlib
import requests
from typing import Optional, List
from loguru import logger


class FeishuClient:
    """Unified Feishu API client"""

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None):
        self.app_id = app_id or os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET", "")
        self._token_cache = {"token": None, "expires_at": 0}
        self.upload_dir = os.environ.get("UPLOAD_DIR", "/opt/recruit-bot/data/uploads")
        os.makedirs(self.upload_dir, exist_ok=True)

    # ── Auth ──────────────────────────────────────

    def get_tenant_token(self) -> str:
        now = time.time()
        if self._token_cache["token"] and now < self._token_cache["expires_at"] - 60:
            return self._token_cache["token"]

        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            logger.error(f"Token error: {data}")
            return ""

        self._token_cache["token"] = data["tenant_access_token"]
        self._token_cache["expires_at"] = now + data.get("expire", 7200)
        return self._token_cache["token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.get_tenant_token()}", "Content-Type": "application/json"}

    # ── Messaging ──────────────────────────────────────

    def reply_message(self, message_id: str, text: str):
        url = f"{self.BASE_URL}/im/v1/messages/{message_id}/reply"
        body = {"content": json.dumps({"text": text}), "msg_type": "text"}
        try:
            resp = requests.post(url, headers=self._headers(), json=body, timeout=10)
            if resp.json().get("code") != 0:
                logger.warning(f"Reply failed: {resp.json()}")
        except Exception as e:
            logger.error(f"reply_message error: {e}")

    def send_message(self, chat_id: str, msg_type: str, content: dict):
        """Send message to a chat"""
        url = f"{self.BASE_URL}/im/v1/messages?receive_id_type=chat_id"
        body = {
            "receive_id": chat_id,
            "msg_type": msg_type,
            "content": json.dumps(content)
        }
        try:
            resp = requests.post(url, headers=self._headers(), json=body, timeout=10)
            if resp.json().get("code") != 0:
                logger.warning(f"Send message failed: {resp.json()}")
        except Exception as e:
            logger.error(f"send_message error: {e}")

    def send_card(self, chat_id: str, card: dict):
        """Send interactive card message"""
        self.send_message(chat_id, "interactive", card)

    def send_text(self, chat_id: str, text: str):
        """Send plain text message"""
        self.send_message(chat_id, "text", {"text": text})

    # ── File download ──────────────────────────────────────

    def download_file(self, message_id: str, file_key: str, filename: str = "") -> Optional[str]:
        """Download file from Feishu message"""
        token = self.get_tenant_token()
        if not token:
            return None

        url = f"{self.BASE_URL}/im/v1/messages/{message_id}/resources/{file_key}"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"type": "file"}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30, stream=True)
            if resp.status_code != 200:
                logger.error(f"Download failed: {resp.status_code}")
                return None

            # Determine filename
            if not filename:
                cd = resp.headers.get("Content-Disposition", "")
                if "filename=" in cd:
                    filename = cd.split("filename=")[-1].strip('"')
                else:
                    filename = f"file_{int(time.time())}"

            filepath = os.path.join(self.upload_dir, filename)
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Downloaded: {filepath} ({os.path.getsize(filepath)} bytes)")
            return filepath

        except Exception as e:
            logger.error(f"download_file error: {e}")
            return None

    def download_image(self, message_id: str, image_key: str) -> Optional[str]:
        """Download image from Feishu message"""
        token = self.get_tenant_token()
        if not token:
            return None

        url = f"{self.BASE_URL}/im/v1/messages/{message_id}/resources/{image_key}"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"type": "image"}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code != 200:
                return None

            filename = f"img_{image_key[:16]}_{int(time.time())}.png"
            filepath = os.path.join(self.upload_dir, filename)
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return filepath
        except Exception as e:
            logger.error(f"download_image error: {e}")
            return None

    # ── Card builders ──────────────────────────────────────

    @staticmethod
    def build_resume_card(candidate: dict, match_info: Optional[dict] = None) -> dict:
        """Build interactive card for parsed resume — v3 with classified skills, better layout"""
        name = candidate.get("name", candidate.get("candidate_name", "未知"))
        role = candidate.get("current_role", "")
        company = candidate.get("current_company", "")
        years = candidate.get("years_experience", 0)
        
        # Skills with classification
        skills = candidate.get("skills", [])
        if isinstance(skills, str):
            try: skills = json.loads(skills)
            except (json.JSONDecodeError, TypeError): skills = []
        skills_classified = candidate.get("skills_classified", {})
        if isinstance(skills_classified, str):
            try: skills_classified = json.loads(skills_classified)
            except (json.JSONDecodeError, TypeError): skills_classified = {}
        
        summary = candidate.get("summary", "")
        highlights = candidate.get("highlights", [])
        if isinstance(highlights, str):
            try: highlights = json.loads(highlights)
            except (json.JSONDecodeError, TypeError): highlights = []
        stability = candidate.get("career_stability", "")
        ats = candidate.get("ats_score", 0)
        edu = candidate.get("education", [])
        if isinstance(edu, str):
            try: edu = json.loads(edu)
            except (json.JSONDecodeError, TypeError): edu = []
        phone = candidate.get("phone", "")
        email = candidate.get("email", "")
        location = candidate.get("location", "")

        highlights_text = "\n".join(highlights[:4]) if highlights else ""
        stability_emoji = {"稳定": "🟢", "一般": "🟡", "频繁跳槽": "🔴"}.get(stability, "⚪")

        # ── Header info line ──
        header_parts = [f"**{role}**" if role else "", f"@{company}" if company else "", f"{years}年" if years else ""]
        header_info = " | ".join(p for p in header_parts if p)

        elements = []

        # Name + role/company
        if header_info:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**{name}**\n{header_info}"}})
        else:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**{name}**"}})

        # Badge row: stability + ATS + location
        badge_parts = []
        if stability:
            badge_parts.append(f"{stability_emoji} 稳定性:{stability}")
        if ats:
            emoji = "🟢" if ats >= 70 else "🟡" if ats >= 50 else "🔴"
            badge_parts.append(f"{emoji} ATS:{ats:.0f}")
        if location:
            badge_parts.append(f"📍{location}")
        if badge_parts:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": " | ".join(badge_parts)}})

        # Contact info (compact)
        contact_parts = []
        if phone:
            contact_parts.append(f"📞{phone}")
        if email:
            contact_parts.append(f"✉️{email}")
        if contact_parts:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": " | ".join(contact_parts)}})

        # Education
        if edu:
            edu_lines = []
            for e in edu[:2]:
                school = e.get('institution', '')
                degree = e.get('degree', '')
                major = e.get('field', e.get('major', ''))
                parts = [p for p in [school, degree, major] if p]
                if parts:
                    edu_lines.append(" | ".join(parts))
            if edu_lines:
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"🎓 {'\n'.join(edu_lines)}"}})

        # Skills with classification
        if skills:
            # 按分类展示
            classified_skills = skills_classified or {}
            category_order = ["ai_ml", "backend", "frontend", "cloud_devops", "data", "mobile", "product", "management"]
            category_labels = {
                "ai_ml": "🤖 AI/ML", "backend": "⚙️ 后端", "frontend": "🎨 前端",
                "cloud_devops": "☁️ 云/DevOps", "data": "📊 数据", "mobile": "📱 移动端",
                "product": "📋 产品", "management": "👥 管理",
            }
            
            has_classified = any(v for v in classified_skills.values())
            
            if has_classified:
                for cat_key in category_order:
                    cat_skills = classified_skills.get(cat_key, [])
                    if cat_skills:
                        label = category_labels.get(cat_key, cat_key)
                        skill_tags = "`" + "` `".join(cat_skills[:6]) + "`"
                        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"{label}: {skill_tags}"}})
                # 未分类的技能
                other = classified_skills.get("other", [])
                if other:
                    other_tags = "`" + "` `".join(other[:6]) + "`"
                    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"📌 其他: {other_tags}"}})
            else:
                # 无分类，直接展示
                if len(skills) <= 12:
                    skill_display = "`" + "` `".join(skills) + "`"
                else:
                    skill_display = "`" + "` `".join(skills[:10]) + f"` +{len(skills)-10}"
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**技能:** {skill_display}"}})

        # Work experience (新增强)
        work_exp = candidate.get("work_experience", [])
        if isinstance(work_exp, str):
            try: work_exp = json.loads(work_exp)
            except (json.JSONDecodeError, TypeError): work_exp = []
        if work_exp:
            exp_lines = []
            for exp in work_exp[:2]:
                company_name = exp.get('company', exp.get('name', ''))
                title = exp.get('position', exp.get('title', exp.get('role', '')))
                duration = exp.get('start_date', '') + " - " + exp.get('end_date', '至今') if exp.get('start_date') else exp.get('duration', '')
                desc = exp.get('description', '')
                level = exp.get('level', '')
                parts = [p for p in [company_name, title, duration] if p]
                header = " | ".join(parts)
                if level:
                    header += f" [{level}]"
                if desc:
                    header += f"\n  {desc[:80]}"
                exp_lines.append(header)
            if exp_lines:
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**工作经历:**\n{'\n'.join(exp_lines)}"}})

        # Projects (新增强)
        projects = candidate.get("projects", [])
        if isinstance(projects, str):
            try: projects = json.loads(projects)
            except (json.JSONDecodeError, TypeError): projects = []
        if projects:
            proj_lines = []
            for p in projects[:2]:
                pname = p.get('name', '')
                proj_role = p.get('role', '')
                proj_desc = p.get('description', '')
                tech = p.get('tech_stack', p.get('technologies', []))
                if isinstance(tech, str):
                    try: tech = json.loads(tech)
                    except (json.JSONDecodeError, TypeError): tech = []
                impact = p.get('impact', '')
                line = f"  • {pname}" if pname else ""
                if proj_role:
                    line += f" ({proj_role})"
                if tech:
                    line += f" [{', '.join(tech[:3])}]"
                if impact:
                    line += f" => {impact[:40]}"
                elif proj_desc:
                    line += f" {proj_desc[:40]}"
                if line:
                    proj_lines.append(line)
            if proj_lines:
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**项目经验:**\n{'\n'.join(proj_lines[:2])}"}})

        # Salary info (从salary_signal对象取)
        salary_signal = candidate.get("salary_signal", {})
        if isinstance(salary_signal, str):
            try: salary_signal = json.loads(salary_signal)
            except (json.JSONDecodeError, TypeError): salary_signal = {}
        salary_current = salary_signal.get("current") if isinstance(salary_signal, dict) else ""
        salary_expected = salary_signal.get("expected") if isinstance(salary_signal, dict) else ""
        if not salary_current and not salary_expected:
            salary_current = candidate.get("salary_current")
            salary_expected = candidate.get("salary_expected")
        if salary_current or salary_expected:
            salary_parts = []
            if salary_current:
                salary_parts.append(f"当前: {salary_current}")
            if salary_expected:
                salary_parts.append(f"期望: {salary_expected}")
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"💰 {' | '.join(salary_parts)}"}})

        # Highlights
        if highlights_text:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**重点亮点:**\n{highlights_text}"}})

        # Summary
        if summary:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"_{summary}_"}})

        # Match info
        if match_info:
            score = match_info.get("overall_score", 0)
            rec = match_info.get("recommendation", "")
            matched = match_info.get("matched_skills", [])
            gaps = match_info.get("missing_skills", [])
            if isinstance(matched, str):
                try: matched = json.loads(matched)
                except (json.JSONDecodeError, TypeError): matched = []
            if isinstance(gaps, str):
                try: gaps = json.loads(gaps)
                except (json.JSONDecodeError, TypeError): gaps = []
            rec_emoji = {"强推": "🔥", "推荐": "✅", "可考虑": "🤔", "不推荐": "❌"}.get(rec, "❓")

            score_bar = "🟩" * int(score * 10) + "⬜" * (10 - int(score * 10))
            match_text = f"**🎯 匹配度** | {rec_emoji} {rec}\n{score_bar} {score*100:.0f}%"

            elements.append({"tag": "hr"})
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": match_text}})
            if matched:
                matched_tags = "`" + "` `".join(matched[:5]) + "`"
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"✅ 匹配: {matched_tags}"}})
            if gaps:
                gap_tags = "`" + "` `".join(gaps[:4]) + "`"
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"⬜ 缺口: {gap_tags}"}})

        # ── 3 rows of actions ──
        elements.append({"tag": "hr"})
        cid = candidate.get("id", candidate.get("candidate_id", ""))
        elements.append({
            "tag": "action",
            "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "👍 准确"}, "type": "primary",
                 "value": {"action": "like", "candidate_id": cid}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "👎 有偏差"}, "type": "danger",
                 "value": {"action": "dislike", "candidate_id": cid}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "📋 原文"}, "type": "default",
                 "value": {"action": "raw", "candidate_id": cid}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "📊 评分"}, "type": "default",
                 "value": {"action": "ats_detail", "candidate_id": cid}},
            ]
        })
        elements.append({
            "tag": "action",
            "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "⭐ 重点关注"}, "type": "primary",
                 "value": {"action": "star", "candidate_id": cid}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "📤 已推荐客户"}, "type": "default",
                 "value": {"action": "send", "candidate_id": cid}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "💬 已沟通"}, "type": "default",
                 "value": {"action": "contact", "candidate_id": cid}},
            ]
        })
        elements.append({
            "tag": "action",
            "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "🎯 匹配岗位"}, "type": "primary",
                 "value": {"action": "quick_match", "candidate_id": cid, "candidate_name": name}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "📈 仪表盘"}, "type": "default",
                 "value": {"action": "dashboard", "candidate_id": ""}},
            ]
        })

        ats_val = int(ats) if ats else 50
        # 使用飞书稳定的header模板色: wathet(蓝绿) / yellow(黄) / carmine(红)
        template = "wathet" if ats_val >= 70 else "yellow" if ats_val >= 40 else "carmine"
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"📄 {name}" if name else "📄 简历解析"},
                "template": template
            },
            "elements": elements
        }

    @staticmethod
    def build_match_card(matches: list, job_title: str = "") -> dict:
        """Build card for match results — v3 with polished UX and more actions"""
        elements = []

        # Header summary
        top_scores = [m.get("overall_score", 0) for m in matches[:5]]
        avg_score = sum(top_scores) / len(top_scores) if top_scores else 0
        best_name = matches[0].get("candidate_name", "") if matches else ""

        # 更直观的进度条
        score_blocks = "🟩" * int(avg_score * 10) + "⬜" * (10 - int(avg_score * 10))
        
        summary_text = (
            f"🎯 找到 **{len(matches)}** 位匹配候选人\n"
            f"{score_blocks} 平均匹配度 {avg_score*100:.0f}%\n"
        )
        if best_name:
            summary_text += f"🏆 最佳匹配: **{best_name}**"
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": summary_text}})

        # 每个候选人更紧凑 — v4 加入薪资/年限/推荐标签
        for i, m in enumerate(matches[:5]):
            name = m.get("candidate_name", "")
            score = m.get("overall_score", 0)
            rec = m.get("recommendation", "")
            role = m.get("current_role", "")
            company = m.get("current_company", "")
            matched = m.get("matched_skills", [])
            if isinstance(matched, str):
                try: matched = json.loads(matched)
                except (json.JSONDecodeError, TypeError): matched = []
            gaps = m.get("missing_skills", [])
            if isinstance(gaps, str):
                try: gaps = json.loads(gaps)
                except (json.JSONDecodeError, TypeError): gaps = []
            years_exp = m.get("years_experience", 0) or 0
            salary_current = m.get("salary_current", "")
            salary_expected = m.get("salary_expected", "")

            progress = "🟩" * int(score * 10) + "⬜" * (10 - int(score * 10))
            subtitle = f"{role} @ {company}" if role and company else role or company or ""

            elements.append({"tag": "hr"})

            # 姓名 + 推荐标签 + 角色
            header_line = f"**{i+1}. {name}**"
            if score >= 0.8:
                header_line += " 🔥强推"
            elif score >= 0.6:
                header_line += " ✅推荐"
            elif score >= 0.4:
                header_line += " 🤔可考虑"
            else:
                header_line += " ❌待定"

            if subtitle:
                subtitle_short = subtitle if len(subtitle) <= 40 else subtitle[:37] + "..."
                header_line += f"\n{subtitle_short}"
            header_line += f"\n{progress} {score*100:.0f}%"

            # 薪资+年限辅助信息
            extra_parts = []
            if years_exp:
                extra_parts.append(f"{years_exp}年经验")
            if salary_current:
                extra_parts.append(f"💰现{salary_current}")
            if salary_expected:
                extra_parts.append(f"📈期{salary_expected}")
            if extra_parts:
                header_line += "\n" + " | ".join(extra_parts)

            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": header_line}})

            # 匹配/缺口技能
            if matched:
                matched_tags = "`" + "` `".join(matched[:4]) + "`"
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"✅ 匹配: {matched_tags}"}})
            if gaps:
                gap_tags = "`" + "` `".join(gaps[:3]) + "`"
                elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"⬜ 缺口: {gap_tags}"}})

            # 操作按钮 — 增强版
            cid = m.get("candidate_id", name)
            elements.append({
                "tag": "action",
                "actions": [
                    {"tag": "button", "text": {"tag": "plain_text", "content": "👍 推荐"}, "type": "primary",
                     "value": {"action": "like", "candidate_id": cid}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "📋 完整资料"}, "type": "default",
                     "value": {"action": "detail", "candidate_id": cid}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "💬 已沟通"}, "type": "default",
                     "value": {"action": "contact", "candidate_id": cid}},
                    {"tag": "button", "text": {"tag": "plain_text", "content": "📤 推客户"}, "type": "default",
                     "value": {"action": "send", "candidate_id": cid}},
                ]
            })

        if len(matches) > 5:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "_...还有 " + str(len(matches)-5) + " 位候选人。用 /search 查询"}})

        elements.append({"tag": "hr"})
        elements.append({
            "tag": "action",
            "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "📊 查看仪表盘"}, "type": "default",
                 "value": {"action": "dashboard", "candidate_id": ""}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "💡 使用教程"}, "type": "default",
                 "value": {"action": "help", "candidate_id": ""}},
            ]
        })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"🎯 匹配结果 — {job_title or '岗位'}"},
                "template": "indigo"
            },
            "elements": elements
        }

    @staticmethod
    def build_progress_card(task_id: str, status: str, progress: float,
                                completed: int, total: int, message: str = "") -> dict:
        """Build progress card for batch processing"""
        bar_len = 20
        filled = int(progress * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        status_emoji = {"pending": "⏳", "extracting": "📖", "analyzing": "🧠", "done": "✅", "failed": "❌"}.get(status, "🔄")

        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": f"{status_emoji} 批量解析进度"}},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"`{bar}` {progress*100:.0f}%"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"已完成: {completed}/{total} | {message}"}},
            ]
        }

    # ── Advanced Cards (v6) ──────────────────────────────────────

    @staticmethod
    def build_agent_result_card(result: dict) -> dict:
        """Build card for agent pipeline result"""
        data = result.get("data", {})
        job_info = data.get("job")
        title = job_info.get("title", "未知岗位") if job_info else "未知岗位"
        company = job_info.get("company", "") if job_info else ""

        screened = data.get("screened_count", 0)
        shortlisted = data.get("shortlisted_count", 0)
        top = data.get("top_matches", [])
        total_candidates = data.get("total_candidates", 0)

        elements = []

        # Summary line
        summary_parts = []
        if screened:
            summary_parts.append(f"筛简历: {screened}份")
        if shortlisted:
            summary_parts.append(f"达标: {shortlisted}人")
        if total_candidates:
            summary_parts.append(f"候选库: {total_candidates}人")
        if summary_parts:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": " | ".join(summary_parts)}
            })

        # Top matches
        if top:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "**🏆 Top 匹配候选人**"}
            })
            for i, m in enumerate(top[:5]):
                name = m.get("candidate_name", "未知")
                score = m.get("overall_score", 0)
                rec = m.get("recommendation", "")
                matched = m.get("matched_skills", [])
                if isinstance(matched, str):
                    try:
                        matched = json.loads(matched)
                    except Exception:
                        matched = []
                rec_emoji = {"强推": "🔥", "推荐": "✅", "可考虑": "🤔", "不推荐": "❌"}.get(rec, "❓")

                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**{i+1}. {name}** {rec_emoji} {score:.0f}分\n"
                            f"   匹配: {' '.join(matched[:4])}"
                        )
                    }
                })
        else:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "⚠️ 未找到匹配候选人"}
            })

        # Pipeline metadata
        elements.append({"tag": "hr"})
        meta = []
        cost = data.get("total_cost", 0)
        latency = data.get("latency_seconds", 0)
        if cost:
            meta.append(f"费用: ${cost:.4f}")
        if latency:
            meta.append(f"耗时: {latency:.1f}s")
        elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": " | ".join(meta)}]
        })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"🤖 Agent 管道结果 — {title}"},
                "template": "blue"
            },
            "elements": elements
        }

    @staticmethod
    def build_interview_card(plan: dict) -> dict:
        """Build card for interview plan"""
        candidate = plan.get("candidate_name", "候选人")
        job_title = plan.get("job_title", "岗位")
        questions = plan.get("questions", [])
        duration = plan.get("total_duration_minutes", 45)

        elements = [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**{candidate}** → {job_title} | {duration}分钟"}}
        ]

        if plan.get("focus_areas"):
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**考察方向**: {' '.join(plan['focus_areas'][:5])}"}
            })

        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**面试问题**"}})

        if questions:
            for i, q in enumerate(questions[:8]):
                cat = q.get("category", "通用")
                diff = q.get("difficulty", "medium")
                difficulty_map = {"junior": "🟢", "medium": "🟡", "senior": "🟠", "expert": "🔴"}
                diff_icon = difficulty_map.get(diff, "⚪")
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**Q{i+1}** {diff_icon}[{cat}] {q.get('question', '')}"}
                })
        else:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "暂无面试题"}})

        if plan.get("overall_recommendation"):
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"💡 {plan['overall_recommendation']}"}
            })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🎤 面试计划"},
                "template": "indigo"
            },
            "elements": elements
        }

    @staticmethod
    def build_outreach_card(draft: dict) -> dict:
        """Build card for outreach draft"""
        candidate = draft.get("candidate_name", "候选人")
        subject = draft.get("subject", "")
        body = draft.get("body", "")
        tone = draft.get("tone", "professional")
        channel = draft.get("channel", "")
        timing = draft.get("timing_suggestion", "")

        tone_emoji = {"professional": "🤝", "亲切": "😊", "直接": "⚡"}
        tone_icon = tone_emoji.get(tone, "📨")

        elements = [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"{tone_icon} **{candidate}** 外联草稿"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**{subject}**"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": body[:500]}},
        ]

        if channel or timing:
            elements.append({"tag": "hr"})
            parts = []
            if channel:
                parts.append(f"渠道建议: {channel}")
            if timing:
                parts.append(f"时间建议: {timing}")
            elements.append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": " | ".join(parts)}]
            })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"📨 外联草稿 — {candidate}"},
                "template": "green"
            },
            "elements": elements
    }

    @staticmethod
    def build_bias_audit_card(audit: dict) -> dict:
        """Build card for bias audit result"""
        is_biased = audit.get("is_biased", False)
        signals = audit.get("flagged_signals", [])
        reasoning = audit.get("reasoning", "")
        mitigation = audit.get("mitigation_suggestion", "")

        color = "red" if is_biased else "green"
        status_text = "⚠️ 发现潜在偏见" if is_biased else "✅ 未发现偏见"

        elements = [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"### {status_text}"}}
        ]

        if signals:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**标记信号**: {' '.join(signals[:5])}"}
            })

        if reasoning:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**分析**: {reasoning}"}
            })

        if mitigation:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"💡 {mitigation}"}
            })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "⚖️ 偏见审计报告"},
                "template": color
            },
            "elements": elements
        }

    @staticmethod
    def build_job_card(job: dict) -> dict:
        """Build card for job/position detail"""
        title = job.get("title", "未知岗位")
        company = job.get("company", "")
        skills = job.get("required_skills", [])
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except Exception:
                skills = []
        prefs = job.get("preferred_skills", [])
        if isinstance(prefs, str):
            try:
                prefs = json.loads(prefs)
            except Exception:
                prefs = []
        salary = job.get("salary_range", "")
        edu = job.get("education", "")
        exp = f"{job.get('min_years_experience', 0)}+年" if job.get('min_years_experience') else "不限"
        hidden = job.get("hidden_requirements", [])
        if isinstance(hidden, str):
            try:
                hidden = json.loads(hidden)
            except Exception:
                hidden = []
        selling = job.get("key_selling_points", [])
        if isinstance(selling, str):
            try:
                selling = json.loads(selling)
            except Exception:
                selling = []
        urgency = job.get("urgency", "")
        location = job.get("location", "")

        elements = [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**{title}** @ {company}"}},
        ]

        info_parts = []
        if location:
            info_parts.append(f"📍 {location}")
        if salary:
            info_parts.append(f"💰 {salary}")
        if exp:
            info_parts.append(f"📅 {exp}")
        if edu:
            info_parts.append(f"🎓 {edu}")
        if urgency:
            urgency_emoji = {"紧急": "🔴", "一般": "🟡", "不急": "🟢"}
            info_parts.append(f"{urgency_emoji.get(urgency, '⚪')} {urgency}")

        if info_parts:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": " | ".join(info_parts)}})

        if skills:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**必要技能**: {' '.join(skills[:8])}"}})
        if prefs:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**加分项**: {' '.join(prefs[:5])}"}})

        if selling:
            elements.append({"tag": "hr"})
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**🎯 卖点**: {' '.join(selling[:3])}"}})

        if hidden:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**潜规则**: {' '.join(hidden[:3])}"}})

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"📋 岗位详情 — {title}"},
                "template": "blue"
            },
            "elements": elements
        }

    @staticmethod
    def build_candidate_card(candidate: dict) -> dict:
        """卡片 V2 — 带交互按钮的候选人详情卡
        
        按钮说明:
          📄 查看原文 — 查看候选人原始简历文本
          ⭐ 关注 — 标记为重点候选人 (追踪隐式反馈)
          📤 已推荐 — 标记为已推荐给客户
          🎯 快速匹配 — 匹配当前岗位
          👍 准确 / 👎 有偏差 — 反馈信号
        """
        import json as _json
        
        name = candidate.get("name", candidate.get("candidate_name", "未知"))
        role = candidate.get("current_role", "")
        company = candidate.get("current_company", "")
        years = candidate.get("years_experience", 0) or 0
        cid = candidate.get("id", "")
        
        skills = candidate.get("skills", [])
        if isinstance(skills, str):
            try: skills = _json.loads(skills)
            except (json.JSONDecodeError, TypeError): skills = []
        
        highlights = candidate.get("highlights", [])
        if isinstance(highlights, str):
            try: highlights = _json.loads(highlights)
            except (json.JSONDecodeError, TypeError): highlights = []
        
        stability = candidate.get("career_stability", "")
        ats = candidate.get("ats_score", 0) or 0
        stability_emoji = {"稳定": "🟢", "一般": "🟡", "频繁跳槽": "🔴"}.get(stability, "⚪")
        
        edu = candidate.get("education", [])
        if isinstance(edu, str):
            try: edu = _json.loads(edu)
            except (json.JSONDecodeError, TypeError): edu = []
        
        summary = candidate.get("summary", "")
        
        # ── ATS 评分详情条 ──
        ats_bar = ""
        if ats > 0:
            blocks = 10
            filled = max(1, round(ats / 100 * blocks))
            empty = blocks - filled
            ats_bar = f"{'█' * filled}{'░' * empty}"
        
        # ── 薪资信息 ──
        salary_current = candidate.get("salary_current", "")
        salary_expected = candidate.get("salary_expected", "")
        salary_info = ""
        if salary_current or salary_expected:
            parts = []
            if salary_current:
                parts.append(f"当前: {salary_current}")
            if salary_expected:
                parts.append(f"期望: {salary_expected}")
            salary_info = f"💰 {' | '.join(parts)}"
        
        # ── 构建卡片头部 ──
        header_text = f"{name}"
        if role:
            header_text += f" · {role[:20]}"
        
        # ── 主体内容 ──
        elements = []
        
        # 基本信息行
        info_parts = [f"**{name}**"]
        if role and company:
            info_parts.append(f"{role} @ {company}")
        elif role:
            info_parts.append(role)
        info_parts.append(f"{years}年")
        
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": " | ".join(info_parts)}
        })
        
        # ATS 评分条
        if ats > 0:
            ats_label = "🟢 高匹配" if ats >= 75 else "🟡 中等" if ats >= 50 else "🔴 待定"
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"ATS **{ats:.0f}/100** {ats_bar} {ats_label}"}
            })
        
        # 稳定性 + 其他标签
        tags = []
        if stability:
            tags.append(f"{stability_emoji} {stability}")
        level = candidate.get("role_level", "")
        if level:
            tags.append(f"📊 {level}")
        if tags:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": " | ".join(tags)}
            })
        
        # 技能标签（带高亮）
        if skills:
            skill_text = " ".join(skills[:12])
            if len(skills) > 12:
                skill_text += f" +{len(skills)-12}"
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"🔧 **技能**: {skill_text}"}
            })
        
        # 教育
        if edu:
            school_parts = []
            for e in edu[:2]:
                deg = e.get('degree', '')
                inst = e.get('institution', '')
                badge = ""
                if e.get('is_qs50'):
                    badge = "🌍QS50"
                elif e.get('is_985'):
                    badge = "🏫985"
                elif e.get('is_211'):
                    badge = "🏫211"
                school_parts.append(f"{deg}@{inst}{badge}" if badge else f"{deg}@{inst}")
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"🎓 **教育**: {' '.join(school_parts)}"}
            })
        
        # 亮点
        if highlights:
            hl_text = " · ".join(highlights[:3])
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"⭐ **亮点**: {hl_text}"}
            })
        
        # 薪资
        if salary_info:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": salary_info}
            })
        
        # 摘要
        if summary:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"_{summary}_"}
            })
        
        # ── 交互按钮行 1: 操作类 ──
        buttons_row1 = {
            "tag": "action",
            "actions": []
        }
        
        if cid:
            buttons_row1["actions"].append({
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📄 原文"},
                "type": "default",
                "value": {"action": "view_raw", "candidate_id": cid}
            })
            buttons_row1["actions"].append({
                "tag": "button",
                "text": {"tag": "plain_text", "content": "⭐ 关注"},
                "type": "default",
                "value": {"action": "star", "candidate_id": cid}
            })
            buttons_row1["actions"].append({
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📤 推荐"},
                "type": "default",
                "value": {"action": "mark_sent", "candidate_id": cid}
            })
            buttons_row1["actions"].append({
                "tag": "button",
                "text": {"tag": "plain_text", "content": "🎯 匹配"},
                "type": "primary",
                "value": {"action": "quick_match", "candidate_id": cid}
            })
        
        if buttons_row1["actions"]:
            elements.append(buttons_row1)
        
        # ── 交互按钮行 2: 反馈类 ──
        if cid:
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "👍 准确"},
                        "type": "primary",
                        "value": {"action": "like", "candidate_id": cid}
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "👎 偏差"},
                        "type": "default",
                        "value": {"action": "dislike", "candidate_id": cid, "need_feedback": True}
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "💬 反馈"},
                        "type": "default",
                        "value": {"action": "feedback", "candidate_id": cid}
                    }
                ]
            })
        
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"👤 {header_text[:40]}"},
                "template": "indigo"
            },
            "elements": elements
        }
    def build_dashboard_card(stats: dict) -> dict:
        """仪表盘卡片 V4 — 带进度条和更清晰的分段"""
        def bar(value, max_v=50, total_blocks=8, filled="🟩", empty="⬜"):
            if max_v <= 0: return ""
            blocks = min(int(value / max_v * total_blocks), total_blocks)
            return filled * blocks + empty * (total_blocks - blocks)
        
        candidates = stats.get('candidates', 0)
        jobs = stats.get('active_jobs', 0)
        matches = stats.get('matches', 0)
        feedback = stats.get('feedback', 0)
        views = stats.get('views', 0)
        likes = stats.get('likes', 0)
        dislikes = stats.get('dislikes', 0)
        stars = stats.get('stars', 0)
        sends = stats.get('sends', 0)
        clicks = stats.get('clicks', 0)
        avg_dwell = stats.get('avg_dwell', 0)
        
        lines = ["**📊 系统概览**", ""]
        
        # 数据量
        lines.append(f"👤 **候选人**: {candidates} 人 {bar(candidates, 50)}")
        lines.append(f"💼 **活跃岗位**: {jobs} 个 {bar(jobs, 10)}")
        lines.append(f"🎯 **匹配**: {matches} 条")
        lines.append(f"💬 **反馈**: {feedback} 条")
        
        # 参与度
        total_fb = likes + dislikes
        accuracy = f"{likes/total_fb*100:.0f}%" if total_fb > 0 else "暂无"
        dwell_str = ""
        if avg_dwell:
            dm = int(avg_dwell // 60)
            ds = int(avg_dwell % 60)
            dwell_str = f"{dm}分{ds}秒" if dm else f"{ds}秒"
        
        lines.extend([
            "",
            "**📈 用户参与**",
            f"👀 浏览: {views} 次 | 🖱️ 点击: {clicks} 次",
            f"👍 准确率: {accuracy} ({likes}/{dislikes})",
            f"⭐ 关注: {stars} | 📤 推荐: {sends}",
        ])
        if dwell_str:
            lines.append(f"⏱ 平均阅读: {dwell_str}")
        lines.append("")
        
        # 操作提示
        if candidates == 0:
            lines.append("💡 **开始使用**: 发一份 PDF 简历试试！")
        elif jobs == 0:
            lines.append("💡 **创建匹配**: 发 /match 输入岗位需求")
        elif matches == 0:
            lines.append("💡 **触发匹配**: 上传简历后自动匹配岗位")
        
        elements = [{"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}}]
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📊 猎头系统仪表盘"},
                "template": "turquoise"
            },
            "elements": elements
        }
    @staticmethod
    def build_error_card(message: str, details: str = "") -> dict:
        """Build error card for failed operations"""
        elements = [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"❌ {message}"}}
        ]
        if details:
            elements.append({
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": details[:200]}]
            })
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "⚠️ 操作失败"},
                "template": "red"
            },
            "elements": elements
        }
