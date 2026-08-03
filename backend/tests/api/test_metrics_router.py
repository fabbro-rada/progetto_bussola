import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, LanguageLevel, SkillKind
from bussola.profile.models import (
    Aspiration,
    DesiredTraining,
    LanguageKnown,
    Skill,
    WorkExperience,
    WorkProfile,
)

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def test_supervisor_gets_aggregate_metrics(client, make_operator, app_conn: psycopg.Connection):
    ProfileRepository(app_conn, PiiRedactor()).save(
        WorkProfile(
            pseudonym_id="P-C",
            languages=[LanguageKnown(language="it", level=LanguageLevel.FLUENT)],
            skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
            experiences=[
                WorkExperience(role="Aiuto cuoco", sector="Ristorazione", duration_months=12)
            ],
            aspiration=Aspiration(fields_of_interest=["Ristorazione"]),
            desired_training=[DesiredTraining(topic="HACCP")],
        )
    )
    user, temp = make_operator("sup1", Role.SUPERVISOR)
    token = _login(client, user, temp)
    r = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_profiles"] == 1
    assert body["completed_profiles"] == 1
    assert body["average_completeness"] == 1.0
    # §2/§5: aggregate only — no per-person data in the response
    assert "pseudonym_id" not in body and "profiles" not in body


def test_operator_role_is_forbidden(client, make_operator):
    user, temp = make_operator("op1", Role.OPERATOR)
    token = _login(client, user, temp)
    r = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_metrics_view_is_audited(client, make_operator, app_conn: psycopg.Connection):
    user, temp = make_operator("sup1", Role.SUPERVISOR)
    token = _login(client, user, temp)
    client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, target_pseudonym FROM audit.audit_log "
            "WHERE action = 'metrics_viewed' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == user
    assert row[1] is None
