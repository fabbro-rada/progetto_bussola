import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_operator_creates_and_lists_own_pending_request(client, make_operator):
    user, temp = make_operator("op1", Role.OPERATOR)
    tok = _login(client, user, temp)
    r = client.post("/exports", json={"filters": {"skill_query": "cucina"}, "reason": "Azienda X"}, headers=_auth(tok))
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    lst = client.get("/exports", headers=_auth(tok))
    assert [x["id"] for x in lst.json()] == [r.json()["id"]]


def test_operator_cannot_approve_or_see_pending(client, make_operator):
    user, temp = make_operator("op1", Role.OPERATOR)
    tok = _login(client, user, temp)
    assert client.get("/exports/pending", headers=_auth(tok)).status_code == 403
    assert client.post("/exports/1/approve", headers=_auth(tok)).status_code == 403


def test_supervisor_cannot_create_or_download(client, make_operator):
    sup, temp = make_operator("sup1", Role.SUPERVISOR)
    tok = _login(client, sup, temp)
    assert client.post("/exports", json={"filters": {}, "reason": "r"}, headers=_auth(tok)).status_code == 403
    assert client.get("/exports/1/download", headers=_auth(tok)).status_code == 403


def test_full_flow_request_approve_download(client, make_operator, app_conn: psycopg.Connection):
    ProfileRepository(app_conn, PiiRedactor()).save(
        WorkProfile(pseudonym_id="P-1", skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)])
    )
    op, otemp = make_operator("op1", Role.OPERATOR)
    sup, stemp = make_operator("sup1", Role.SUPERVISOR)
    otok = _login(client, op, otemp)
    stok = _login(client, sup, stemp)
    rid = client.post("/exports", json={"filters": {"skill_query": "cucina"}, "reason": "Azienda X"}, headers=_auth(otok)).json()["id"]
    # not approved yet → 409
    assert client.get(f"/exports/{rid}/download", headers=_auth(otok)).status_code == 409
    # supervisor sees it pending and approves
    assert rid in [x["id"] for x in client.get("/exports/pending", headers=_auth(stok)).json()]
    assert client.post(f"/exports/{rid}/approve", headers=_auth(stok)).status_code == 204
    # operator downloads → work-only profiles
    dl = client.get(f"/exports/{rid}/download", headers=_auth(otok))
    assert dl.status_code == 200
    body = dl.json()
    assert [p["pseudonym_id"] for p in body] == ["P-1"]
    assert all(set(p) <= set(WorkProfile.model_fields) for p in body)  # WorkProfile-only


def test_download_of_other_operators_request_is_404(client, make_operator):
    op1, t1 = make_operator("op1", Role.OPERATOR)
    op2, t2 = make_operator("op2", Role.OPERATOR)
    sup, st = make_operator("sup1", Role.SUPERVISOR)
    tok1, tok2, stok = _login(client, op1, t1), _login(client, op2, t2), _login(client, sup, st)
    rid = client.post("/exports", json={"filters": {}, "reason": "r"}, headers=_auth(tok1)).json()["id"]
    client.post(f"/exports/{rid}/approve", headers=_auth(stok))
    assert client.get(f"/exports/{rid}/download", headers=_auth(tok2)).status_code == 404


def test_approve_twice_conflicts(client, make_operator):
    op, ot = make_operator("op1", Role.OPERATOR)
    sup, st = make_operator("sup1", Role.SUPERVISOR)
    otok, stok = _login(client, op, ot), _login(client, sup, st)
    rid = client.post("/exports", json={"filters": {}, "reason": "r"}, headers=_auth(otok)).json()["id"]
    assert client.post(f"/exports/{rid}/approve", headers=_auth(stok)).status_code == 204
    assert client.post(f"/exports/{rid}/approve", headers=_auth(stok)).status_code == 409
    assert client.post("/exports/999/approve", headers=_auth(stok)).status_code == 404
