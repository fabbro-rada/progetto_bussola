"""Matching domain models. All work-only whitelists (extra="forbid"): a job
request cannot carry discriminatory or non-work criteria by construction."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from bussola.profile.enums import Availability, LanguageLevel

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)
_TEXT = 200


class RequiredLanguage(BaseModel):
    model_config = _STRICT
    language: str = Field(min_length=2, max_length=32)
    min_level: LanguageLevel


class JobRequestCreate(BaseModel):
    model_config = _STRICT
    title: str = Field(min_length=1, max_length=_TEXT)
    sector: str = Field(min_length=1, max_length=_TEXT)
    description: str = Field(default="", max_length=2000)
    required_skills: list[str] = Field(default_factory=list, max_length=30)
    required_languages: list[RequiredLanguage] = Field(default_factory=list, max_length=10)
    required_availability: Availability | None = None
    involves_night_shifts: bool = False
    training_prerequisites: list[str] = Field(default_factory=list, max_length=20)


class JobRequest(JobRequestCreate):
    id: int
    created_by: str


class RequirementVerdict(BaseModel):
    model_config = _STRICT
    requirement: str
    satisfied: bool
    evidence: str | None = None


class ConstraintOutcome(BaseModel):
    model_config = _STRICT
    compatible: bool
    reasons: list[str] = Field(default_factory=list)


class GapItem(BaseModel):
    model_config = _STRICT
    requirement: str
    recommended_training: str


class MatchResult(BaseModel):
    model_config = _STRICT
    pseudonym_id: str
    score: float
    requirements: list[RequirementVerdict] = Field(default_factory=list)
    constraint: ConstraintOutcome
    gaps: list[GapItem] = Field(default_factory=list)
