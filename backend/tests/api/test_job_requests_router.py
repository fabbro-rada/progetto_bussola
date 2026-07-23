import pytest

from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _login(client, make_operator, role):
    user, temp = make_operator(f"{role.value}1", role)
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def test_operator_creates_and_lists_job_requests(client, make_operator):
    token = _login(client, make_operator, Role.OPERATOR)
    r = client.post(
        "/job-requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Cuoco", "sector": "ristorazione", "required_skills": ["cucina"]},
    )
    assert r.status_code == 201 and r.json()["id"] > 0
    lst = client.get("/job-requests", headers={"Authorization": f"Bearer {token}"})
    assert lst.status_code == 200 and len(lst.json()) == 1


def test_non_operator_forbidden(client, make_operator):
    token = _login(client, make_operator, Role.AUDITOR)
    r = client.post(
        "/job-requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "X", "sector": "Y"},
    )
    assert r.status_code == 403
