from bussola.interview.sections import (
    AspirationsExtraction,
    SkillsExtraction,
    ConstraintsExtraction,
)
from bussola.interview.session import InterviewSession
from bussola.profile.enums import Availability, EvidenceGrade, SkillKind
from bussola.profile.models import Skill


def test_starts_at_first_section_with_empty_profile():
    s = InterviewSession("P-1", "it")
    assert s.current_section.key == "skills"
    assert s.profile.pseudonym_id == "P-1"
    assert s.profile.skills == []
    assert s.completed is False


def test_merge_applies_extracted_fields():
    s = InterviewSession("P-1", "it")
    s.merge(
        SkillsExtraction(
            skills=[
                Skill(name="cooking", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
            ]
        )
    )
    assert s.profile.skills[0].name == "cooking"


def test_merge_composes_aspiration_across_sections():
    s = InterviewSession("P-1", "it")
    s.merge(AspirationsExtraction(fields_of_interest=["ristorazione"]))
    s.merge(ConstraintsExtraction(availability=Availability.PART_TIME))
    assert s.profile.aspiration is not None
    assert s.profile.aspiration.fields_of_interest == ["ristorazione"]
    assert s.profile.aspiration.availability is Availability.PART_TIME


def test_advance_and_completion():
    s = InterviewSession("P-1", "it")
    for _ in range(5):
        assert s.completed is False
        s.advance()
    assert s.completed is True
    assert s.current_section is None
