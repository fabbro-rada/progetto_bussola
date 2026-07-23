import pytest
from pydantic import ValidationError

from bussola.matching.models import (
    JobRequest,
    JobRequestCreate,
    MatchResult,
    RequiredLanguage,
    RequirementVerdict,
)
from bussola.profile.enums import Availability, LanguageLevel


def test_job_request_create_forbids_extra_fields():
    with pytest.raises(ValidationError):
        JobRequestCreate(title="Cuoco", sector="ristorazione", danger_score=9)


def test_job_request_create_minimal():
    jr = JobRequestCreate(title="Cuoco", sector="ristorazione")
    assert jr.required_skills == []
    assert jr.involves_night_shifts is False
    assert jr.required_availability is None


def test_required_language_roundtrip():
    rl = RequiredLanguage(language="it", min_level=LanguageLevel.INTERMEDIATE)
    assert rl.min_level is LanguageLevel.INTERMEDIATE


def test_job_request_has_id_and_creator():
    jr = JobRequest(
        id=1,
        created_by="op1",
        title="Cuoco",
        sector="ristorazione",
        required_availability=Availability.FULL_TIME,
    )
    assert jr.id == 1 and jr.created_by == "op1"


def test_match_result_shape():
    mr = MatchResult(
        pseudonym_id="P-1",
        score=0.5,
        requirements=[RequirementVerdict(requirement="cooking", satisfied=True, evidence="Cucina")],
        constraint={"compatible": True, "reasons": ["ok"]},
        gaps=[],
    )
    assert mr.requirements[0].satisfied is True
    assert mr.constraint.compatible is True
