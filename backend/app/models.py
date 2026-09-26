from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class RunStatus(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    RESEARCHING = "researching"
    EVALUATING = "evaluating"
    GUARDRAIL_REVIEW = "guardrail_review"
    RECOMMENDING = "recommending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class DecisionLabel(StrEnum):
    ADVANCE = "advance"
    HOLD = "hold"
    DECLINE = "decline"
    NEEDS_MORE_INFORMATION = "needs_more_information"


class SourceType(StrEnum):
    TEXT = "text"
    PDF = "pdf"
    DOCX = "docx"
    URL = "url"


class JobCriteria(BaseModel):
    required: list[str] = Field(default_factory=list)
    preferred: list[str] = Field(default_factory=list)
    disqualifying: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)


class JobCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=20)
    seniority: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=120)
    work_model: str | None = Field(default=None, max_length=80)
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class JobRecord(BaseModel):
    id: str
    title: str
    description: str
    seniority: str | None = None
    location: str | None = None
    work_model: str | None = None
    criteria: JobCriteria
    created_at: datetime
    updated_at: datetime


class CandidateInput(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    label: str = Field(min_length=1, max_length=160)
    source_type: SourceType = SourceType.TEXT
    text: str | None = Field(default=None, min_length=20)
    approved_urls: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_text_for_text_sources(self) -> "CandidateInput":
        if self.source_type == SourceType.TEXT and not self.text:
            msg = "text is required when source_type is text"
            raise ValueError(msg)
        return self


class AnalysisOptions(BaseModel):
    include_markdown_export: bool = True
    allow_public_url_fetch: bool = False


class AnalysisRunRequest(BaseModel):
    job_id: str = Field(min_length=1)
    candidates: list[CandidateInput] = Field(min_length=1, max_length=10)
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class SourceReference(BaseModel):
    source_id: str
    label: str
    snippet: str


class CandidateProfile(BaseModel):
    candidate_id: str
    label: str
    name: str | None = None
    headline: str | None = None
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    employers: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    evidence: list[SourceReference] = Field(default_factory=list)
    uncertainty_flags: list[str] = Field(default_factory=list)


class CriteriaMatch(BaseModel):
    criterion: str
    status: str
    evidence: list[SourceReference] = Field(default_factory=list)


class CandidateEvaluation(BaseModel):
    candidate_id: str
    fit_score: int = Field(ge=0, le=100)
    required_matches: list[CriteriaMatch] = Field(default_factory=list)
    preferred_matches: list[CriteriaMatch] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: str
    follow_up_questions: list[str] = Field(default_factory=list)


class GuardrailResult(BaseModel):
    passed: bool
    findings: list[str] = Field(default_factory=list)


class RankedCandidate(BaseModel):
    rank: int
    candidate_id: str
    label: str
    fit_score: int = Field(ge=0, le=100)
    rationale: str
    confidence: str
    missing_information: list[str] = Field(default_factory=list)
    interview_prompts: list[str] = Field(default_factory=list)


class ShortlistRecommendation(BaseModel):
    human_review_notice: str
    ranked_candidates: list[RankedCandidate]
    guardrail_summary: GuardrailResult
    generated_at: datetime


class AnalysisRunResponse(BaseModel):
    run_id: str
    job_id: str
    status: RunStatus
    progress_phase: RunStatus
    candidate_count: int
    created_at: datetime
    updated_at: datetime
    warnings: list[str] = Field(default_factory=list)
    profiles: list[CandidateProfile] = Field(default_factory=list)
    evaluations: list[CandidateEvaluation] = Field(default_factory=list)
    recommendation: ShortlistRecommendation | None = None
    errors: list[str] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    candidate_id: str
    label: DecisionLabel
    notes: str | None = Field(default=None, max_length=2000)


class ReviewDecisionRequest(BaseModel):
    decisions: list[ReviewDecision] = Field(min_length=1)


class ApiError(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    retryable: bool = False


class HealthResponse(BaseModel):
    status: str
    runtime: str
    database: str
    model_configured: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExportFormat(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"


class ExportResponse(BaseModel):
    run_id: str
    format: ExportFormat
    content: str
    generated_at: datetime


class CriteriaUpdateRequest(BaseModel):
    criteria: JobCriteria

    @field_validator("criteria")
    @classmethod
    def require_some_criteria(cls, criteria: JobCriteria) -> JobCriteria:
        if not criteria.required and not criteria.preferred:
            msg = "At least one required or preferred criterion is required."
            raise ValueError(msg)
        return criteria