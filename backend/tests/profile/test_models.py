import pytest
from pydantic import ValidationError

from bussola.profile.enums import (
    EvidenceGrade,
    LanguageLevel,
    SkillKind,
)
from bussola.profile.models import (
    Aspiration,
    DesiredTraining,
    LanguageKnown,
    Skill,
    WorkExperience,
)


def test_language_known_valid():
    lk = LanguageKnown(language="arabic", level=LanguageLevel.NATIVE)
    assert lk.level is LanguageLevel.NATIVE


def test_skill_valid():
    s = Skill(name="welding", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
    assert s.name == "welding"


def test_work_experience_rejects_negative_duration():
    with pytest.raises(ValidationError):
        WorkExperience(role="cook", sector="catering", duration_months=-1)


def test_aspiration_defaults_are_empty():
    a = Aspiration()
    assert a.fields_of_interest == []
    assert a.constraints == []
    assert a.availability is None


def test_desired_training_valid():
    t = DesiredTraining(topic="electrical maintenance")
    assert t.topic == "electrical maintenance"


def test_leaf_model_rejects_unknown_field():
    with pytest.raises(ValidationError):
        Skill(
            name="welding",
            kind=SkillKind.TECHNICAL,
            evidence=EvidenceGrade.STATED,
            secret_note="x",
        )
