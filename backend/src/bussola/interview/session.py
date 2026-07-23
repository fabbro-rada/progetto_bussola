"""In-memory interview session state. The confirmed WorkProfile is built up
section by section; the app persists it per confirmed section (see Interview)."""

from __future__ import annotations

from pydantic import BaseModel

from bussola.interview.sections import (
    SECTIONS,
    AspirationsExtraction,
    SkillsExtraction,
    ExperiencesExtraction,
    PreferencesExtraction,
    Section,
    ConstraintsExtraction,
)
from bussola.profile.models import Aspiration, WorkProfile


class InterviewSession:
    def __init__(self, pseudonym_id: str, language: str) -> None:
        self.language = language
        self.profile = WorkProfile(pseudonym_id=pseudonym_id)
        self.section_index = 0

    @property
    def current_section(self) -> Section | None:
        if self.section_index >= len(SECTIONS):
            return None
        return SECTIONS[self.section_index]

    @property
    def completed(self) -> bool:
        return self.section_index >= len(SECTIONS)

    def advance(self) -> None:
        self.section_index += 1

    def _aspiration(self) -> Aspiration:
        if self.profile.aspiration is None:
            self.profile.aspiration = Aspiration()
        return self.profile.aspiration

    def merge(self, extracted: BaseModel) -> None:
        """Apply an extracted section model to the partial profile."""
        if isinstance(extracted, SkillsExtraction):
            self.profile.skills = extracted.skills
            self.profile.languages = extracted.languages
            self.profile.digital_literacy = extracted.digital_literacy
        elif isinstance(extracted, ExperiencesExtraction):
            self.profile.experiences = extracted.experiences
        elif isinstance(extracted, AspirationsExtraction):
            asp = self._aspiration()
            asp.fields_of_interest = extracted.fields_of_interest
            self.profile.desired_training = extracted.desired_training
        elif isinstance(extracted, ConstraintsExtraction):
            asp = self._aspiration()
            asp.availability = extracted.availability
            asp.constraints = extracted.constraints
        elif isinstance(extracted, PreferencesExtraction):
            self.profile.operational_notes = extracted.operational_notes
        else:  # pragma: no cover - defensive
            raise TypeError(f"unknown extraction model: {type(extracted)!r}")
