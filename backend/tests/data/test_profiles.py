import psycopg
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkExperience, WorkProfile

from .conftest import requires_db

pytestmark = requires_db


@pytest.fixture(scope="session")
def redactor() -> PiiRedactor:
    return PiiRedactor()


def test_create_new_returns_persisted_pseudonym(app_conn: psycopg.Connection, redactor):
    repo = ProfileRepository(app_conn, redactor)
    pid = repo.create_new()
    assert pid.startswith("P-")
    loaded = repo.get(pid)
    assert loaded is not None
    assert loaded.pseudonym_id == pid


def test_save_round_trips(app_conn: psycopg.Connection, redactor):
    repo = ProfileRepository(app_conn, redactor)
    profile = WorkProfile(
        pseudonym_id="P-roundtrip",
        skills=[
            Skill(name="cooking", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
        ],
        experiences=[WorkExperience(role="cook", sector="catering", duration_months=24)],
    )
    repo.save(profile)
    loaded = repo.get("P-roundtrip")
    assert loaded is not None
    assert loaded.skills[0].name == "cooking"
    assert loaded.experiences[0].duration_months == 24


def test_save_redacts_pii_before_persisting(app_conn: psycopg.Connection, redactor):
    repo = ProfileRepository(app_conn, redactor)
    profile = WorkProfile(
        pseudonym_id="P-pii",
        skills=[
            Skill(
                name="contact mario.rossi@example.com",
                kind=SkillKind.SOFT,
                evidence=EvidenceGrade.STATED,
            )
        ],
    )
    repo.save(profile)
    # The raw stored JSONB must not contain the email.
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT profile::text FROM profiles.work_profile WHERE pseudonym_id = %s", ("P-pii",)
        )
        stored = cur.fetchone()[0]
    assert "mario.rossi@example.com" not in stored


def test_get_missing_returns_none(app_conn: psycopg.Connection, redactor):
    repo = ProfileRepository(app_conn, redactor)
    assert repo.get("P-does-not-exist") is None
