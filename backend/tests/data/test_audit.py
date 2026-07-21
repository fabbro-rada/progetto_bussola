import psycopg
import pytest

from bussola.data.audit import append_audit, verify_audit_chain

from .conftest import requires_db

pytestmark = requires_db


def test_append_and_verify_ok(app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1", target_pseudonym="P-1")
    append_audit(app_conn, action="matching_run", actor="op1")
    result = verify_audit_chain(app_conn)
    assert result.ok is True


def test_app_cannot_update_audit(app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1")
    with pytest.raises(psycopg.Error):
        with app_conn.cursor() as cur:
            cur.execute("UPDATE audit.audit_log SET action = 'tampered'")
    app_conn.rollback()


def test_app_cannot_delete_audit(app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1")
    with pytest.raises(psycopg.Error):
        with app_conn.cursor() as cur:
            cur.execute("DELETE FROM audit.audit_log")
    app_conn.rollback()


def test_auditor_can_read_audit_but_not_profiles(
    auditor_conn: psycopg.Connection, app_conn: psycopg.Connection
):
    append_audit(app_conn, action="export_performed", actor="sup1")
    with auditor_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log")
        assert cur.fetchone()[0] == 1
    with pytest.raises(psycopg.Error):
        with auditor_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM profiles.work_profile")
    auditor_conn.rollback()


def test_tampering_is_detected(app_conn: psycopg.Connection, owner_conn: psycopg.Connection):
    append_audit(app_conn, action="a1", actor="op1")
    append_audit(app_conn, action="a2", actor="op1")
    # Tamper as owner (drop the append-only trigger, mutate, restore).
    with owner_conn.cursor() as cur:
        cur.execute("ALTER TABLE audit.audit_log DISABLE TRIGGER audit_log_append_only")
        cur.execute("UPDATE audit.audit_log SET action = 'tampered' WHERE id = 1")
        cur.execute("ALTER TABLE audit.audit_log ENABLE TRIGGER audit_log_append_only")
    owner_conn.commit()
    result = verify_audit_chain(app_conn)
    assert result.ok is False
    assert result.broken_at == 1
