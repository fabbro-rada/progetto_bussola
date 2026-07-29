"""Authorized CSV/JSON export of the aggregate/anonymous report (S28 Task 6),
reusing the S16 approval workflow via `export_request.kind`.

Retro-compatibility (binding, §CLAUDE.md governance / plan Task 6): the
`kind='profiles'` flow must round-trip exactly as before the `kind` column
was surfaced end-to-end. That scenario is asserted FIRST, before any
`kind='report'` test — if it ever forced a change to an S16 assertion,
that would mean this feature isn't retro-compatible.
"""

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


@pytest.fixture
def client_as(client, make_operator):
    """`client_as("operator")` / `client_as("supervisor")` -> a thin wrapper
    around the shared `client` TestClient that injects that role's bearer
    token into every request. One operator and one supervisor are created
    lazily (on first use) and reused for the rest of the test."""

    tokens: dict[str, str] = {}

    class _RoleClient:
        def __init__(self, token: str) -> None:
            self._token = token

        def get(self, url: str, **kwargs):
            headers = {**_auth(self._token), **kwargs.pop("headers", {})}
            return client.get(url, headers=headers, **kwargs)

        def post(self, url: str, **kwargs):
            headers = {**_auth(self._token), **kwargs.pop("headers", {})}
            return client.post(url, headers=headers, **kwargs)

    def _for(role_name: str) -> _RoleClient:
        if role_name not in tokens:
            username, temp = make_operator(f"{role_name}-actor", Role(role_name))
            tokens[role_name] = _login(client, username, temp)
        return _RoleClient(tokens[role_name])

    return _for


# --- Step 1: retro-compatibility FIRST ------------------------------------


def test_profiles_export_round_trip_is_unchanged(client_as, app_conn: psycopg.Connection):
    """The pre-existing S16 profile-export flow (create -> pending
    kind='profiles' -> approve -> download = list[WorkProfile]) must still
    work exactly as before, now that `create_request`/`ExportRequest`
    carry a `kind` field defaulting to 'profiles'."""
    ProfileRepository(app_conn, PiiRedactor()).save(
        WorkProfile(
            pseudonym_id="P-1",
            skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
        )
    )
    created = client_as("operator").post(
        "/exports", json={"filters": {"skill_query": "cucina"}, "reason": "Azienda X"}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "pending"
    assert body["kind"] == "profiles"
    rid = body["id"]

    assert client_as("supervisor").post(f"/exports/{rid}/approve").status_code == 204

    dl = client_as("operator").get(f"/exports/{rid}/download")
    assert dl.status_code == 200
    profiles = dl.json()
    assert [p["pseudonym_id"] for p in profiles] == ["P-1"]
    assert all(set(p) <= set(WorkProfile.model_fields) for p in profiles)


# --- Step 2: the report path ------------------------------------------------


def test_report_export_end_to_end(client_as):
    rid = client_as("supervisor").post("/report/export").json()["id"]
    assert client_as("operator").post("/report/export").status_code == 403  # only VIEW_METRICS
    assert client_as("supervisor").post(f"/exports/{rid}/approve").status_code == 204

    j = client_as("supervisor").get(f"/exports/{rid}/download?format=json")
    assert j.status_code == 200
    assert "coverage" in j.json()

    c = client_as("supervisor").get(f"/exports/{rid}/download?format=csv")
    assert c.status_code == 200
    assert "text/csv" in c.headers["content-type"]
    assert "section,key,value" in c.text


def test_report_export_created_with_kind_report(client_as):
    body = client_as("supervisor").post("/report/export").json()
    assert body["kind"] == "report"
    assert body["status"] == "pending"


def test_report_download_gated_until_approved(client_as):
    rid = client_as("supervisor").post("/report/export").json()["id"]
    assert client_as("supervisor").get(f"/exports/{rid}/download").status_code == 409  # pending


def test_report_download_by_non_owner_supervisor_is_not_found(client, client_as, make_operator):
    rid = client_as("supervisor").post("/report/export").json()["id"]
    client_as("supervisor").post(f"/exports/{rid}/approve")
    user2, temp2 = make_operator("sup2", Role.SUPERVISOR)
    token2 = _login(client, user2, temp2)
    assert client.get(f"/exports/{rid}/download", headers=_auth(token2)).status_code == 404


def test_operator_cannot_download_report_even_with_export_data(client_as):
    rid = client_as("supervisor").post("/report/export").json()["id"]
    client_as("supervisor").post(f"/exports/{rid}/approve")
    # the operator holds EXPORT_DATA but not APPROVE_EXPORTS: report
    # downloads require the latter, so this stays 403 (never EXPORT_DATA
    # for report-kind requests).
    assert client_as("operator").get(f"/exports/{rid}/download").status_code == 403
