import pytest

from bussola.guardrails.pii import PiiRedactor, sanitize_profile
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import (
    Aspiration,
    DesiredTraining,
    Skill,
    WorkExperience,
    WorkProfile,
)


@pytest.fixture(scope="session")
def redactor() -> PiiRedactor:
    return PiiRedactor()


def test_sanitize_redacts_pii_in_free_text(redactor):
    # Italian redaction is pattern-based only (no NER model, see pii.py
    # docstring), so the embedded PII here is an email, not a person name.
    profile = WorkProfile(
        pseudonym_id="P-010",
        skills=[
            Skill(
                name="assistente, contatto marco.rossi@example.com",
                kind=SkillKind.SOFT,
                evidence=EvidenceGrade.STATED,
            )
        ],
        experiences=[
            WorkExperience(role="aiuto cuoco", sector="ristorazione", duration_months=12)
        ],
    )
    clean = sanitize_profile(profile, redactor, language="it")

    assert "marco.rossi@example.com" not in clean.skills[0].name
    assert "<EMAIL_ADDRESS>" in clean.skills[0].name
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


def test_sanitize_handles_redaction_that_expands_field_length(redactor):
    """A short PII span (e.g. `a@b.co`, 6 chars) is replaced by a longer
    placeholder (`<EMAIL_ADDRESS>`, 15 chars). A free-text field close to
    the boundary can therefore come out of redaction *longer* than it went
    in. `sanitize_profile` must still return a schema-valid `WorkProfile`
    in that case, never a silently invalid one."""
    original_pii = "a@b.co"
    role = (
        "responsabile assistenza clienti e contatto diretto quotidiano "
        f"{original_pii} in sede"
    )
    profile = WorkProfile(
        pseudonym_id="P-012",
        experiences=[
            WorkExperience(role=role, sector="ristorazione", duration_months=6)
        ],
    )

    clean = sanitize_profile(profile, redactor, language="it")

    redacted_role = clean.experiences[0].role
    assert original_pii not in redacted_role
    # The redacted copy must always re-validate against the schema, even
    # when redaction expanded the field beyond its original length.
    assert WorkProfile.model_validate(clean.model_dump())


def test_sanitize_redacts_pii_in_aspiration_and_desired_training(redactor):
    """`aspiration.fields_of_interest` and `desired_training` are redacted
    too. Uses pattern-based PII (email) so it works under `language="it"`
    with no NER model."""
    profile = WorkProfile(
        pseudonym_id="P-013",
        aspiration=Aspiration(
            fields_of_interest=["contattami a mario@example.com per proposte"]
        ),
        desired_training=[
            DesiredTraining(topic="corso richiesto, scrivere a laura@example.com")
        ],
    )

    clean = sanitize_profile(profile, redactor, language="it")

    assert "mario@example.com" not in clean.aspiration.fields_of_interest[0]
    assert "<EMAIL_ADDRESS>" in clean.aspiration.fields_of_interest[0]
    assert "laura@example.com" not in clean.desired_training[0].topic
    assert "<EMAIL_ADDRESS>" in clean.desired_training[0].topic
