import psycopg
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.export.errors import ExportNotApproved, ExportNotFound, ExportNotPending
from bussola.export.models import ExportFilters
from bussola.export.service import ExportService
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def _seed_profile(conn: psycopg.Connection, pid: str, skill: str) -> None:
    ProfileRepository(conn, PiiRedactor()).save(
        WorkProfile(
            pseudonym_id=pid,
            skills=[Skill(name=skill, kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)],
        )
    )


def test_create_starts_pending_and_lists_for_owner(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(skill_query="cucina"), reason="Azienda X")
    assert req.status == "pending"
    assert req.requested_by == "op1"
    assert svc.list_own(actor="op1")[0].id == req.id
    assert svc.list_own(actor="op2") == []  # not visible to another operator


def test_approve_then_download_returns_matching_work_profiles(app_conn: psycopg.Connection):
    _seed_profile(app_conn, "P-1", "Cucina")
    _seed_profile(app_conn, "P-2", "Muratura")
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(skill_query="cucina"), reason="Azienda X")
    svc.approve(actor="sup1", request_id=req.id)
    payload = svc.generate_payload(actor="op1", request_id=req.id)
    assert [p.pseudonym_id for p in payload] == ["P-1"]
    # payload is WorkProfile-only (no extra/PII fields) by construction
    assert all(isinstance(p, WorkProfile) for p in payload)


def test_download_before_approval_is_blocked(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(), reason="r")
    with pytest.raises(ExportNotApproved):
        svc.generate_payload(actor="op1", request_id=req.id)


def test_download_of_another_operators_request_is_not_found(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(), reason="r")
    svc.approve(actor="sup1", request_id=req.id)
    with pytest.raises(ExportNotFound):
        svc.generate_payload(actor="op2", request_id=req.id)


def test_deciding_twice_conflicts(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(), reason="r")
    svc.approve(actor="sup1", request_id=req.id)
    with pytest.raises(ExportNotPending):
        svc.deny(actor="sup1", request_id=req.id, reason="late")


def test_approve_missing_request_is_not_found(app_conn: psycopg.Connection):
    with pytest.raises(ExportNotFound):
        ExportService(app_conn).approve(actor="sup1", request_id=999)


def test_deny_records_reason_and_blocks_download(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(), reason="r")
    svc.deny(actor="sup1", request_id=req.id, reason="fuori scopo")
    own = svc.list_own(actor="op1")[0]
    assert own.status == "denied"
    assert own.decision_reason == "fuori scopo"
    with pytest.raises(ExportNotApproved):
        svc.generate_payload(actor="op1", request_id=req.id)


def test_download_is_audited_with_count_no_pii(app_conn: psycopg.Connection):
    _seed_profile(app_conn, "P-1", "Cucina")
    svc = ExportService(app_conn)
    req = svc.create_request(actor="op1", filters=ExportFilters(skill_query="cucina"), reason="r")
    svc.approve(actor="sup1", request_id=req.id)
    svc.generate_payload(actor="op1", request_id=req.id)
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, target_pseudonym, details FROM audit.audit_log "
            "WHERE action = 'export_downloaded' ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    assert row is not None
    actor, target, details = row
    assert actor == "op1"
    assert target is None
    assert set(details) <= {"request_id", "filters", "count"}
    assert details.get("count") == "1"


def test_create_and_decisions_are_audited(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    a = svc.create_request(actor="op1", filters=ExportFilters(), reason="r")
    svc.approve(actor="sup1", request_id=a.id)
    b = svc.create_request(actor="op1", filters=ExportFilters(), reason="r2")
    svc.deny(actor="sup1", request_id=b.id, reason="no")
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT action, actor, target_pseudonym FROM audit.audit_log "
            "WHERE action IN ('export_requested','export_approved','export_denied') ORDER BY id"
        )
        rows = cur.fetchall()
    actions = [r[0] for r in rows]
    assert actions.count("export_requested") == 2
    assert "export_approved" in actions and "export_denied" in actions
    # decision events record the approver as actor; no pseudonym leaks
    approved = next(r for r in rows if r[0] == "export_approved")
    assert approved[1] == "sup1"
    assert all(r[2] is None for r in rows)


def test_list_pending_shows_all_operators_fifo(app_conn: psycopg.Connection):
    svc = ExportService(app_conn)
    a = svc.create_request(actor="op1", filters=ExportFilters(), reason="a")
    b = svc.create_request(actor="op2", filters=ExportFilters(), reason="b")
    svc.approve(actor="sup1", request_id=a.id)  # a leaves the pending queue
    # both operators' requests are visible to the approver; only still-pending ones, FIFO
    c = svc.create_request(actor="op1", filters=ExportFilters(), reason="c")
    assert [p.id for p in svc.list_pending()] == [b.id, c.id]
