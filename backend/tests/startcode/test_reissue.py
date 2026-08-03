from __future__ import annotations

import psycopg
import pytest
from psycopg.types.json import Jsonb

from bussola.data.profiles import create_empty_profile
from bussola.identity.service import IdentityService
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile
from bussola.startcode.errors import InterviewAlreadyStarted, MatricolaNotProvisioned
from bussola.startcode.reissue import reissue_start_code
from bussola.startcode.service import StartCodeService

pytestmark = pytest.mark.usefixtures("db")


def _provision(conn: psycopg.Connection, matricola: str) -> str:
    pseudonym = create_empty_profile(conn)
    IdentityService(conn).link(pseudonym, matricola, actor="op")
    conn.commit()
    return pseudonym


def _give_content(conn: psycopg.Connection, pseudonym: str) -> None:
    profile = WorkProfile(
        pseudonym_id=pseudonym,
        skills=[Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
    )
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE profiles.work_profile SET profile = %s WHERE pseudonym_id = %s",
            (Jsonb(profile.model_dump(mode="json")), pseudonym),
        )
    conn.commit()


def test_reissue_for_empty_profile_returns_a_consumable_code(app_conn: psycopg.Connection):
    pseudonym = _provision(app_conn, "MAT-1")
    events: list[dict] = []
    code = reissue_start_code(app_conn, "MAT-1", actor="sup", audit=lambda **kw: events.append(kw))
    app_conn.commit()
    # the fresh code launches the FIRST interview on the SAME existing pseudonym
    assert StartCodeService(app_conn).consume(code) == pseudonym
    # §7.3: the de-anon resolution AND the re-issue are both audited, on the pseudonym
    assert [e["action"] for e in events] == ["identity_resolved", "start_code_reissued"]
    assert all(e["target_pseudonym"] == pseudonym for e in events)


def test_reissue_unknown_matricola_raises(app_conn: psycopg.Connection):
    with pytest.raises(MatricolaNotProvisioned):
        reissue_start_code(app_conn, "MAT-nope", actor="sup")


def test_reissue_refuses_when_profile_has_content(app_conn: psycopg.Connection):
    pseudonym = _provision(app_conn, "MAT-2")
    _give_content(app_conn, pseudonym)
    with pytest.raises(InterviewAlreadyStarted):
        reissue_start_code(app_conn, "MAT-2", actor="sup")
    # nothing minted for this pseudonym (fail-closed, no overwrite path opened)
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM startcode.start_code WHERE pseudonym_id = %s", (pseudonym,)
        )
        assert cur.fetchone()[0] == 0
