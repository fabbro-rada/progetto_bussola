import psycopg
import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_provision_followup_requires_operator(client, make_operator):
    sup, sup_temp = make_operator("sup1", Role.SUPERVISOR)
    sup_tok = _login(client, sup, sup_temp)
    r = client.post("/followups", json={"pseudonym_id": "P-x"}, headers=_auth(sup_tok))
    assert r.status_code == 403

    aud, aud_temp = make_operator("aud1", Role.AUDITOR)
    aud_tok = _login(client, aud, aud_temp)
    r = client.post("/followups", json={"pseudonym_id": "P-x"}, headers=_auth(aud_tok))
    assert r.status_code == 403

    op, op_temp = make_operator("op1", Role.OPERATOR)
    op_tok = _login(client, op, op_temp)
    r = client.post("/followups", json={"pseudonym_id": "P-x"}, headers=_auth(op_tok))
    assert r.status_code == 201
    assert r.json()["token"]


def test_provision_is_audited(client, make_operator, app_conn: psycopg.Connection):
    op, op_temp = make_operator("op1", Role.OPERATOR)
    op_tok = _login(client, op, op_temp)
    r = client.post("/followups", json={"pseudonym_id": "P-x"}, headers=_auth(op_tok))
    assert r.status_code == 201

    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, target_pseudonym FROM audit.audit_log "
            "WHERE action = 'followup_provisioned' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == op
    assert row[1] == "P-x"

    with app_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM followup.followup_token")
        assert cur.fetchone()[0] == 1
