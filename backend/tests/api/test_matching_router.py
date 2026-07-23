import pytest

from bussola.auth.rbac import Role
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def test_match_endpoint_returns_results(client, make_operator, app_conn, monkeypatch):
    # stub the LLM client the router builds, so the test is deterministic
    from bussola.api.routers import matching as matching_router

    class FakeLlm:
        def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None):
            return {
                "verdicts": [{"requirement": "cucina", "satisfied": True, "evidence": "Cucina"}]
            }

    monkeypatch.setattr(matching_router, "HttpxLlmClient", lambda: FakeLlm())

    ProfileRepository(app_conn, PiiRedactor()).save(
        WorkProfile(
            pseudonym_id="P-1",
            skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
        )
    )
    user, temp = make_operator("op1", Role.OPERATOR)
    token = client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]
    created = client.post(
        "/job-requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Cuoco", "sector": "ristorazione", "required_skills": ["cucina"]},
    ).json()
    r = client.post(
        f"/job-requests/{created['id']}/match", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json()[0]["pseudonym_id"] == "P-1"
    assert r.json()[0]["requirements"][0]["satisfied"] is True


def test_match_endpoint_returns_503_when_llm_unavailable(
    client, make_operator, app_conn, monkeypatch
):
    # graceful degradation (§3): LLM down must surface as 503, not 500, with no
    # internal detail leaked.
    from bussola.api.routers import matching as matching_router
    from bussola.llm.client import LlmUnavailable

    class DownLlm:
        def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None):
            raise LlmUnavailable("llama-server unreachable")

    monkeypatch.setattr(matching_router, "HttpxLlmClient", lambda: DownLlm())

    ProfileRepository(app_conn, PiiRedactor()).save(
        WorkProfile(
            pseudonym_id="P-1",
            skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
        )
    )
    user, temp = make_operator("op1", Role.OPERATOR)
    token = client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]
    created = client.post(
        "/job-requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Cuoco", "sector": "ristorazione", "required_skills": ["cucina"]},
    ).json()
    r = client.post(
        f"/job-requests/{created['id']}/match", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 503
    assert "llama-server" not in r.text
    assert r.json() == {"detail": "servizio di matching temporaneamente non disponibile"}
