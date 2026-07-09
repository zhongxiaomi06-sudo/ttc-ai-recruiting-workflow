"""Skill layer public models."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SearchIntent(BaseModel):
    """Structured intent parsed from a natural-language recruiting request."""

    query: str = Field(description="Original natural language query")
    title: str = Field(default="", description="Target job title")
    skills: list[str] = Field(default_factory=list, description="Required skills")
    location: str = Field(default="", description="Work location")
    min_years: int = Field(default=0, ge=0, description="Minimum years of experience")
    max_years: Optional[int] = Field(default=None, description="Maximum years of experience")
    education: str = Field(default="", description="Education requirement")
    salary_range: str = Field(default="", description="Salary range hint")
    company: str = Field(default="", description="Target company or industry")
    count: int = Field(default=10, ge=1, le=100, description="How many candidates to return")
    channels: list[str] = Field(default_factory=list, description="Requested channels")
    clarification: Optional[str] = Field(default=None, description="Clarification question if intent unclear")


class Candidate(BaseModel):
    """A single candidate returned by an executor."""

    id: str
    name: str = ""
    source: str = Field(description="Channel/executor that produced this candidate")
    source_url: str = ""
    current_role: str = ""
    current_company: str = ""
    years_experience: int = 0
    location: str = ""
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    email: str = ""
    phone: str = ""
    summary: str = ""
    overall_score: float = Field(default=0.0, ge=0, le=100)
    jd_alignment: float = Field(default=0.0, ge=0, le=100)
    risk_flags: list[str] = Field(default_factory=list)
    evidence: str = ""
    raw: dict[str, Any] = Field(default_factory=dict, description="Raw data from executor")


class SearchResult(BaseModel):
    """Output of a skill search invocation."""

    ok: bool = True
    query: str = ""
    intent: Optional[SearchIntent] = None
    sources: list[str] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    total_found: int = 0
    review_url: str = ""
    message: str = ""
    raw_executor_results: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    """Payload for POST /skill/search."""

    query: str = Field(min_length=1, max_length=4000)
    max_results: int = Field(default=10, ge=1, le=50)
    channels: list[str] = Field(default_factory=list)
    include_mock: bool = Field(default=False, description="Include demo candidates if no real data found")
