import psycopg
from bussola.data import config
from bussola.data.migrate import apply_migrations


def test_identity_and_startcode_tables_exist_and_are_segregated():
    with psycopg.connect(config.dsn("owner")) as conn:
        apply_migrations(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='identity' AND table_name='pseudonym_identity' ORDER BY 1"
            )
            cols = [r[0] for r in cur.fetchall()]
            assert cols == ["created_at", "created_by", "matricola", "pseudonym_id"]
            # matricola is UNIQUE (one profile per person)
            cur.execute(
                "SELECT 1 FROM information_schema.table_constraints "
                "WHERE table_schema='identity' AND table_name='pseudonym_identity' "
                "AND constraint_type='UNIQUE'"
            )
            assert cur.fetchone() is not None
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='startcode' AND table_name='start_code' ORDER BY 1"
            )
            assert [r[0] for r in cur.fetchall()] == [
                "code_hash", "created_at", "expires_at", "pseudonym_id", "used_at",
            ]


def test_identity_and_startcode_grants_are_segregated():
    # §5/§6: the auditor gets NO grant on either new schema (deny-by-omission),
    # and bussola_app can only append to identity.pseudonym_identity (the
    # pseudonym<->matricola link is immutable, never updated or deleted), while
    # it can update (but never delete) startcode.start_code to mark a code used.
    with psycopg.connect(config.dsn("owner")) as conn:
        apply_migrations(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT has_schema_privilege('bussola_auditor', 'identity', 'USAGE')")
            assert cur.fetchone()[0] is False
            cur.execute("SELECT has_schema_privilege('bussola_auditor', 'startcode', 'USAGE')")
            assert cur.fetchone()[0] is False
            cur.execute(
                "SELECT has_table_privilege('bussola_app', 'identity.pseudonym_identity', 'UPDATE')"
            )
            assert cur.fetchone()[0] is False
            cur.execute(
                "SELECT has_table_privilege('bussola_app', 'identity.pseudonym_identity', 'DELETE')"
            )
            assert cur.fetchone()[0] is False
            cur.execute(
                "SELECT has_table_privilege('bussola_app', 'startcode.start_code', 'UPDATE')"
            )
            assert cur.fetchone()[0] is True
            cur.execute(
                "SELECT has_table_privilege('bussola_app', 'startcode.start_code', 'DELETE')"
            )
            assert cur.fetchone()[0] is False
