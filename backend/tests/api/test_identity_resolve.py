"""Supervisor-only, audited de-anonymization (§6/§7.3, Task 7).

`Permission.DEANONYMIZE` is granted ONLY to `Role.SUPERVISOR` — operator,
admin and auditor must all get 403 on both directions. Every successful
resolution audits `identity_resolved` (mirrors the atomic-audit assertions
in `test_interviews_provision.py`/`test_followups_router.py`), but the
read-back here must use `owner_conn`, not `auditor_conn`: `bussola_auditor`
has no grant on schema `identity` at all (§6), so this suite never even
opens an auditor connection against it.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.profiles import create_empty_profile
from bussola.identity.service import IdentityService

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass(frozen=True)
class Provisioned:
    pseudonym: str
    matricola: str


@pytest.fixture
def provisioned(app_conn: psycopg.Connection) -> Provisioned:
    pseudonym = create_empty_profile(app_conn)
    IdentityService(app_conn).link(pseudonym, "MAT-777", actor="bootstrap")
    app_conn.commit()
    return Provisioned(pseudonym=pseudonym, matricola="MAT-777")


def test_supervisor_resolves_pseudonym_to_matricola(client, make_operator, provisioned: Provisioned):
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    sup_tok = _login(client, sup, sup_temp)
    r = client.post(
        "/identity/resolve",
        json={"pseudonym_ids": [provisioned.pseudonym]},
        headers=_auth(sup_tok),
    )
    assert r.status_code == 200
    assert r.json()["results"] == [
        {"pseudonym_id": provisioned.pseudonym, "matricola": provisioned.matricola}
    ]


def test_unknown_pseudonym_is_omitted_from_results(client, make_operator, provisioned: Provisioned):
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    sup_tok = _login(client, sup, sup_temp)
    r = client.post(
        "/identity/resolve",
        json={"pseudonym_ids": [provisioned.pseudonym, "P-nope"]},
        headers=_auth(sup_tok),
    )
    assert r.status_code == 200
    assert r.json()["results"] == [
        {"pseudonym_id": provisioned.pseudonym, "matricola": provisioned.matricola}
    ]


def test_operator_admin_and_auditor_cannot_resolve(client, make_operator):
    op, op_temp = make_operator("op1", Role.OPERATOR)
    op_tok = _login(client, op, op_temp)
    assert client.post(
        "/identity/resolve", json={"pseudonym_ids": ["P-x"]}, headers=_auth(op_tok)
    ).status_code == 403
    assert client.post(
        "/identity/resolve-matricola", json={"matricola": "MAT-x"}, headers=_auth(op_tok)
    ).status_code == 403

    admin, admin_temp = make_operator("admin1", Role.ADMIN)
    admin_tok = _login(client, admin, admin_temp)
    assert client.post(
        "/identity/resolve", json={"pseudonym_ids": ["P-x"]}, headers=_auth(admin_tok)
    ).status_code == 403
    assert client.post(
        "/identity/resolve-matricola", json={"matricola": "MAT-x"}, headers=_auth(admin_tok)
    ).status_code == 403

    aud, aud_temp = make_operator("aud1", Role.AUDITOR)
    aud_tok = _login(client, aud, aud_temp)
    assert client.post(
        "/identity/resolve", json={"pseudonym_ids": ["P-x"]}, headers=_auth(aud_tok)
    ).status_code == 403
    assert client.post(
        "/identity/resolve-matricola", json={"matricola": "MAT-x"}, headers=_auth(aud_tok)
    ).status_code == 403


def test_resolve_matricola_reverse_and_404(client, make_operator, provisioned: Provisioned):
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    sup_tok = _login(client, sup, sup_temp)
    r = client.post(
        "/identity/resolve-matricola",
        json={"matricola": provisioned.matricola},
        headers=_auth(sup_tok),
    )
    assert r.status_code == 200
    assert r.json()["pseudonym_id"] == provisioned.pseudonym

    r404 = client.post(
        "/identity/resolve-matricola", json={"matricola": "MAT-nope"}, headers=_auth(sup_tok)
    )
    assert r404.status_code == 404


def test_resolution_is_audited(
    client, make_operator, provisioned: Provisioned, owner_conn: psycopg.Connection
):
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    sup_tok = _login(client, sup, sup_temp)
    r = client.post(
        "/identity/resolve",
        json={"pseudonym_ids": [provisioned.pseudonym]},
        headers=_auth(sup_tok),
    )
    assert r.status_code == 200

    with owner_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, target_pseudonym FROM audit.audit_log "
            "WHERE action = 'identity_resolved' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == sup
    assert row[1] == provisioned.pseudonym
    owner_conn.rollback()


def test_unknown_pseudonym_is_not_audited(client, make_operator, owner_conn: psycopg.Connection):
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    sup_tok = _login(client, sup, sup_temp)
    r = client.post(
        "/identity/resolve", json={"pseudonym_ids": ["P-nope"]}, headers=_auth(sup_tok)
    )
    assert r.status_code == 200
    assert r.json()["results"] == []

    with owner_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log WHERE action = 'identity_resolved'")
        assert cur.fetchone()[0] == 0
    owner_conn.rollback()
