"""RecruitingPipeline — orchestrates JD parsing, screening, scoring, outreach, and interview"""
from __future__ import annotations
import json
import time
import uuid
from typing import Optional, Callable
from loguru import logger

from .base import BaseAgent, AgentCache
from .jd_agent import JDParserAgent, AgentJobRequirements
from .resume_agent import ResumeScreenerAgent, AgentCandidateProfile
from .match_agent import MatchScorerAgent, AgentMatchScore
from .outreach_agent import OutreachDrafterAgent, OutreachDraft
from .interview_agent import InterviewGeneratorAgent, InterviewPlan
from .bias_agent import BiasMitigatorAgent, BiasAuditResult


class PipelineResult:
    """Result of a full pipeline run with all artifacts"""
    def __init__(self):
        self.pipeline_id: str = str(uuid.uuid4())
        self.status: str = "running"  # running/completed/failed
        self.error: str = ""

        # Phase results
        self.job: Optional[AgentJobRequirements] = None
        self.screened_candidates: list[AgentCandidateProfile] = []
        self.matched_scores: list[AgentMatchScore] = []
        self.outreach_drafts: list[OutreachDraft] = []
        self.interview_plans: list[InterviewPlan] = []
        self.bias_audits: list[BiasAuditResult] = []

        # Metadata
        self.total_candidates: int = 0
        self.shortlisted_count: int = 0
        self.total_cost: float = 0.0
        self.latency_seconds: float = 0.0
        self.created_at: float = time.time()

    def to_dict(self) -> dict:
        return {
            "pipeline_id": self.pipeline_id,
            "status": self.status,
            "error": self.error,
            "job": self.job.model_dump() if self.job else None,
            "screened_count": len(self.screened_candidates),
            "total_candidates": self.total_candidates,
            "shortlisted_count": self.shortlisted_count,
            "top_matches": [s.model_dump() for s in self.matched_scores[:5]],
            "outreach_count": len(self.outreach_drafts),
            "interview_plan_count": len(self.interview_plans),
            "bias_audit_count": len(self.bias_audits),
            "total_cost": round(self.total_cost, 4),
            "latency_seconds": round(self.latency_seconds, 1),
        }


