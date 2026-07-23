from bussola.matching.models import JobRequest
from bussola.matching.semantic import judge_requirements
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile


def _profile() -> WorkProfile:
    return WorkProfile(
        pseudonym_id="P-1",
        skills=[
            Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
        ],
    )


def _job() -> JobRequest:
    return JobRequest(
        id=1,
        created_by="op1",
        title="Cuoco",
        sector="ristorazione",
        required_skills=["cucina", "igiene alimentare"],
    )


def test_parses_grounded_verdicts(make_fake_json_llm):
    client = make_fake_json_llm(
        json_responses=[
            {
                "verdicts": [
                    {"requirement": "cucina", "satisfied": True, "evidence": "Cucina"},
                    {"requirement": "igiene alimentare", "satisfied": False, "evidence": None},
                ]
            }
        ]
    )
    verdicts = judge_requirements(client, _profile(), _job(), "it")
    assert len(verdicts) == 2
    assert verdicts[0].satisfied is True and verdicts[0].evidence == "Cucina"
    assert verdicts[1].satisfied is False


def test_invalid_output_is_fail_safe_unsatisfied(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[{"unexpected": "x"}])
    verdicts = judge_requirements(client, _profile(), _job(), "it")
    # one verdict per requirement, all unsatisfied, no invented evidence
    assert [v.requirement for v in verdicts] == ["cucina", "igiene alimentare"]
    assert all(v.satisfied is False and v.evidence is None for v in verdicts)


def test_no_requirements_returns_empty(make_fake_json_llm):
    job = JobRequest(id=1, created_by="op1", title="t", sector="s")
    client = make_fake_json_llm(json_responses=[{"verdicts": []}])
    assert judge_requirements(client, _profile(), job, "it") == []
