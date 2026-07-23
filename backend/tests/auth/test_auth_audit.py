import psycopg
import pytest

from bussola.auth.auth_audit import record_auth_event

pytestmark = pytest.mark.usefixtures("db")


def _count(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log")
        return cur.fetchone()[0]


def test_event_participates_in_caller_transaction_and_rolls_back(app_conn: psycopg.Connection):
    assert _count(app_conn) == 0
    record_auth_event(app_conn, action="login_succeeded", actor="alice")
    # not committed yet -> visible in-tx, absent after rollback
    assert _count(app_conn) == 1
    app_conn.rollback()
    assert _count(app_conn) == 0


def test_details_are_whitelisted(app_conn: psycopg.Connection):
    record_auth_event(
        app_conn,
        action="operator_created",
        actor="admin",
        target_operator="bob",
        role="operator",
    )
    app_conn.commit()
    with app_conn.cursor() as cur:
        cur.execute(
            "SELECT actor, action, target_pseudonym, details FROM audit.audit_log ORDER BY id DESC LIMIT 1"
        )
        actor, action, target_pseudonym, details = cur.fetchone()
    assert actor == "admin"
    assert action == "operator_created"
    assert target_pseudonym is None
    assert set(details) <= {"target_operator", "role"}
    assert details["target_operator"] == "bob"
