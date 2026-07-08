"""Match pipeline: JD → search → score → notify
v2: better dedup, skill-first search, top-k scoring, result caching"""
from __future__ import annotations
import json
import time
from typing import List, Optional, Set
from loguru import logger

from job_parser.parser import JobParser
from matching.unified_engine import UnifiedMatchEngine, candidate_from_storage, job_from_storage
from storage.db import Storage
from bot.feishu_client import FeishuClient


class MatchPipeline:
    """End-to-end job-candidate matching pipeline"""

    def __init__(self, storage: Storage, feishu: Optional[FeishuClient] = None,
                 api_key: Optional[str] = None, model: str = "deepseek-chat"):
        self.storage = storage
        self.feishu = feishu
        self.job_parser = JobParser(api_key=api_key, model=model)
        self.match_engine = UnifiedMatchEngine()

    def match_jd(self, jd_text: str, chat_id: str = "", source: str = "feishu",
                 use_llm: bool = False, top_k: int = 10) -> dict:
        """Parse JD → find matching candidates → score → notify"""
        logger.info(f"Matching JD from {source}")

        try:
            # Step 1: Parse JD
            job = self.job_parser.parse(jd_text, source=source)
            job_data = job.model_dump()
            jid = self.storage.save_job(job_data)

            # Step 2: Multi-strategy candidate search with dedup
            seen_ids: Set[str] = set()
            candidates = []

            # Strategy A: Vector search on full JD text
            vec_results = []
            if hasattr(self.storage, 'search_candidates_vector'):
                vec_results = self.storage.search_candidates_vector(jd_text, limit=top_k * 2)
            for c in vec_results:
                cid = c.get("id", "")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    candidates.append(c)

            # Strategy B: Text search on required skills
            required = job.required_skills[:5]
            for skill in required:
                if not skill.strip():
                    continue
                search_fn = getattr(self.storage, 'search_candidates_text', self.storage.search_candidates)
                skill_results = search_fn(skill, limit=3) if search_fn.__name__ == 'search_candidates_text' else search_fn(skill, limit=3)
                for c in skill_results:
                    cid = c.get("id", "")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        candidates.append(c)

            # Strategy C: If too few candidates, broaden search
            if len(candidates) < 5 and job.preferred_skills:
                search_fn = getattr(self.storage, 'search_candidates_text', self.storage.search_candidates)
                for skill in job.preferred_skills[:3]:
                    if not skill.strip():
                        continue
                    broad_results = search_fn(skill, limit=3) if search_fn.__name__ == 'search_candidates_text' else search_fn(skill, limit=3)
                    for c in broad_results:
                        cid = c.get("id", "")
                        if cid and cid not in seen_ids:
                            seen_ids.add(cid)
                            candidates.append(c)

            if not candidates:
                if self.feishu and chat_id:
                    self.feishu.send_text(chat_id,
                        f"📋 **岗位已入库**: {job.title}\n"
                        f"🏢 {job.company or ''}\n"
                        f"⚠️ 人才库中暂无匹配候选人\n"
                        f"💡 上传几份简历试试匹配效果！")
                return {"job_id": jid, "matches": [], "total_candidates": 0, "job_title": job.title}

            # Step 3: Score each candidate
            matches = []
            for c in candidates:
                c_data = self.storage.get_candidate(c["id"])
                if not c_data:
                    continue

                cv = candidate_from_storage(c_data)
                jv = job_from_storage(job_data)
                result = self.match_engine.compute_match(cv, jv)

                match_data = {
                    "candidate_id": c["id"],
                    "job_id": jid,
                    "overall_score": result.overall_score,
                    "candidate_name": result.candidate_name,
                    "job_title": result.job_title,
                    "current_role": c_data.get("current_role", ""),
                    "current_company": c_data.get("current_company", ""),
                    "matched_skills": result.matched_skills,
                    "missing_skills": result.missing_skills,
                    "recommendation": result.recommendation,
                    "explanation": result.explanation,
                    "dimensions": [
                        {"name": d.name, "score": d.score, "weight": d.weight, "evidence": d.evidence}
                        for d in result.dimensions
                    ],
                }

                self.storage.save_match(match_data)
                matches.append(match_data)

            # Sort by overall_score descending
            matches.sort(key=lambda x: x.get("overall_score", 0) or 0, reverse=True)
            matches = matches[:top_k]

            # Step 4: Notify with rich card
            if self.feishu and chat_id:
                card = FeishuClient.build_match_card(matches, job.title)
                self.feishu.send_card(chat_id, card)
                
                # Text summary too
                top_3 = matches[:3]
                lines = [f"🎯 **{len(matches)}** 位候选人匹配 **{job.title}**"]
                for m in top_3:
                    name = m.get("candidate_name", "未知")
                    score = m.get("overall_score", 0) or 0
                    rec = m.get("recommendation", "")
                    pct = score * 100 if score <= 1 else score
                    lines.append(f"  {name} — {pct:.0f}% {rec}")
                if len(matches) > 3:
                    lines.append(f"  ...还有 {len(matches)-3} 位")
                self.feishu.send_text(chat_id, "\n".join(lines))

            return {
                "job_id": jid,
                "matches": matches,
                "total_candidates": len(candidates),
                "job_title": job.title
            }

        except Exception as e:
            logger.error(f"Match pipeline error: {e}")
            if self.feishu and chat_id:
                self.feishu.send_text(chat_id, f"❌ 匹配失败: {str(e)[:200]}")
            return {"error": str(e)}
