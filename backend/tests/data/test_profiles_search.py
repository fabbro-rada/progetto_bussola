import psycopg
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import (
    Availability,
    EvidenceGrade,
    LanguageLevel,
    OperationalNoteCategory,
    SkillKind,
)
from bussola.profile.models import Aspiration, LanguageKnown, Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


@pytest.fixture
def repo(app_conn: psycopg.Connection) -> ProfileRepository:
    return ProfileRepository(app_conn, PiiRedactor())


def _seed(repo: ProfileRepository) -> None:
    repo.save(
        WorkProfile(
            pseudonym_id="P-cook",
            skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
            languages=[LanguageKnown(language="it", level=LanguageLevel.FLUENT)],
            aspiration=Aspiration(availability=Availability.FULL_TIME),
            operational_notes=[OperationalNoteCategory.PREFERS_TEAM_WORK],
        )
    )
    repo.save(
        WorkProfile(
            pseudonym_id="P-clerk",
            skills=[
                Skill(name="Data entry", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)
            ],
            aspiration=Aspiration(availability=Availability.PART_TIME),
        )
    )


def test_list_all(repo: ProfileRepository):
    _seed(repo)
    assert {p.pseudonym_id for p in repo.list_all()} == {"P-cook", "P-clerk"}


def test_search_by_availability(repo: ProfileRepository):
    _seed(repo)
    got = repo.search(availability=Availability.FULL_TIME)
    assert [p.pseudonym_id for p in got] == ["P-cook"]


def test_search_by_skill_query_case_insensitive(repo: ProfileRepository):
    _seed(repo)
    got = repo.search(skill_query="cucina")
    assert [p.pseudonym_id for p in got] == ["P-cook"]


def test_search_by_note(repo: ProfileRepository):
    _seed(repo)
    got = repo.search(note=OperationalNoteCategory.PREFERS_TEAM_WORK)
    assert [p.pseudonym_id for p in got] == ["P-cook"]
