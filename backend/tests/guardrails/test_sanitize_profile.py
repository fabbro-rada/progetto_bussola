import pytest

from bussola.guardrails.pii import PiiRedactor, sanitize_profile
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkExperience, WorkProfile


@pytest.fixture(scope="session")
def redactor() -> PiiRedactor:
    return PiiRedactor()


def test_sanitize_redacts_pii_in_free_text(redactor):
    profile = WorkProfile(
        pseudonym_id="P-010",
        skills=[
            Skill(
                name="assistente di Marco Rossi",
                kind=SkillKind.SOFT,
                evidence=EvidenceGrade.STATED,
            )
        ],
        experiences=[
            WorkExperience(role="aiuto cuoco", sector="ristorazione", duration_months=12)
        ],
    )
    clean = sanitize_profile(profile, redactor, language="it")

    assert "Marco Rossi" not in clean.skills[0].name
    # Non-free-text data is preserved unchanged.
    assert clean.experiences[0].duration_months == 12
    assert clean.pseudonym_id == "P-010"


def test_sanitize_does_not_mutate_original(redactor):
    profile = WorkProfile(
        pseudonym_id="P-011",
        skills=[
            Skill(
                name="contatto mario@example.com",
                kind=SkillKind.SOFT,
                evidence=EvidenceGrade.STATED,
            )
        ],
    )
    sanitize_profile(profile, redactor, language="it")

    # The original object is untouched.
    assert profile.skills[0].name == "contatto mario@example.com"
