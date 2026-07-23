"""Deterministic hard-constraint gate. Runs BEFORE the LLM: incompatible
profiles are excluded WITH an explicit reason and never reach the semantic
judgment. Only enum dimensions are decided here (availability, night shifts,
language level) — never free-text skills."""

from __future__ import annotations

from bussola.matching.models import ConstraintOutcome, JobRequest, RequiredLanguage
from bussola.profile.enums import Availability, LanguageLevel, WorkConstraint
from bussola.profile.models import WorkProfile

_LEVEL_ORDER = {
    LanguageLevel.BASIC: 0,
    LanguageLevel.INTERMEDIATE: 1,
    LanguageLevel.FLUENT: 2,
    LanguageLevel.NATIVE: 3,
}


def _availability_conflict(profile: WorkProfile, job: JobRequest) -> str | None:
    if job.required_availability is None or profile.aspiration is None:
        return None
    person = profile.aspiration.availability
    if person is None or person is Availability.FLEXIBLE:
        return None
    # A full-time-available person can also take a part-time position; the only
    # confirmed conflict is a part-time-only person against a full-time job.
    if job.required_availability is Availability.FULL_TIME and person is Availability.PART_TIME:
        return "job requires full-time but person is available part-time only"
    return None


def _night_conflict(profile: WorkProfile, job: JobRequest) -> str | None:
    if not job.involves_night_shifts or profile.aspiration is None:
        return None
    if WorkConstraint.NO_NIGHT_SHIFTS in profile.aspiration.constraints:
        return "job involves night shifts but person cannot work nights"
    return None


def _part_time_only_conflict(profile: WorkProfile, job: JobRequest) -> str | None:
    if profile.aspiration is None:
        return None
    if (
        job.required_availability is Availability.FULL_TIME
        and WorkConstraint.PART_TIME_ONLY in profile.aspiration.constraints
    ):
        return "job requires full-time but person is part-time only"
    return None


def _language_conflicts(profile: WorkProfile, job: JobRequest) -> list[str]:
    reasons: list[str] = []
    for req in job.required_languages:
        if not _has_language(profile, req):
            reasons.append(f"missing language {req.language} at level {req.min_level.value}")
    return reasons


def _has_language(profile: WorkProfile, req: RequiredLanguage) -> bool:
    need = _LEVEL_ORDER[req.min_level]
    target = req.language.strip().lower()
    return any(
        lang.language.strip().lower() == target and _LEVEL_ORDER[lang.level] >= need
        for lang in profile.languages
    )


def evaluate(profile: WorkProfile, job: JobRequest) -> ConstraintOutcome:
    reasons: list[str] = []
    for reason in (
        _availability_conflict(profile, job),
        _night_conflict(profile, job),
        _part_time_only_conflict(profile, job),
    ):
        if reason is not None:
            reasons.append(reason)
    reasons.extend(_language_conflicts(profile, job))
    if reasons:
        return ConstraintOutcome(compatible=False, reasons=reasons)
    return ConstraintOutcome(compatible=True, reasons=["all hard constraints satisfied"])
