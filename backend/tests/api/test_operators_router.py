import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password}).json()[
        "token"
    ]


def test_admin_creates_operator(client, make_operator):
    admin_user, admin_temp = make_operator("admin1", Role.ADMIN)
    admin_token = _login(client, admin_user, admin_temp)
    r = client.post(
        "/operators",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "newbie", "display_name": "New Bie", "role": "operator"},
    )
    assert r.status_code == 201
    assert r.json()["operator"]["username"] == "newbie"
    assert r.json()["temp_password"]


def test_non_admin_cannot_manage_operators(client, make_operator):
    op_user, op_temp = make_operator("plainop", Role.OPERATOR)
    token = _login(client, op_user, op_temp)
    r = client.post(
        "/operators",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "x", "display_name": "X", "role": "operator"},
    )
    assert r.status_code == 403


def test_disable_kills_target_sessions(client, make_operator):
    admin_user, admin_temp = make_operator("admin2", Role.ADMIN)
    admin_token = _login(client, admin_user, admin_temp)
    created = client.post(
        "/operators",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "victim", "display_name": "V", "role": "operator"},
    ).json()
    victim_token = _login(client, "victim", created["temp_password"])
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {victim_token}"}).status_code
        == 200
    )
    oid = created["operator"]["id"]
    client.post(f"/operators/{oid}/disable", headers={"Authorization": f"Bearer {admin_token}"})
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {victim_token}"}).status_code
        == 401
    )
