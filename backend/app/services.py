from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from .config import Settings
from .guardrails import redact_personal_data, review_outputs
from .models import (
    AnalysisRunRequest,
    AnalysisRunResponse,
    CandidateEvaluation,
    CandidateInput,
    CandidateProfile,
    CriteriaMatch,
    ExportFormat,
    ExportResponse,
    GuardrailResult,
    JobCreateRequest,
    JobCriteria,
    JobRecord,
    RankedCandidate,
    ReviewDecisionRequest,
    RunStatus,
    ShortlistRecommendation,
    SourceReference,
)
from .storage import SQLiteStore


class RecruitmentService:
    def __init__(self, settings: Settings, store: SQLiteStore) -> None:
        self.settings = settings
        self.store = store

    def create_job(self, request: JobCreateRequest) -> JobRecord:
        now = datetime.now(UTC)
        criteria = JobCriteria(
            required=_dedupe(request.must_have_skills + _extract_requirement_lines(request.description, "required")),
            preferred=_dedupe(request.nice_to_have_skills + _extract_requirement_lines(request.description, "preferred")),
            disqualifying=_dedupe(request.constraints),
            responsibilities=_dedupe(request.responsibilities),
        )
        if not criteria.required and not criteria.preferred:
            criteria.required = _extract_keywords(request.description)[:6]

        job = JobRecord(
            id=uuid4().hex,
            title=request.title,
            description=request.description,
            seniority=request.seniority,
            location=request.location,
            work_model=request.work_model,
            criteria=criteria,
            created_at=now,
            updated_at=now,
        )
        self.store.save_job(job.id, job.model_dump(mode="json"))
        self.store.audit("job_created", job.id, {"title": job.title, "criteria_count": len(criteria.required) + len(criteria.preferred)})
        return job

    def update_criteria(self, job_id: str, criteria: JobCriteria) -> JobRecord | None:
        payload = self.store.get_job(job_id)
        if not payload:
            return None
        payload["criteria"] = criteria.model_dump(mode="json")
        payload["updated_at"] = datetime.now(UTC).isoformat()
        self.store.save_job(job_id, payload)
        self.store.audit("criteria_updated", job_id, {"criteria_count": len(criteria.required) + len(criteria.preferred)})
        return JobRecord.model_validate(payload)

    def run_analysis(self, request: AnalysisRunRequest) -> AnalysisRunResponse | None:
        job_payload = self.store.get_job(request.job_id)
        if not job_payload:
            return None
        if len(request.candidates) > self.settings.max_candidates_per_run:
            msg = f"A run supports at most {self.settings.max_candidates_per_run} candidates."
            raise ValueError(msg)

        job = JobRecord.model_validate(job_payload)
        now = datetime.now(UTC)
        run_id = uuid4().hex
        profiles = [self._research_candidate(candidate) for candidate in request.candidates]
        evaluations = [self._evaluate_candidate(job.criteria, profile) for profile in profiles]
        guardrail = review_outputs(profiles, evaluations)

        recommendation = None
        status = RunStatus.COMPLETED
        errors: list[str] = []
        if guardrail.passed:
            recommendation = self._recommend(profiles, evaluations, guardrail)
        else:
            status = RunStatus.FAILED
            errors.extend(guardrail.findings)

        response = AnalysisRunResponse(
            run_id=run_id,
            job_id=job.id,
            status=status,
            progress_phase=status,
            candidate_count=len(request.candidates),
            created_at=now,
            updated_at=datetime.now(UTC),
            warnings=[],
            profiles=profiles,
            evaluations=evaluations,
            recommendation=recommendation,
            errors=errors,
        )
        self.store.save_run(run_id, job.id, response.model_dump(mode="json"))
        self.store.audit(
            "analysis_run_completed",
            run_id,
            {
                "runtime": self.settings.aamad_target_runtime,
                "model": self.settings.model_name,
                "temperature": self.settings.crewai_temperature,
                "max_tokens": self.settings.crewai_max_tokens,
                "guardrail_passed": guardrail.passed,
            },
        )
        return response

    def get_run(self, run_id: str) -> AnalysisRunResponse | None:
        payload = self.store.get_run(run_id)
        return AnalysisRunResponse.model_validate(payload) if payload else None

    def save_decisions(self, run_id: str, request: ReviewDecisionRequest) -> AnalysisRunResponse | None:
        run = self.get_run(run_id)
        if not run:
            return None
        decisions = [decision.model_dump(mode="json") for decision in request.decisions]
        self.store.save_decisions(run_id, decisions)
        self.store.audit("review_decisions_saved", run_id, {"decision_count": len(decisions)})
        return run

    def export_run(self, run_id: str, export_format: ExportFormat) -> ExportResponse | None:
        run = self.get_run(run_id)
        if not run:
            return None
        generated_at = datetime.now(UTC)
        if export_format == ExportFormat.JSON:
            content = run.model_dump_json(indent=2)
        else:
            content = self._to_markdown(run)
        self.store.audit("run_exported", run_id, {"format": export_format.value})
        return ExportResponse(run_id=run_id, format=export_format, content=content, generated_at=generated_at)

    def _research_candidate(self, candidate: CandidateInput) -> CandidateProfile:
        text = candidate.text or ""
        redacted_text = redact_personal_data(text)
        snippets = _sentences(redacted_text)[:5]
        evidence = [SourceReference(source_id=candidate.id, label=candidate.label, snippet=snippet) for snippet in snippets]
        return CandidateProfile(
            candidate_id=candidate.id,
            label=candidate.label,
            name=_guess_name(text),
            headline=snippets[0] if snippets else None,
            skills=_extract_keywords(text),
            education=_extract_lines_matching(text, ("university", "college", "degree", "bachelor", "master", "phd")),
            certifications=_extract_lines_matching(text, ("certified", "certification", "certificate")),
            projects=_extract_lines_matching(text, ("project", "built", "implemented", "launched")),
            employers=_extract_lines_matching(text, ("company", "inc", "llc", "corp", "employer")),
            links=re.findall(r"https?://\S+", text),
            evidence=evidence,
            uncertainty_flags=[] if len(text.split()) >= 40 else ["Candidate material is short; extraction confidence may be limited."],
        )

    def _evaluate_candidate(self, criteria: JobCriteria, profile: CandidateProfile) -> CandidateEvaluation:
        searchable = " ".join(profile.skills + profile.projects + profile.employers + [profile.headline or ""]).lower()
        required_matches = [_match_criterion(criterion, searchable, profile.evidence) for criterion in criteria.required]
        preferred_matches = [_match_criterion(criterion, searchable, profile.evidence) for criterion in criteria.preferred]
        matched_required = sum(match.status == "matched" for match in required_matches)
        matched_preferred = sum(match.status == "matched" for match in preferred_matches)
        total_weight = max((len(required_matches) * 2) + len(preferred_matches), 1)
        score = int((((matched_required * 2) + matched_preferred) / total_weight) * 100)
        gaps = [match.criterion for match in required_matches + preferred_matches if match.status != "matched"]
        strengths = [match.criterion for match in required_matches + preferred_matches if match.status == "matched"]
        return CandidateEvaluation(
            candidate_id=profile.candidate_id,
            fit_score=score,
            required_matches=required_matches,
            preferred_matches=preferred_matches,
            strengths=strengths[:6],
            gaps=gaps[:6],
            risks=profile.uncertainty_flags,
            confidence="high" if score >= 75 and not profile.uncertainty_flags else "medium" if score >= 45 else "low",
            follow_up_questions=[f"Can you describe recent hands-on experience with {gap}?" for gap in gaps[:3]],
        )

    def _recommend(
        self,
        profiles: list[CandidateProfile],
        evaluations: list[CandidateEvaluation],
        guardrail: GuardrailResult,
    ) -> ShortlistRecommendation:
        profile_by_id = {profile.candidate_id: profile for profile in profiles}
        ranked: list[RankedCandidate] = []
        for rank, evaluation in enumerate(sorted(evaluations, key=lambda item: item.fit_score, reverse=True), start=1):
            profile = profile_by_id[evaluation.candidate_id]
            rationale = "Matched criteria: " + (", ".join(evaluation.strengths[:4]) if evaluation.strengths else "no explicit criteria matches found")
            ranked.append(
                RankedCandidate(
                    rank=rank,
                    candidate_id=evaluation.candidate_id,
                    label=profile.label,
                    fit_score=evaluation.fit_score,
                    rationale=rationale,
                    confidence=evaluation.confidence,
                    missing_information=evaluation.gaps[:4],
                    interview_prompts=evaluation.follow_up_questions,
                )
            )
        return ShortlistRecommendation(
            human_review_notice="Recommendations are decision-support outputs and require recruiter review before any candidate disposition.",
            ranked_candidates=ranked,
            guardrail_summary=guardrail,
            generated_at=datetime.now(UTC),
        )

    def _to_markdown(self, run: AnalysisRunResponse) -> str:
        lines = [
            f"# Recruitment Shortlist Export",
            "",
            f"Run ID: {run.run_id}",
            f"Status: {run.status.value}",
            "",
        ]
        if run.recommendation:
            lines.extend([run.recommendation.human_review_notice, ""])
            for candidate in run.recommendation.ranked_candidates:
                lines.extend(
                    [
                        f"## {candidate.rank}. {candidate.label}",
                        f"Fit score: {candidate.fit_score}",
                        f"Confidence: {candidate.confidence}",
                        f"Rationale: {candidate.rationale}",
                        "Missing information: " + (", ".join(candidate.missing_information) or "None identified"),
                        "Interview prompts: " + ("; ".join(candidate.interview_prompts) or "None generated"),
                        "",
                    ]
                )
        if run.errors:
            lines.extend(["## Guardrail / Error Findings", *[f"- {error}" for error in run.errors], ""])
        return "\n".join(lines)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _extract_requirement_lines(description: str, marker: str) -> list[str]:
    matches: list[str] = []
    for line in description.splitlines():
        lowered = line.lower()
        if marker in lowered or "must" in lowered or "required" in lowered:
            matches.extend(part.strip(" -:;") for part in re.split(r"[,;]", line) if len(part.strip()) > 2)
    return matches


def _extract_keywords(text: str) -> list[str]:
    common_skills = (
        "python",
        "fastapi",
        "sql",
        "react",
        "typescript",
        "aws",
        "docker",
        "kubernetes",
        "machine learning",
        "data analysis",
        "leadership",
        "recruiting",
    )
    lowered = text.lower()
    return [skill for skill in common_skills if skill in lowered]


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|\n+", text) if sentence.strip()]


def _extract_lines_matching(text: str, terms: tuple[str, ...]) -> list[str]:
    lines = _sentences(text)
    return [line[:240] for line in lines if any(term in line.lower() for term in terms)][:6]


def _guess_name(text: str) -> str | None:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if 2 <= len(first_line.split()) <= 4 and len(first_line) <= 80:
        return first_line
    return None


def _match_criterion(criterion: str, searchable: str, evidence: list[SourceReference]) -> CriteriaMatch:
    terms = [term for term in re.findall(r"[a-zA-Z][a-zA-Z+#.]{2,}", criterion.lower()) if term not in {"required", "preferred", "must", "have"}]
    matched = any(term in searchable for term in terms)
    return CriteriaMatch(criterion=criterion, status="matched" if matched else "missing", evidence=evidence[:2] if matched else [])