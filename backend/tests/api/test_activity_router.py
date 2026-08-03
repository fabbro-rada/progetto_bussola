import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.audit import append_audit

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def test_supervisor_gets_operator_activity(client, make_operator, app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1", target_pseudonym="P-1")
    user, temp = make_operator("sup1", Role.SUPERVISOR)
    token = _login(client, user, temp)
    r = client.get("/operator-activity", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert any(row["actor"] == "op1" and row["profiles_viewed"] == 1 for row in body)
    # aggregate only — no per-person data
    assert all("pseudonym_id" not in row for row in body)


def test_operator_and_auditor_are_forbidden(client, make_operator):
    for name, role in [("op1", Role.OPERATOR), ("aud1", Role.AUDITOR)]:
        user, temp = make_operator(name, role)
        token = _login(client, user, temp)
        assert (
            client.get(
                "/operator-activity", headers={"Authorization": f"Bearer {token}"}
            ).status_code
            == 403
        )


def test_view_is_audited(client, make_operator, app_conn: psycopg.Connection):
    user, temp = make_operator("sup1", Role.SUPERVISOR)
    token = _login(client, user, temp)
    client.get("/operator-activity", headers={"Authorization": f"Bearer {token}"})
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor FROM audit.audit_log WHERE action = 'operator_activity_viewed' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None and row[0] == user
