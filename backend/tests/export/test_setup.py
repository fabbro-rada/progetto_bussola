import psycopg
import pytest

from bussola.auth.rbac import Permission, Role, has_permission

pytestmark = pytest.mark.usefixtures("db")


def test_export_schema_and_table_exist(owner_conn: psycopg.Connection):
    with owner_conn.cursor() as cur:
        cur.execute("SELECT to_regclass('export.export_request')")
        assert cur.fetchone()[0] is not None


def test_status_check_rejects_unknown_value(app_conn: psycopg.Connection):
    with app_conn.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO export.export_request (requested_by, reason, status) "
                "VALUES ('op1', 'why', 'bogus')"
            )
    app_conn.rollback()


def test_app_can_write_but_not_delete_and_auditor_has_no_access(
    app_conn: psycopg.Connection, auditor_conn: psycopg.Connection
):
    with app_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO export.export_request (requested_by, reason) VALUES ('op1', 'why')"
        )
    app_conn.commit()
    with app_conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM export.export_request")
    app_conn.rollback()
    with auditor_conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("SELECT count(*) FROM export.export_request")
    auditor_conn.rollback()


def test_supervisor_approves_exports_operator_does_not():
    assert has_permission(Role.SUPERVISOR, Permission.APPROVE_EXPORTS) is True
    assert has_permission(Role.OPERATOR, Permission.APPROVE_EXPORTS) is False
    # the requester permission stays with the operator
    assert has_permission(Role.OPERATOR, Permission.EXPORT_DATA) is True
    assert has_permission(Role.SUPERVISOR, Permission.EXPORT_DATA) is False
