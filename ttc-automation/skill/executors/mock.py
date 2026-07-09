"""Mock executor that returns demo candidates for testing."""
from __future__ import annotations

from typing import List

from ..models import Candidate, SearchIntent
from .base import BaseExecutor


class MockExecutor(BaseExecutor):
    """Return demo candidates when no real data is available."""

    name = "mock"

    async def search(self, intent: SearchIntent, limit: int = 10) -> List[Candidate]:
        demo = [
            Candidate(
                id="mock_001",
                name="张伟",
                source=self.name,
                current_role="高级 Java 后端工程师",
                current_company="某头部电商",
                years_experience=6,
                location="上海",
                skills=["Java", "Spring", "MySQL", "Redis", "Kafka"],
                overall_score=88.5,
                jd_alignment=90.0,
                evidence="6 年 Java 经验，熟悉 Spring 生态与中间件",
            ),
            Candidate(
                id="mock_002",
                name="李娜",
                source=self.name,
                current_role="后端开发负责人",
                current_company="某独角兽",
                years_experience=8,
                location="上海",
                skills=["Java", "Go", "Microservices", "Kubernetes"],
                overall_score=85.0,
                jd_alignment=87.0,
                evidence="8 年经验，带过 5 人团队",
            ),
            Candidate(
                id="mock_003",
                name="王强",
                source=self.name,
                current_role="Python 算法工程师",
                current_company="某 AI 公司",
                years_experience=4,
                location="北京",
                skills=["Python", "PyTorch", "Machine Learning"],
                overall_score=78.0,
                jd_alignment=80.0,
                evidence="算法背景，适合 AI 项目",
            ),
        ]

        # Simple filtering by location/skills for slightly realistic behavior
        filtered = [c for c in demo]
        if intent.location:
            filtered = [c for c in filtered if intent.location in c.location]
        if intent.skills:
            filtered = [
                c for c in filtered
                if any(s.lower() in [x.lower() for x in c.skills] for s in intent.skills)
            ]

        return filtered[:limit]
