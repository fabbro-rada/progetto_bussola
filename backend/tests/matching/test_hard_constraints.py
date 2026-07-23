from bussola.matching.hard_constraints import evaluate
from bussola.matching.models import JobRequest, RequiredLanguage
from bussola.profile.enums import Availability, LanguageLevel, WorkConstraint
from bussola.profile.models import Aspiration, LanguageKnown, WorkProfile


def _job(**kw) -> JobRequest:
    base = dict(id=1, created_by="op1", title="t", sector="s")
    base.update(kw)
    return JobRequest(**base)


def test_night_shift_conflict_excludes_with_reason():
    profile = WorkProfile(
        pseudonym_id="P-1",
        aspiration=Aspiration(constraints=[WorkConstraint.NO_NIGHT_SHIFTS]),
    )
    out = evaluate(profile, _job(involves_night_shifts=True))
    assert out.compatible is False
    assert any("night" in r.lower() for r in out.reasons)


def test_part_time_only_conflicts_with_full_time():
    profile = WorkProfile(
        pseudonym_id="P-1",
        aspiration=Aspiration(availability=Availability.PART_TIME),
    )
    out = evaluate(profile, _job(required_availability=Availability.FULL_TIME))
    assert out.compatible is False


def test_flexible_availability_is_compatible():
    profile = WorkProfile(
        pseudonym_id="P-1", aspiration=Aspiration(availability=Availability.FLEXIBLE)
    )
    out = evaluate(profile, _job(required_availability=Availability.FULL_TIME))
    assert out.compatible is True


def test_missing_language_level_excludes():
    profile = WorkProfile(
        pseudonym_id="P-1",
        languages=[LanguageKnown(language="it", level=LanguageLevel.BASIC)],
    )
    out = evaluate(
        profile,
        _job(required_languages=[RequiredLanguage(language="it", min_level=LanguageLevel.FLUENT)]),
    )
    assert out.compatible is False
    assert any("it" in r.lower() for r in out.reasons)


def test_language_at_or_above_level_is_ok():
    profile = WorkProfile(
        pseudonym_id="P-1",
        languages=[LanguageKnown(language="IT", level=LanguageLevel.NATIVE)],
    )
    out = evaluate(
        profile,
        _job(required_languages=[RequiredLanguage(language="it", min_level=LanguageLevel.FLUENT)]),
    )
    assert out.compatible is True


def test_no_constraints_is_compatible_with_reason():
    out = evaluate(WorkProfile(pseudonym_id="P-1"), _job())
    assert out.compatible is True
    assert out.reasons  # non-empty ("all hard constraints satisfied")
