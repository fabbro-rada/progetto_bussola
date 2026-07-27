import psycopg
import pytest

from bussola.data.audit import append_audit
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.metrics.service import compute_metrics
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


def _complete(pid: str) -> WorkProfile:
    return WorkProfile(
        pseudonym_id=pid,
        languages=[LanguageKnown(language="it", level=LanguageLevel.FLUENT)],
        skills=[Skill(name="Cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
        experiences=[WorkExperience(role="Aiuto cuoco", sector="Ristorazione", duration_months=12)],
        aspiration=Aspiration(fields_of_interest=["Ristorazione"]),
        desired_training=[DesiredTraining(topic="HACCP")],
    )


def test_zero_profiles_gives_zeroed_metrics(app_conn: psycopg.Connection):
    m = compute_metrics(app_conn)
    assert (m.total_profiles, m.completed_profiles, m.average_completeness) == (0, 0, 0.0)
    assert (m.total_job_requests, m.matching_runs) == (0, 0)


def test_mixed_profiles_counts_and_average(app_conn: psycopg.Connection):
    repo = ProfileRepository(app_conn, PiiRedactor())
    repo.save(_complete("P-C"))
    repo.save(  # 1 sezione-chiave su 5 → 0.2
        WorkProfile(
            pseudonym_id="P-P",
            skills=[Skill(name="X", kind=SkillKind.SOFT, evidence=EvidenceGrade.STATED)],
        )
    )
    m = compute_metrics(app_conn)
    assert m.total_profiles == 2
    assert m.completed_profiles == 1
    assert m.average_completeness == pytest.approx((1.0 + 0.2) / 2)


def test_context_counts(app_conn: psycopg.Connection):
    with app_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO matching.job_request (title, sector, created_by) VALUES (%s, %s, %s)",
            ("Aiuto cuoco", "Ristorazione", "op1"),
        )
    append_audit(app_conn, action="matching_run", actor="op1")
    append_audit(app_conn, action="matching_run", actor="op1")
    m = compute_metrics(app_conn)
    assert m.total_job_requests == 1
    assert m.matching_runs == 2
