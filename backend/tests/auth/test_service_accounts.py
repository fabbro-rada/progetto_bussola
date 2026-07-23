import psycopg
import pytest

from bussola.auth.errors import OperatorNotFound
from bussola.auth.rbac import Role
from bussola.auth.service import AuthService

pytestmark = pytest.mark.usefixtures("db")


def test_create_operator_returns_temp_password_and_forces_change(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    op, temp = svc.create_operator(
        actor="admin", username="newop", display_name="New Op", role=Role.OPERATOR
    )
    assert op.username == "newop" and op.must_change_password is True
    assert temp and len(temp) >= 8
    # the temp password actually works
    assert svc.login("newop", temp).operator.username == "newop"


def test_create_is_audited_with_whitelisted_details(app_conn: psycopg.Connection):
    AuthService(app_conn).create_operator(
        actor="admin", username="op2", display_name="Op Two", role=Role.SUPERVISOR
    )
    with app_conn.cursor() as cur:
        cur.execute("SELECT action, actor, details FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        action, actor, details = cur.fetchone()
    assert action == "operator_created" and actor == "admin"
    assert details["target_operator"] == "op2" and details["role"] == "supervisor"


def test_disable_revokes_sessions_immediately(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    op, temp = svc.create_operator(
        actor="admin", username="todisable", display_name="X", role=Role.OPERATOR
    )
    token = svc.login("todisable", temp).token
    assert svc.authenticate(token) is not None
    svc.disable_operator(actor="admin", operator_id=op.id)
    assert svc.authenticate(token) is None  # session dead + account inactive


def test_reset_password_issues_new_temp_and_revokes(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    op, temp = svc.create_operator(
        actor="admin", username="toreset", display_name="X", role=Role.OPERATOR
    )
    token = svc.login("toreset", temp).token
    new_temp = svc.reset_password(actor="admin", operator_id=op.id)
    assert new_temp != temp
    assert svc.authenticate(token) is None  # old sessions revoked
    assert svc.login("toreset", new_temp).operator.username == "toreset"


def test_disable_operator_is_audited(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    op, _ = svc.create_operator(
        actor="admin", username="todisable2", display_name="X", role=Role.OPERATOR
    )
    svc.disable_operator(actor="admin", operator_id=op.id)
    with app_conn.cursor() as cur:
        cur.execute("SELECT action, actor, details FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        action, actor, details = cur.fetchone()
    assert action == "operator_disabled"
    assert actor == "admin"
    assert details["target_operator"] == "todisable2"


def test_enable_operator_is_audited(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    op, _ = svc.create_operator(
        actor="admin", username="toenable", display_name="X", role=Role.OPERATOR
    )
    svc.disable_operator(actor="admin", operator_id=op.id)
    svc.enable_operator(actor="admin", operator_id=op.id)
    with app_conn.cursor() as cur:
        cur.execute("SELECT action, actor, details FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        action, actor, details = cur.fetchone()
    assert action == "operator_enabled"
    assert actor == "admin"
    assert details["target_operator"] == "toenable"


def test_reset_password_is_audited(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    op, _ = svc.create_operator(
        actor="admin", username="toreset2", display_name="X", role=Role.OPERATOR
    )
    svc.reset_password(actor="admin", operator_id=op.id)
    with app_conn.cursor() as cur:
        cur.execute("SELECT action, actor, details FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        action, actor, details = cur.fetchone()
    assert action == "operator_password_reset"
    assert actor == "admin"
    assert details["target_operator"] == "toreset2"


def test_operations_on_missing_operator_raise(app_conn: psycopg.Connection):
    svc = AuthService(app_conn)
    with pytest.raises(OperatorNotFound):
        svc.disable_operator(actor="admin", operator_id=999999)
