"""Operator provisioning endpoint (§6/§7.2, Task 6): matricola -> start_code.

The response must NEVER contain the pseudonym (only the operator's own audit
trail and the segregated identity register know it). Mirrors
`test_followups_router.py`'s auth harness and atomic-audit assertions.
"""

from __future__ import annotations

import psycopg
import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_provision_requires_operator(client, make_operator):
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    sup_tok = _login(client, sup, sup_temp)
    r = client.post("/interviews/provision", json={"matricola": "MAT-100"}, headers=_auth(sup_tok))
    assert r.status_code == 403

    aud, aud_temp = make_operator("aud1", Role.AUDITOR)
    aud_tok = _login(client, aud, aud_temp)
    r = client.post("/interviews/provision", json={"matricola": "MAT-100"}, headers=_auth(aud_tok))
    assert r.status_code == 403


def test_provision_returns_start_code_and_never_the_pseudonym(client, make_operator):
    op, op_temp = make_operator("op1", Role.OPERATOR)
    op_tok = _login(client, op, op_temp)
    r = client.post("/interviews/provision", json={"matricola": "MAT-100"}, headers=_auth(op_tok))
    assert r.status_code == 201
    body = r.json()
    assert body["start_code"]
    assert "pseudonym" not in str(body).lower()


def test_duplicate_matricola_returns_409(client, make_operator):
    op, op_temp = make_operator("op1", Role.OPERATOR)
    op_tok = _login(client, op, op_temp)
    client.post("/interviews/provision", json={"matricola": "MAT-DUP"}, headers=_auth(op_tok))
    r = client.post("/interviews/provision", json={"matricola": "MAT-DUP"}, headers=_auth(op_tok))
    assert r.status_code == 409


def test_provision_is_audited(client, make_operator, owner_conn: psycopg.Connection):
    # Use an INDEPENDENT connection (not the `app_conn` the handler writes
    # through) so this assertion is genuinely commit-sensitive — see the
    # identical rationale in `test_followups_router.py::test_provision_is_audited`.
    op, op_temp = make_operator("op1", Role.OPERATOR)
    op_tok = _login(client, op, op_temp)
    r = client.post("/interviews/provision", json={"matricola": "MAT-AUD"}, headers=_auth(op_tok))
    assert r.status_code == 201

    with owner_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, target_pseudonym FROM audit.audit_log "
            "WHERE action = 'identity_link_created' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == op

    with owner_conn.cursor() as cur:
        cur.execute(
            "SELECT matricola FROM identity.pseudonym_identity WHERE pseudonym_id = %s",
            (row[1],),
        )
        matricola_row = cur.fetchone()
    assert matricola_row is not None
    assert matricola_row[0] == "MAT-AUD"

    with owner_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM startcode.start_code")
        assert cur.fetchone()[0] == 1
    owner_conn.rollback()
