"""In-memory interview session state. The confirmed WorkProfile is built up
section by section; the app persists it per confirmed section (see Interview).

Two modes share this module:
- first interview (`InterviewSession`): fresh profile, all `SECTIONS` in
  order, `merge()` OVERWRITES each section's fields (unchanged behaviour).
- follow-up (`FollowupInterviewSession`, built via `InterviewSession.
  for_followup`): starts on an EXISTING profile, walks a REDUCED section
  order, and `merge()` APPENDS/UPGRADES instead of overwriting, so a
  follow-up interview can never lose or downgrade data already confirmed
  in a prior interview (nucleo §5)."""

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
from bussola.profile.enums import EvidenceGrade
from bussola.profile.models import (
    Aspiration,
    DesiredTraining,
    LanguageKnown,
    Skill,
    WorkProfile,
)

# Follow-up interviews walk a reduced, follow-up-ordered subset of the
# sections, reusing the SAME Section objects (base_question/extraction_model/
# extraction_prompt unchanged) so nothing about how a section is asked or
# extracted differs between modes.
_SECTIONS_BY_KEY = {section.key: section for section in SECTIONS}
FOLLOWUP_SECTIONS: tuple[Section, ...] = tuple(
    _SECTIONS_BY_KEY[key] for key in ("experiences", "skills", "aspirations")
)

# How strongly a skill is evidenced, from weakest to strongest. Mirrors the
# declaration order of `EvidenceGrade` but is spelled out explicitly (same
# convention as `_LEVEL_ORDER` in matching/hard_constraints.py) so the
# ordering is not silently affected by a future reordering of the enum.
_EVIDENCE_ORDER = {
    EvidenceGrade.STATED: 0,
    EvidenceGrade.DEMONSTRATED: 1,
    EvidenceGrade.CERTIFIED: 2,
}


def _higher_evidence(a: EvidenceGrade, b: EvidenceGrade) -> EvidenceGrade:
    return a if _EVIDENCE_ORDER[a] >= _EVIDENCE_ORDER[b] else b


def _merge_skills(existing: list[Skill], new: list[Skill]) -> list[Skill]:
    """Union by name (case-insensitive): a known skill is kept and its
    evidence raised to the higher grade (never downgraded, never
    duplicated); a genuinely new skill is appended."""
    merged = list(existing)
    index_by_name = {skill.name.strip().lower(): i for i, skill in enumerate(merged)}
    for skill in new:
        key = skill.name.strip().lower()
        i = index_by_name.get(key)
        if i is None:
            merged.append(skill)
            index_by_name[key] = len(merged) - 1
        else:
            current = merged[i]
            merged[i] = current.model_copy(
                update={"evidence": _higher_evidence(current.evidence, skill.evidence)}
            )
    return merged


def _merge_languages(
    existing: list[LanguageKnown], new: list[LanguageKnown]
) -> list[LanguageKnown]:
    """Union by language (case-insensitive): existing entries are kept as-is;
    a language not already known is added."""
    merged = list(existing)
    known = {lang.language.strip().lower() for lang in merged}
    for lang in new:
        key = lang.language.strip().lower()
        if key not in known:
            merged.append(lang)
            known.add(key)
    return merged


def _merge_strings(existing: list[str], new: list[str]) -> list[str]:
    """Union, de-duplicated case-insensitively, preserving existing order
    with genuinely new values appended."""
    merged = list(existing)
    seen = {value.strip().lower() for value in merged}
    for value in new:
        key = value.strip().lower()
        if key not in seen:
            merged.append(value)
            seen.add(key)
    return merged


def _merge_desired_training(
    existing: list[DesiredTraining], new: list[DesiredTraining]
) -> list[DesiredTraining]:
    """Union by topic (case-insensitive), de-duplicated."""
    merged = list(existing)
    seen = {item.topic.strip().lower() for item in merged}
    for item in new:
        key = item.topic.strip().lower()
        if key not in seen:
            merged.append(item)
            seen.add(key)
    return merged


