"""Work profile data model (Pydantic v2).

Every model forbids unknown fields (`extra="forbid"`). This is the
structural core of the profile-as-whitelist guarantee.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from bussola.profile.enums import (
    Availability,
    DigitalLiteracy,
    EvidenceGrade,
    LanguageLevel,
    OperationalNoteCategory,
    SkillKind,
    WorkConstraint,
)

# Shared strict config: unknown fields are rejected; strings are trimmed.
_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)

# Max length for the free-text fields that `sanitize_profile`
# (bussola.guardrails.pii) redacts in place. Presidio replaces a detected
# PII span with a placeholder token (e.g. `<EMAIL_ADDRESS>`, `<PHONE_NUMBER>`)
# that can be longer than the original span, so these fields need headroom
# beyond the plain input bound to still validate after redaction, while
# staying capped so free-text input remains bounded.
_FREE_TEXT_MAX_LENGTH = 200


class LanguageKnown(BaseModel):
    model_config = _STRICT

    language: str = Field(min_length=2, max_length=32)
    level: LanguageLevel


class Skill(BaseModel):
    model_config = _STRICT

    name: str = Field(min_length=1, max_length=_FREE_TEXT_MAX_LENGTH)
    kind: SkillKind
    evidence: EvidenceGrade


class WorkExperience(BaseModel):
    model_config = _STRICT

    role: str = Field(min_length=1, max_length=_FREE_TEXT_MAX_LENGTH)
    sector: str = Field(min_length=1, max_length=_FREE_TEXT_MAX_LENGTH)
    duration_months: int = Field(ge=0, le=720)  # 0..60 years


class Aspiration(BaseModel):
    model_config = _STRICT

    fields_of_interest: list[str] = Field(default_factory=list, max_length=20)
    availability: Availability | None = None
    constraints: list[WorkConstraint] = Field(default_factory=list)


class DesiredTraining(BaseModel):
    model_config = _STRICT

    topic: str = Field(min_length=1, max_length=_FREE_TEXT_MAX_LENGTH)


class WorkProfile(BaseModel):
    """Work-only profile.

    By construction it cannot hold crimes, juridical position, health,
    family data, or any judgement/score about the person: there is simply
    no field for them, and unknown fields are rejected (`extra="forbid"`).
    """

    model_config = _STRICT

    pseudonym_id: str = Field(min_length=1, max_length=64)
    languages: list[LanguageKnown] = Field(default_factory=list)
    digital_literacy: DigitalLiteracy | None = None
    skills: list[Skill] = Field(default_factory=list)
    experiences: list[WorkExperience] = Field(default_factory=list)
    aspiration: Aspiration | None = None
    desired_training: list[DesiredTraining] = Field(default_factory=list)
    operational_notes: list[OperationalNoteCategory] = Field(default_factory=list)
