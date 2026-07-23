import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def test_operator_searches_profiles(client, make_operator, app_conn: psycopg.Connection):
    ProfileRepository(app_conn, PiiRedactor()).save(
        WorkProfile(
            pseudonym_id="P-1",
            skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
        )
    )
    user, temp = make_operator("op1", Role.OPERATOR)
    token = client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]
    r = client.get("/profiles?skill_query=cucina", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert [p["pseudonym_id"] for p in r.json()] == ["P-1"]