class InterviewSession:
    def __init__(self, pseudonym_id: str, language: str) -> None:
        self.language = language
        self.profile = WorkProfile(pseudonym_id=pseudonym_id)
        self.section_index = 0
        self._sections: tuple[Section, ...] = SECTIONS

    @classmethod
    def for_followup(cls, profile: WorkProfile, language: str) -> "InterviewSession":
        """Start a follow-up interview session on an EXISTING profile: a
        reduced section order and append/upgrade merge (never overwrite),
        so prior data survives untouched (nucleo §5)."""
        return FollowupInterviewSession(profile, language)

    @property
    def current_section(self) -> Section | None:
        if self.section_index >= len(self._sections):
            return None
        return self._sections[self.section_index]

    @property
    def completed(self) -> bool:
        return self.section_index >= len(self._sections)

    def advance(self) -> None:
        self.section_index += 1

    def _aspiration(self) -> Aspiration:
        if self.profile.aspiration is None:
            self.profile.aspiration = Aspiration()
        return self.profile.aspiration

    def merge(self, extracted: BaseModel) -> None:
        """Apply an extracted section model to the partial profile
        (first-interview semantics: OVERWRITE each section's fields)."""
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


class FollowupInterviewSession(InterviewSession):
    """Follow-up mode: starts on an EXISTING profile (not a fresh one), walks
    the reduced `FOLLOWUP_SECTIONS` order, and merges with append/upgrade
    semantics — prior data is never lost or downgraded (nucleo §5).

    `merge()` can run MORE THAN ONCE for the same section: the person may see
    the summary, reject it ("no, correggi"), and re-answer — `Interview._submit`
    re-asks the SAME section without advancing, and each new answer merges
    again. Because append/upgrade is not naturally idempotent (a plain append
    would accumulate the rejected answer's contribution on top of the
    corrected one), `merge()` always recomputes from a BASELINE snapshot of
    the profile taken ONCE at construction (the prior-confirmed state, before
    this follow-up session touched anything) plus the CURRENT extraction —
    never from `self.profile`'s already-merged state. A re-answer therefore
    REPLACES the previous (rejected) delta instead of stacking on it, while
    everything the person confirmed before this follow-up interview started
    is still preserved."""

    def __init__(self, profile: WorkProfile, language: str) -> None:
        self.language = language
        self.profile = profile
        self.section_index = 0
        self._sections = FOLLOWUP_SECTIONS
        # Baseline snapshot (prior-confirmed data), frozen at construction.
        # Independent list copies: mutating `self.profile` afterwards (new
        # lists are assigned, never appended to in place) never mutates these.
        self._baseline_experiences = list(profile.experiences)
        self._baseline_skills = list(profile.skills)
        self._baseline_languages = list(profile.languages)
        self._baseline_digital_literacy = profile.digital_literacy
        self._baseline_fields_of_interest = (
            list(profile.aspiration.fields_of_interest) if profile.aspiration else []
        )
        self._baseline_desired_training = list(profile.desired_training)

    def merge(self, extracted: BaseModel) -> None:
        """Apply an extracted section model to the EXISTING profile
        (follow-up semantics: APPEND/UPGRADE from the baseline snapshot,
        never overwrite, drop, or accumulate across re-answers)."""
        if isinstance(extracted, ExperiencesExtraction):
            # Append the current extraction's delta onto the frozen prior
            # baseline (NOT onto `self.profile.experiences`, which may still
            # hold a rejected answer's delta from an earlier merge() call in
            # this same section) — a re-answer replaces, never stacks.
            self.profile.experiences = self._baseline_experiences + extracted.experiences
        elif isinstance(extracted, SkillsExtraction):
            self.profile.skills = _merge_skills(self._baseline_skills, extracted.skills)
            self.profile.languages = _merge_languages(self._baseline_languages, extracted.languages)
            self.profile.digital_literacy = (
                extracted.digital_literacy
                if extracted.digital_literacy is not None
                else self._baseline_digital_literacy
            )
        elif isinstance(extracted, AspirationsExtraction):
            asp = self._aspiration()
            asp.fields_of_interest = _merge_strings(
                self._baseline_fields_of_interest, extracted.fields_of_interest
            )
            self.profile.desired_training = _merge_desired_training(
                self._baseline_desired_training, extracted.desired_training
            )
        else:  # pragma: no cover - defensive: follow-up only walks the
            # sections above (experiences, skills, aspirations).
            raise TypeError(f"unexpected extraction model in follow-up mode: {type(extracted)!r}")