class RecruitingPipeline:
    """Production-grade multi-agent recruiting pipeline with parallel processing.

    Orchestrates the full workflow:
    1. Parse JD → 2. Screen resumes → 3. Score matches → 4. Audit bias → 5. Draft outreach → 6. Generate interview plans
    """

    def __init__(
        self,
        model: str = "",
        min_score: float = 70.0,
        top_k: int = 10,
        outreach_tone: str = "professional",
        sender_name: str = "",
        company_name: str = "",
        use_llm_match: bool = True,
        use_cache: bool = True,
    ):
        self.model = model
        self.min_score = min_score
        self.top_k = top_k
        self.outreach_tone = outreach_tone
        self.sender_name = sender_name
        self.company_name = company_name
        self.use_llm_match = use_llm_match
        self.use_cache = use_cache

        # Initialize all agents
        self.jd_parser = JDParserAgent(model=model, use_cache=use_cache)
        self.screener = ResumeScreenerAgent(model=model, use_cache=use_cache)
        self.matcher = MatchScorerAgent(model=model, use_llm_analysis=use_llm_match, use_cache=use_cache)
        self.drafter = OutreachDrafterAgent(model=model, use_cache=use_cache)
        self.interview_gen = InterviewGeneratorAgent(model=model, use_cache=use_cache)
        self.bias_mitigator = BiasMitigatorAgent(model=model, use_cache=use_cache)

    def run(
        self,
        jd_text: str,
        resume_texts: Optional[list[tuple[str, str]]] = None,
        resume_dir: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> PipelineResult:
        """Run the full pipeline end-to-end.

        Args:
            jd_text: Unstructured job description text
            resume_texts: List of (filename, text) tuples
            resume_dir: Directory to scan for resume files (alternative to resume_texts)
            progress_callback: Optional callback(phase, progress, message)

        Returns:
            PipelineResult with all artifacts
        """
        result = PipelineResult()
        start = time.monotonic()

        def _progress(phase: str, pct: float, msg: str = ""):
            if progress_callback:
                progress_callback(phase, pct, msg)
            logger.info(f"[Pipeline {result.pipeline_id[:8]}] {phase}: {msg}")

        try:
            # ── Phase 1: Parse JD ──────────────────────────────────────
            _progress("parse_jd", 0.1, "解析岗位需求...")
            job, cost = self.jd_parser.parse(jd_text)
            result.job = job
            result.total_cost += cost

            if not job.title:
                result.status = "failed"
                result.error = "JD解析失败：未能提取职位信息"
                _progress("error", 1.0, result.error)
                return result

            _progress("parse_jd", 0.2, f"JD解析完成: {job.title} @ {job.company}")

            # ── Phase 2: Screen resumes ─────────────────────────────────
            raw_resumes: list[tuple[str, str]] = []

            if resume_texts:
                raw_resumes = resume_texts
            elif resume_dir:
                resume_texts = self._load_resumes_from_dir(resume_dir)
                raw_resumes = resume_texts or []

            if not raw_resumes:
                logger.warning("⚠️ No resumes to process")
                result.status = "completed"
                _progress("done", 1.0, "没有简历需要处理")
                return result

            result.total_candidates = len(raw_resumes)
            _progress("screen", 0.3, f"筛选 {len(raw_resumes)} 份简历...")

            screened: list[AgentCandidateProfile] = []
            for i, (filename, text) in enumerate(raw_resumes):
                profile, cost = self.screener.screen(text, filename)
                screened.append(profile)
                result.total_cost += cost

                if (i + 1) % 5 == 0:
                    _progress("screen", 0.3 + 0.2 * (i + 1) / len(raw_resumes),
                              f"已解析 {i+1}/{len(raw_resumes)} 份简历")

            result.screened_candidates = screened
            _progress("screen", 0.5, f"完成 {len(screened)} 份简历筛选")

            # ── Phase 3: Score matches ──────────────────────────────────
            _progress("match", 0.5, "计算匹配度...")
            scored: list[AgentMatchScore] = []
            for i, profile in enumerate(screened):
                score, cost = self.matcher.score(profile, job)
                scored.append(score)
                result.total_cost += cost

            # Filter and sort
            scored.sort(key=lambda s: s.overall_score, reverse=True)
            shortlisted = [s for s in scored if s.overall_score >= self.min_score]
            result.matched_scores = scored[:self.top_k]
            result.shortlisted_count = len(shortlisted)
            _progress("match", 0.65,
                      f"匹配完成: {len(shortlisted)} 人达标 (>{self.min_score}分)")

            # ── Phase 4: Bias audit on top candidates ───────────────────
            if shortlisted:
                _progress("bias", 0.65, f"审计 {min(10, len(shortlisted))} 位top候选人的偏见...")
                audit_pairs = []
                for score in shortlisted[:10]:
                    # Find the profile for this score
                    for prof in screened:
                        if prof.candidate_name == score.candidate_name:
                            audit_pairs.append((prof, score))
                            break

                for prof, sc in audit_pairs:
                    audit, cost = self.bias_mitigator.audit_match(prof, sc)
                    result.bias_audits.append(audit)
                    result.total_cost += cost
                    if audit.is_biased:
                        logger.warning(f"⚠️ Bias detected for {sc.candidate_name}: {audit.reasoning}")

                _progress("bias", 0.75, "偏见审计完成")

            # ── Phase 5: Draft outreach ─────────────────────────────────
            if shortlisted:
                _progress("outreach", 0.75, f"为 {min(5, len(shortlisted))} 位候选人撰写外联...")
                for i, score in enumerate(shortlisted[:5]):
                    draft, cost = self.drafter.draft(
                        score, job,
                        tone=self.outreach_tone,
                        sender_name=self.sender_name,
                        company_name=self.company_name,
                    )
                    result.outreach_drafts.append(draft)
                    result.total_cost += cost

                _progress("outreach", 0.85, "外联草稿完成")

            # ── Phase 6: Interview plans for top candidates ─────────────
            if shortlisted:
                _progress("interview", 0.85, f"为 {min(3, len(shortlisted))} 位top候选人设计面试...")
                for i, score in enumerate(shortlisted[:3]):
                    # Find profile
                    prof = None
                    for p in screened:
                        if p.candidate_name == score.candidate_name:
                            prof = p
                            break
                    if not prof:
                        continue

                    plan, cost = self.interview_gen.generate_plan(prof, job, score)
                    result.interview_plans.append(plan)
                    result.total_cost += cost

                _progress("interview", 0.95, "面试计划完成")

            # ── Complete ───────────────────────────────────────────────
            result.status = "completed"
            result.latency_seconds = time.monotonic() - start
            _progress("done", 1.0,
                      f"管道完成: {result.shortlisted_count}人达标, 耗时{result.latency_seconds:.1f}秒, "
                      f"费用${result.total_cost:.4f}")

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            result.status = "failed"
            result.error = str(e)
            result.latency_seconds = time.monotonic() - start
            _progress("error", 1.0, f"管道失败: {str(e)[:200]}")
            import traceback
            logger.error(traceback.format_exc())

        return result

    def run_async(self, jd_text: str, **kwargs) -> str:
        """Run pipeline in background task. Returns pipeline_id for status polling."""
        import threading
        pipeline_id = str(uuid.uuid4())

        # We use threading for simplicity (avoids Celery/RQ dependency)
        def _run():
            result = self.run(jd_text, **kwargs)
            logger.info(f"Async pipeline {pipeline_id} completed: {result.status}")

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return pipeline_id

    def _load_resumes_from_dir(self, directory: str) -> list[tuple[str, str]]:
        """Load resume text from a directory of files"""
        import os
        from resume_parser.parser import extract_text

        results: list[tuple[str, str]] = []
        valid_exts = {".txt", ".md", ".pdf", ".docx", ".doc"}

        if not os.path.isdir(directory):
            logger.warning(f"Resume directory not found: {directory}")
            return results

        for fname in sorted(os.listdir(directory)):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in valid_exts:
                continue
            fpath = os.path.join(directory, fname)
            try:
                text = extract_text(fpath)
                if text and len(text) > 50:
                    results.append((fname, text))
            except Exception as e:
                logger.warning(f"Failed to load {fname}: {e}")

        return results

    def save_results(self, result: PipelineResult, storage) -> bool:
        """Save pipeline results to v5 storage layer.

        Args:
            result: PipelineResult from run()
            storage: Storage instance from storage.db

        Returns:
            True if saved successfully
        """
        try:
            if not storage:
                logger.warning("No storage provided, cannot save results")
                return False
            if result.job:
                job_dict = {
                    "title": result.job.title,
                    "company": result.job.company,
                    "department": result.job.team or result.job.department,
                    "description": result.job.description,
                    "required_skills": result.job.required_skills,
                    "preferred_skills": result.job.preferred_skills,
                    "min_years_experience": result.job.min_years_experience,
                    "max_years_experience": result.job.max_years_experience,
                    "education": result.job.education,
                    "salary_range": result.job.salary_range,
                    "company_tier": result.job.company_tier,
                    "industry": result.job.industry,
                    "urgency": result.job.urgency,
                    "priority_level": result.job.priority_level,
                    "key_selling_points": result.job.key_selling_points,
                    "hidden_requirements": result.job.hidden_requirements,
                    "raw_text": result.job.raw_text[:2000],
                    "source": "agent_pipeline",
                }
                jid = storage.save_job(job_dict)

                # Save matches
                for score in result.matched_scores:
                    match_dict = {
                        "candidate_id": score.candidate_name,
                        "candidate_name": score.candidate_name,
                        "job_id": jid,
                        "job_title": score.job_title,
                        "overall_score": round(score.overall_score / 100, 3),
                        "skill_score": round(score.skill_score / 100, 3),
                        "experience_score": round(score.experience_score / 100, 3),
                        "education_score": round(score.education_score / 100, 3),
                        "project_score": round(score.project_score / 100, 3),
                        "signal_score": round(score.signal_score / 100, 3),
                        "matched_skills": score.matched_skills,
                        "missing_skills": score.missing_skills,
                        "strengths": score.strengths,
                        "gaps": score.gaps,
                        "reasoning": score.reasoning,
                        "recommendation": score.recommendation,
                    }
                    try:
                        storage.save_match(match_dict)
                    except Exception as e:
                        logger.warning(f"Failed to save match for {score.candidate_name}: {e}")

            return True
        except Exception as e:
            logger.error(f"Failed to save pipeline results: {e}")
            return False
