import psycopg
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.matching.errors import JobRequestNotFound
from bussola.matching.models import JobRequestCreate
from bussola.matching.requests import JobRequestRepository
from bussola.matching.service import MatchingService
from bussola.profile.enums import (
    Availability,
    EvidenceGrade,
    LanguageLevel,
    SkillKind,
    WorkConstraint,
)
from bussola.profile.models import Aspiration, LanguageKnown, Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


class FakeLlm:
    """Marks a requirement satisfied iff the profile has a skill whose name
    appears in the requirement (case-insensitive) — deterministic, grounded."""

    def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None):
        import json as _json

        user = messages[-1]["content"]
        reqs = _json.loads(user.split("[requirements]\n", 1)[1].split("\n[profile]", 1)[0])
        profile = _json.loads(user.split("[profile]\n", 1)[1])
        names = [s["name"].lower() for s in profile["skills"]]
        verdicts = []
        for r in reqs:
            hit = next((n for n in names if n in r.lower() or r.lower() in n), None)
            verdicts.append({"requirement": r, "satisfied": hit is not None, "evidence": hit})
        return {"verdicts": verdicts}


def _seed_profiles(app_conn: psycopg.Connection) -> None:
    repo = ProfileRepository(app_conn, PiiRedactor())
    repo.save(
        WorkProfile(
            pseudonym_id="P-cook",
            skills=[
                Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
            ],
            languages=[LanguageKnown(language="it", level=LanguageLevel.FLUENT)],
            aspiration=Aspiration(availability=Availability.FULL_TIME),
        )
    )
    repo.save(
        WorkProfile(
            pseudonym_id="P-night",  # excluded by the night-shift hard constraint
            skills=[
                Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
            ],
            aspiration=Aspiration(constraints=[WorkConstraint.NO_NIGHT_SHIFTS]),
        )
    )


def _job(app_conn: psycopg.Connection, **kw) -> int:
    base = dict(title="Cuoco", sector="ristorazione", required_skills=["cucina", "igiene"])
    base.update(kw)
    jr = JobRequestRepository(app_conn).create(JobRequestCreate(**base), created_by="op1")
    app_conn.commit()
    return jr.id


def test_match_ranks_and_reports_gaps(app_conn: psycopg.Connection):
    _seed_profiles(app_conn)
    job_id = _job(app_conn)
    svc = MatchingService(app_conn, FakeLlm(), PiiRedactor())
    results = svc.match(job_id, actor="op1")
    ids = [r.pseudonym_id for r in results]
    assert "P-cook" in ids
    cook = next(r for r in results if r.pseudonym_id == "P-cook")
    assert 0.0 < cook.score <= 1.0
    assert any(g.requirement == "igiene" for g in cook.gaps)  # unmet -> gap


def test_hard_constraint_excludes_candidate(app_conn: psycopg.Connection):
    _seed_profiles(app_conn)
    job_id = _job(app_conn, involves_night_shifts=True)
    svc = MatchingService(app_conn, FakeLlm(), PiiRedactor())
    ids = [r.pseudonym_id for r in svc.match(job_id, actor="op1")]
    assert "P-night" not in ids  # excluded by the deterministic gate


def test_missing_job_raises(app_conn: psycopg.Connection):
    svc = MatchingService(app_conn, FakeLlm(), PiiRedactor())
    with pytest.raises(JobRequestNotFound):
        svc.match(999999, actor="op1")


def test_match_is_audited(app_conn: psycopg.Connection):
    _seed_profiles(app_conn)
    job_id = _job(app_conn)
    from bussola.data.audit import append_audit

    def audit(**kw):
        append_audit(app_conn, commit=False, **kw)

    svc = MatchingService(app_conn, FakeLlm(), PiiRedactor(), audit=audit)
    svc.match(job_id, actor="op1")
    with app_conn.cursor() as cur:
        cur.execute("SELECT action, actor FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        action, actor = cur.fetchone()
    assert action == "matching_run" and actor == "op1"
