import psycopg

from .conftest import requires_db

pytestmark = requires_db

_TEST_DB = "bussola_test"  # session test DB (see tests/conftest.py)


def test_migrate_main_is_idempotent_on_migrated_db(db: None, capsys):
    # The CLI (`python -m bussola.data.migrate`, used by scripts/run-stack.sh)
    # connects by DSN and applies pending migrations. On the already-migrated
    # test DB it applies nothing and reports so — proving connect+delegate+report.
    from bussola.data import config, migrate

    rc = migrate.main(config.dsn("owner", dbname=_TEST_DB))
    assert rc == 0
    assert "up to date" in capsys.readouterr().out


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


def test_0007_adds_match_run_and_export_kind(owner_conn: psycopg.Connection):
    from bussola.data.migrate import apply_migrations

    # Migrations already applied once via the session-scoped `test_database`
    # fixture; re-running here on an already-migrated DB checks idempotency.
    apply_migrations(owner_conn)
    with owner_conn.cursor() as cur:
        cur.execute(
            "SELECT evaluated_count, compatible_count, gaps FROM matching.match_run WHERE false"
        )
        cur.execute("SELECT kind FROM export.export_request WHERE false")
        cur.execute(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_schema='export' AND table_name='export_request' AND column_name='kind'"
        )
        assert "profiles" in (cur.fetchone()[0] or "")


def test_auditor_cannot_use_matching_schema(auditor_conn: psycopg.Connection):
    with auditor_conn.cursor() as cur:
        cur.execute("SELECT has_schema_privilege('bussola_auditor', 'matching', 'USAGE')")
        assert cur.fetchone()[0] is False


def test_0008_adds_followup_token_without_identity_columns(owner_conn: psycopg.Connection):
    from bussola.data.migrate import apply_migrations

    # Migrations already applied once via the session-scoped `test_database`
    # fixture; re-running here on an already-migrated DB checks idempotency.
    apply_migrations(owner_conn)
    with owner_conn.cursor() as cur:
        cur.execute(
            "SELECT token_hash, pseudonym_id, created_at, expires_at, used_at "
            "FROM followup.followup_token WHERE false"
        )
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='followup' AND table_name='followup_token'"
        )
        cols = {r[0] for r in cur.fetchall()}
        assert cols == {"token_hash", "pseudonym_id", "created_at", "expires_at", "used_at"}
        # §5: the profile/token store must never carry identity data.
        assert not cols & {"name", "surname", "person", "anagraphic", "identity", "cf"}
        # deny-by-omission: auditor gets no USAGE on the followup schema at all.
        cur.execute("SELECT has_schema_privilege('bussola_auditor', 'followup', 'USAGE')")
        assert cur.fetchone()[0] is False
