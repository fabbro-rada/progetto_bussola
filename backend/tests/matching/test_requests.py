import psycopg
import pytest

from bussola.matching.models import JobRequestCreate, RequiredLanguage
from bussola.matching.requests import JobRequestRepository
from bussola.profile.enums import Availability, LanguageLevel

pytestmark = pytest.mark.usefixtures("db")


def _sample() -> JobRequestCreate:
    return JobRequestCreate(
        title="Cuoco",
        sector="ristorazione",
        description="mensa",
        required_skills=["cucina", "igiene alimentare"],
        required_languages=[RequiredLanguage(language="it", min_level=LanguageLevel.INTERMEDIATE)],
        required_availability=Availability.FULL_TIME,
        involves_night_shifts=False,
        training_prerequisites=["sicurezza alimentare"],
    )


def test_create_and_get(app_conn: psycopg.Connection):
    repo = JobRequestRepository(app_conn)
    jr = repo.create(_sample(), created_by="op1")
    app_conn.commit()
    assert jr.id > 0 and jr.created_by == "op1"
    got = repo.get(jr.id)
    assert got is not None
    assert got.required_skills == ["cucina", "igiene alimentare"]
    assert got.required_languages[0].language == "it"
    assert got.required_availability is Availability.FULL_TIME


def test_get_missing_returns_none(app_conn: psycopg.Connection):
    assert JobRequestRepository(app_conn).get(999999) is None


def test_list_all(app_conn: psycopg.Connection):
    repo = JobRequestRepository(app_conn)
    repo.create(_sample(), created_by="op1")
    repo.create(_sample(), created_by="op1")
    app_conn.commit()
    assert len(repo.list_all()) == 2
