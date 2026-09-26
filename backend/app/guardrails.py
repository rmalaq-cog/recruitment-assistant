from __future__ import annotations

import re
from collections.abc import Iterable

from .models import CandidateEvaluation, CandidateProfile, GuardrailResult, ShortlistRecommendation


PROTECTED_CLASS_TERMS = {
    "age",
    "birthday",
    "married",
    "pregnant",
    "religion",
    "church",
    "mosque",
    "synagogue",
    "race",
    "ethnicity",
    "nationality",
    "disability",
    "gender",
    "sexual orientation",
}

AUTOMATED_DECISION_TERMS = {
    "automatically reject",
    "auto reject",
    "must reject",
    "do not hire",
    "unhireable",
}


def redact_personal_data(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[redacted-email]", text)
    text = re.sub(r"\+?\d[\d\s().-]{7,}\d", "[redacted-phone]", text)
    return text


def review_text_for_sensitive_language(chunks: Iterable[str]) -> GuardrailResult:
    findings: list[str] = []
    normalized = "\n".join(chunks).lower()

    for term in sorted(PROTECTED_CLASS_TERMS):
        if term in normalized:
            findings.append(f"Potential protected-class reference detected: {term}")

    for term in sorted(AUTOMATED_DECISION_TERMS):
        if term in normalized:
            findings.append(f"Automated decisioning language detected: {term}")

    return GuardrailResult(passed=not findings, findings=findings)


def review_outputs(
    profiles: list[CandidateProfile],
    evaluations: list[CandidateEvaluation],
    recommendation: ShortlistRecommendation | None = None,
) -> GuardrailResult:
    chunks: list[str] = []
    for profile in profiles:
        chunks.extend(profile.skills)
        chunks.extend(profile.education)
        chunks.extend(profile.certifications)
        chunks.extend(profile.projects)
        chunks.extend(profile.employers)
        chunks.extend(flag for flag in profile.uncertainty_flags)
    for evaluation in evaluations:
        chunks.extend(evaluation.strengths)
        chunks.extend(evaluation.gaps)
        chunks.extend(evaluation.risks)
        chunks.extend(evaluation.follow_up_questions)
    if recommendation:
        chunks.append(recommendation.human_review_notice)
        for candidate in recommendation.ranked_candidates:
            chunks.append(candidate.rationale)
            chunks.extend(candidate.missing_information)
            chunks.extend(candidate.interview_prompts)

    return review_text_for_sensitive_language(chunks)