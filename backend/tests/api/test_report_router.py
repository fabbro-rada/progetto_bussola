import psycopg
import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def test_supervisor_gets_report(client, make_operator):
    user, temp = make_operator("sup1", Role.SUPERVISOR)
    token = _login(client, user, temp)
    r = client.get("/report", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    # §2/§5: aggregate only — no per-person data in the response
    assert "coverage" in body
    assert "pseudonym_id" not in body and "profiles" not in body


@pytest.mark.parametrize("role", [Role.OPERATOR, Role.ADMIN, Role.AUDITOR])
def test_non_supervisor_role_is_forbidden(client, make_operator, role):
    user, temp = make_operator(f"user-{role.value}", role)
    token = _login(client, user, temp)
    r = client.get("/report", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_report_view_is_audited(client, make_operator, app_conn: psycopg.Connection):
    user, temp = make_operator("sup1", Role.SUPERVISOR)
    token = _login(client, user, temp)
    client.get("/report", headers={"Authorization": f"Bearer {token}"})
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, target_pseudonym FROM audit.audit_log "
            "WHERE action = 'report_viewed' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == user
    assert row[1] is None
