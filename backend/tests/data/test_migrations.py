import psycopg

from .conftest import requires_db

pytestmark = requires_db


def test_schemas_exist(owner_conn: psycopg.Connection):
    with owner_conn.cursor() as cur:
        cur.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name IN ('profiles', 'audit')"
        )
        found = {r[0] for r in cur.fetchall()}
    assert found == {"profiles", "audit"}


def test_auditor_cannot_use_profiles_schema(auditor_conn: psycopg.Connection):
    with auditor_conn.cursor() as cur:
        cur.execute("SELECT has_schema_privilege('bussola_auditor', 'profiles', 'USAGE')")
        assert cur.fetchone()[0] is False


def test_app_can_use_both_schemas(app_conn: psycopg.Connection):
    with app_conn.cursor() as cur:
        cur.execute("SELECT has_schema_privilege('bussola_app', 'profiles', 'USAGE')")
        assert cur.fetchone()[0] is True
        cur.execute("SELECT has_schema_privilege('bussola_app', 'audit', 'USAGE')")
        assert cur.fetchone()[0] is True
