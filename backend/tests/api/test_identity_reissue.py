"""Supervisor-only start-code re-issue (§6/§7.3, follow-up A1).

`POST /identity/reissue-start-code` is DEANONYMIZE-gated (supervisor only): it
resolves the matricola to its pseudonym internally and mints a fresh
first-interview start_code, WITHOUT ever returning the pseudonym. It refuses
(409) once the profile has content — a first-interview code must not reopen an
interview that already ran — and 404s an unprovisioned matricola.
"""

from __future__ import annotations

import psycopg
import pytest
from psycopg.types.json import Jsonb

from bussola.auth.rbac import Role
from bussola.data.profiles import create_empty_profile
from bussola.identity.service import IdentityService
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile
from bussola.startcode.service import StartCodeService

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def provisioned(app_conn: psycopg.Connection) -> str:
    pseudonym = create_empty_profile(app_conn)
    IdentityService(app_conn).link(pseudonym, "MAT-777", actor="bootstrap")
    app_conn.commit()
    return pseudonym


def test_supervisor_reissues_a_code_for_an_empty_profile(
    client, make_operator, provisioned: str, app_conn
):
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    tok = _login(client, sup, sup_temp)
    r = client.post(
        "/identity/reissue-start-code", json={"matricola": "MAT-777"}, headers=_auth(tok)
    )
    assert r.status_code == 201
    body = r.json()
    # the pseudonym is NEVER disclosed — only the fresh code
    assert set(body) == {"start_code"}
    assert body["start_code"] != provisioned
    # and it really launches the first interview on the existing pseudonym
    assert StartCodeService(app_conn).consume(body["start_code"]) == provisioned


def test_operator_without_deanonymize_is_403(client, make_operator, provisioned: str):
    op, temp = make_operator("op1", Role.OPERATOR)
    tok = _login(client, op, temp)
    r = client.post(
        "/identity/reissue-start-code", json={"matricola": "MAT-777"}, headers=_auth(tok)
    )
    assert r.status_code == 403


def test_unknown_matricola_is_404(client, make_operator):
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    tok = _login(client, sup, sup_temp)
    r = client.post(
        "/identity/reissue-start-code", json={"matricola": "MAT-nope"}, headers=_auth(tok)
    )
    assert r.status_code == 404


def test_profile_with_content_is_409(client, make_operator, provisioned: str, app_conn):
    # populate the profile -> no longer a fresh provisioning
    profile = WorkProfile(
        pseudonym_id=provisioned,
        skills=[Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
    )
    with app_conn.cursor() as cur:
        cur.execute(
            "UPDATE profiles.work_profile SET profile = %s WHERE pseudonym_id = %s",
            (Jsonb(profile.model_dump(mode="json")), provisioned),
        )
    app_conn.commit()
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    tok = _login(client, sup, sup_temp)
    r = client.post(
        "/identity/reissue-start-code", json={"matricola": "MAT-777"}, headers=_auth(tok)
    )
    assert r.status_code == 409
