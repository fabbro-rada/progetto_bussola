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
