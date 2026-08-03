"""Aggregate persistence of matching outcomes (§5): counts + gap frequencies
per run, never a pseudonym or a per-person row. Mirrors the DB-backed setup
in test_service.py (FakeLlm, app_conn, audit via append_audit)."""

from __future__ import annotations

import psycopg
import pytest

from bussola.data.audit import append_audit
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.matching.match_runs import record_match_run
from bussola.matching.models import JobRequestCreate
from bussola.matching.requests import JobRequestRepository
from bussola.matching.service import MatchingService
from bussola.profile.enums import Availability, EvidenceGrade, SkillKind
from bussola.profile.models import Aspiration, Skill, WorkProfile

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


def test_record_match_run_persists_aggregate_without_pseudonym(app_conn: psycopg.Connection):
    record_match_run(
        app_conn,
        job_request_id=1,
        evaluated_count=7,
        compatible_count=3,
        gaps={"HACCP": 2, "muletto": 1},
    )
    app_conn.commit()
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT evaluated_count, compatible_count, gaps FROM matching.match_run "
            "ORDER BY id DESC LIMIT 1"
        )
        ev, comp, gaps = cur.fetchone()
        assert (ev, comp) == (7, 3)
        assert gaps == {"HACCP": 2, "muletto": 1}
        # no per-person column exists at all:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='matching' AND table_name='match_run'"
        )
        cols = {r[0] for r in cur.fetchall()}
        assert "pseudonym_id" not in cols and "pseudonym" not in cols


def test_match_return_value_unchanged_and_aggregate_row_recorded(app_conn: psycopg.Connection):
    repo = ProfileRepository(app_conn, PiiRedactor())
    repo.save(
        WorkProfile(
            pseudonym_id="P-cook",
            skills=[
                Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
            ],
            aspiration=Aspiration(availability=Availability.FULL_TIME),
        )
    )
    job = JobRequestRepository(app_conn).create(
        JobRequestCreate(
            title="Cuoco", sector="ristorazione", required_skills=["cucina", "igiene"]
        ),
        created_by="op1",
    )
    app_conn.commit()

    def audit(**kw):
        append_audit(app_conn, commit=False, **kw)

    svc = MatchingService(app_conn, FakeLlm(), PiiRedactor(), audit=audit)
    results = svc.match(job.id, actor="op1")

    # (a) match()'s return value is unchanged: still a list[MatchResult] with
    # the same content it always had.
    assert isinstance(results, list)
    assert [r.pseudonym_id for r in results] == ["P-cook"]
    cook = results[0]
    assert any(g.requirement == "igiene" for g in cook.gaps)

    # (b) an aggregate match_run row now exists, consistent with the results
    # just returned — with no per-person data (§5).
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT job_request_id, evaluated_count, compatible_count, gaps "
            "FROM matching.match_run ORDER BY id DESC LIMIT 1"
        )
        job_request_id, evaluated_count, compatible_count, gaps = cur.fetchone()
    assert job_request_id == job.id
    assert evaluated_count == 1  # one profile was seeded/evaluated
    assert compatible_count == len(results)
    assert gaps == {"formazione in igiene": 1}
