import psycopg
import pytest

pytestmark = pytest.mark.usefixtures("db")


def test_auth_schema_and_tables_exist(owner_conn: psycopg.Connection):
    with owner_conn.cursor() as cur:
        cur.execute("SELECT to_regclass('auth.operator'), to_regclass('auth.session')")
        operator_tbl, session_tbl = cur.fetchone()
    assert operator_tbl is not None
    assert session_tbl is not None


def test_app_can_write_auth_but_auditor_has_no_access(
    app_conn: psycopg.Connection, auditor_conn: psycopg.Connection
):
    with app_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO auth.operator (username, display_name, password_hash, role) "
            "VALUES ('u1', 'U One', 'h', 'operator')"
        )
    app_conn.commit()
    with auditor_conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("SELECT count(*) FROM auth.operator")
    auditor_conn.rollback()
