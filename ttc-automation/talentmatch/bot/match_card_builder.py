"""
飞书匹配结果卡片构建器 v2 — 含雷达图可视化+详细评分解释
"""
from __future__ import annotations
import json, math
from typing import List, Optional, Dict
from loguru import logger


def build_hybrid_match_card(match: dict, detailed: bool = True) -> dict:
    """
    构建混合评分结果卡片（飞书消息卡片）
    
    相比v1的改进:
    - 雷达图可视化（用ASCII或emoji进度条展示5维评分）
    - 规则vsML评分对比
    - 自然语言解释
    - 可点击按钮查看更多
    """
    score = match.get("overall_score", 0) or 0
    name = match.get("candidate_name", "候选人")
    title = match.get("job_title", "岗位")
    rec = match.get("recommendation", "可考虑")
    explanation = match.get("explanation", "")
    
    # 推荐级别emoji
    rec_emojis = {"强推": "🔥", "推荐": "✅", "可考虑": "🤔", "不推荐": "❌"}
    rec_emoji = rec_emojis.get(rec, "❓")
    
    # 5维评分条
    dimensions = [
        ("技能匹配", match.get("skill_score", 0) or 0),
        ("经验匹配", match.get("experience_score", 0) or 0),
        ("教育背景", match.get("education_score", 0) or 0),
        ("项目经验", match.get("project_score", 0) or 0),
        ("信号评分", match.get("signal_score", 0) or 0),
    ]
    
    score_bars = ""
    for dim_name, dim_score in dimensions:
        filled = "🟩" * max(1, int(dim_score * 10))
        empty = "⬜" * (10 - max(1, int(dim_score * 10)))
        score_bars += f"{dim_name}  {filled}{empty} {dim_score*100:.0f}%\n"
    
    # 总体评分条
    overall_bar = "🟩" * max(1, int(score * 10)) + "⬜" * (10 - max(1, int(score * 10)))
    
    # 构建卡片
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{rec_emoji} 匹配结果: {name} → {title}"},
            "template": "blue" if score >= 0.7 else ("orange" if score >= 0.5 else "red"),
        },
        "elements": [
            # 总体评分
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**🎯 综合匹配度**\n{overall_bar} **{score*100:.0f}%** — {rec_emoji} {rec}"}
            },
            {"tag": "hr"},
            # 5维雷达图（进度条形式）
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**📊 多维评分**\n{score_bars}"}
            },
        ]
    }
    
    # 自然语言解释
    if explanation:
        card["elements"].append({"tag": "hr"})
        card["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**💡 评分解读**\n{explanation}"}
        })
    
    # 技能详情
    matched = match.get("matched_skills", [])
    missing = match.get("missing_skills", [])
    if matched or missing:
        card["elements"].append({"tag": "hr"})
        detail = ""
        if matched:
            detail += f"✅ 匹配技能: {' '.join(matched[:8])}\n"
        if missing:
            detail += f"❌ 缺失技能: {' '.join(missing[:8])}"
        card["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**🔧 技能分析**\n{detail}"}
        })
    
    # 操作按钮
    card["elements"].append({
        "tag": "action",
        "actions": [
            {"tag": "button", "text": {"tag": "plain_text", "content": "📋 查看简历"}, "type": "default",
             "value": {"action": "view_resume", "candidate_id": match.get("candidate_id", "")}},
            {"tag": "button", "text": {"tag": "plain_text", "content": "💬 联系候选人"}, "type": "primary",
             "value": {"action": "contact_candidate", "candidate_id": match.get("candidate_id", "")}},
            {"tag": "button", "text": {"tag": "plain_text", "content": "👍 准确"}, "type": "default",
             "value": {"action": "feedback_match", "match_id": match.get("id", ""), "feedback": "like"}},
            {"tag": "button", "text": {"tag": "plain_text", "content": "👎 偏差"}, "type": "default",
             "value": {"action": "feedback_match", "match_id": match.get("id", ""), "feedback": "dislike"}},
        ]
    })
    
    return card


def build_match_compare_card(results: List[dict], candidate_name: str) -> dict:
    """
    构建岗位对比卡片 — 同一候选人对多个岗位的评分对比
    """
    if not results:
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "暂无对比数据"}, "template": "grey"},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": "该候选人暂无岗位匹配记录"}}]
        }
    
    # 按评分排序
    sorted_results = sorted(results, key=lambda x: x.get("overall_score", 0) or 0, reverse=True)
    
    # 构建对比表格
    rows = ""
    for i, r in enumerate(sorted_results[:8]):
        s = r.get("overall_score", 0) or 0
        job_title = r.get("job_title", "?")
        rec = r.get("recommendation", "可考虑")
        rows += f"{i+1}. **{job_title}** — {s*100:.0f}% ({rec})\n"
    
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📊 {candidate_name} — 岗位匹配对比"},
            "template": "blue",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"共 {len(sorted_results)} 个岗位匹配结果\n\n{rows}"}}
        ]
    }
    
    # 最佳匹配
    best = sorted_results[0]
    if best.get("explanation"):
        card["elements"].append({"tag": "hr"})
        card["elements"].append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**🏆 最佳匹配建议**\n{best['explanation']}"}
        })
    
    return card


def build_explanation_card(candidate_name: str, job_title: str, explanation: str) -> dict:
    """构建纯解释卡片 — 用于/why命令"""
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"💡 评分解读: {candidate_name}"},
            "template": "blue",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**岗位**: {job_title}\n\n{explanation}"}}
        ]
    }
