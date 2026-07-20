"""Work profile data model (Pydantic v2).

Every model forbids unknown fields (`extra="forbid"`). This is the
structural core of the profile-as-whitelist guarantee.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from bussola.profile.enums import (
    Availability,
    EvidenceGrade,
    LanguageLevel,
    SkillKind,
    WorkConstraint,
)

# Shared strict config: unknown fields are rejected; strings are trimmed.
_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LanguageKnown(BaseModel):
    model_config = _STRICT

    language: str = Field(min_length=2, max_length=32)
    level: LanguageLevel


class Skill(BaseModel):
    model_config = _STRICT

    name: str = Field(min_length=1, max_length=80)
    kind: SkillKind
    evidence: EvidenceGrade


class WorkExperience(BaseModel):
    model_config = _STRICT

    role: str = Field(min_length=1, max_length=80)
    sector: str = Field(min_length=1, max_length=80)
    duration_months: int = Field(ge=0, le=720)  # 0..60 years


class Aspiration(BaseModel):
    model_config = _STRICT

    fields_of_interest: list[str] = Field(default_factory=list, max_length=20)
    availability: Availability | None = None
    constraints: list[WorkConstraint] = Field(default_factory=list)


class DesiredTraining(BaseModel):
    model_config = _STRICT

    topic: str = Field(min_length=1, max_length=80)
