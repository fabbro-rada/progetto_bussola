from bussola.matching.gaps import compute
from bussola.matching.models import RequirementVerdict
from bussola.matching.scoring import score
from bussola.profile.models import DesiredTraining, WorkProfile


def _v(name, sat):
    return RequirementVerdict(requirement=name, satisfied=sat, evidence=("x" if sat else None))


def test_score_is_fraction_satisfied():
    assert score([_v("a", True), _v("b", True), _v("c", False), _v("d", False)]) == 0.5
    assert score([]) == 0.0
    assert score([_v("a", True)]) == 1.0


def test_gaps_only_for_unsatisfied():
    profile = WorkProfile(pseudonym_id="P-1")
    gaps = compute([_v("cucina", True), _v("igiene alimentare", False)], profile)
    assert len(gaps) == 1
    assert gaps[0].requirement == "igiene alimentare"


def test_gap_uses_desired_training_when_matching():
    profile = WorkProfile(
        pseudonym_id="P-1",
        desired_training=[DesiredTraining(topic="corso di igiene alimentare")],
    )
    gaps = compute([_v("igiene alimentare", False)], profile)
    assert "igiene alimentare" in gaps[0].recommended_training.lower()
