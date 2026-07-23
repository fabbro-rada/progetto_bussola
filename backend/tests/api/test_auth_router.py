import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def test_login_me_logout_flow(client, make_operator):
    username, temp = make_operator("alice", Role.OPERATOR)
    r = client.post("/auth/login", json={"username": username, "password": temp})
    assert r.status_code == 200
    token = r.json()["token"]
    assert r.json()["must_change_password"] is True

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["username"] == "alice"

    out = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert out.status_code == 204
    # session now dead
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_login_wrong_password_is_401_generic(client, make_operator):
    make_operator("bob")
    r = client.post("/auth/login", json={"username": "bob", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "credenziali non valide"


def test_change_password_then_login_with_new(client, make_operator):
    username, temp = make_operator("carl")
    token = client.post("/auth/login", json={"username": username, "password": temp}).json()[
        "token"
    ]
    r = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": temp, "new_password": "a-brand-new-pw"},
    )
    assert r.status_code == 204
    assert (
        client.post(
            "/auth/login", json={"username": username, "password": "a-brand-new-pw"}
        ).status_code
        == 200
    )
