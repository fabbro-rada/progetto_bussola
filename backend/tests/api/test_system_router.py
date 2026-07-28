import psycopg
import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def test_admin_gets_system_config(client, make_operator):
    user, temp = make_operator("adm1", Role.ADMIN)
    token = _login(client, user, temp)
    r = client.get("/system-config", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["llm_model"]  # non-empty
    assert body["languages"] == ["it", "en", "fr", "es", "ar"]
    assert body["tts_voices"]["ar"] is False
    # no secret leaked
    assert not any(k in body for k in ("db_password", "password", "token", "dsn"))


def test_non_admin_roles_are_forbidden(client, make_operator):
    for name, role in [("op1", Role.OPERATOR), ("sup1", Role.SUPERVISOR), ("aud1", Role.AUDITOR)]:
        user, temp = make_operator(name, role)
        token = _login(client, user, temp)
        assert client.get("/system-config", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_view_is_audited(client, make_operator, app_conn: psycopg.Connection):
    user, temp = make_operator("adm1", Role.ADMIN)
    token = _login(client, user, temp)
    client.get("/system-config", headers={"Authorization": f"Bearer {token}"})
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor FROM audit.audit_log WHERE action = 'system_config_viewed' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None and row[0] == user
