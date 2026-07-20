import pytest
from pydantic import ValidationError

from bussola.profile.enums import (
    DigitalLiteracy,
    EvidenceGrade,
    LanguageLevel,
    SkillKind,
)
from bussola.profile.models import LanguageKnown, Skill, WorkProfile


def test_minimal_profile_is_valid():
    p = WorkProfile(pseudonym_id="P-001")
    assert p.pseudonym_id == "P-001"
    assert p.skills == []
    assert p.operational_notes == []


def test_rich_profile_round_trips():
    p = WorkProfile(
        pseudonym_id="P-002",
        languages=[LanguageKnown(language="italian", level=LanguageLevel.FLUENT)],
        digital_literacy=DigitalLiteracy.BASIC,
        skills=[
            Skill(name="cooking", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
        ],
    )
    restored = WorkProfile.model_validate(p.model_dump())
    assert restored == p


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "criminal_record",
        "reato",
        "offense",
        "sentence",
        "juridical_position",
        "health",
        "diagnosis",
        "medical_notes",
        "family",
        "family_situation",
        "risk_score",
        "dangerousness",
        "recidivism_risk",
    ],
)
def test_forbidden_fields_are_rejected(forbidden_field):
    with pytest.raises(ValidationError):
        WorkProfile(pseudonym_id="P-003", **{forbidden_field: "whatever"})


def test_operational_notes_reject_free_text():
    # Only predefined categories are allowed; free text must be rejected.
    with pytest.raises(ValidationError):
        WorkProfile(pseudonym_id="P-004", operational_notes=["condannato per furto"])
