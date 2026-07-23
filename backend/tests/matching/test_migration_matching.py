import psycopg
import pytest

pytestmark = pytest.mark.usefixtures("db")


def test_matching_schema_and_table_exist(owner_conn: psycopg.Connection):
    with owner_conn.cursor() as cur:
        cur.execute("SELECT to_regclass('matching.job_request')")
        assert cur.fetchone()[0] is not None


def test_app_can_write_matching_but_auditor_cannot(
    app_conn: psycopg.Connection, auditor_conn: psycopg.Connection
):
    with app_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO matching.job_request (title, sector, created_by) "
            "VALUES ('Cuoco', 'ristorazione', 'op1')"
        )
    app_conn.commit()
    with auditor_conn.cursor() as cur:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("SELECT count(*) FROM matching.job_request")
    auditor_conn.rollback()
