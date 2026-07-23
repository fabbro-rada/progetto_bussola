from datetime import datetime, timezone

import psycopg
import pytest

from bussola.auth.accounts import AccountRepository
from bussola.auth.rbac import Role
from bussola.auth.sessions import SessionStore, hash_token

pytestmark = pytest.mark.usefixtures("db")


def _make_operator(conn: psycopg.Connection) -> int:
    op = AccountRepository(conn).create(
        username="u", display_name="U", role=Role.OPERATOR, password_hash="h", created_by="admin"
    )
    conn.commit()
    return op.id


def test_create_returns_raw_token_stored_only_as_hash(app_conn: psycopg.Connection):
    oid = _make_operator(app_conn)
    store = SessionStore(app_conn)
    token = store.create(oid)
    app_conn.commit()
    assert token and len(token) > 20
    with app_conn.cursor() as cur:
        cur.execute("SELECT token_hash FROM auth.session")
        stored = cur.fetchone()[0]
    assert stored == hash_token(token)
    assert stored != token


def test_lookup_valid_returns_operator(app_conn: psycopg.Connection):
    oid = _make_operator(app_conn)
    store = SessionStore(app_conn)
    token = store.create(oid)
    app_conn.commit()
    assert store.lookup(token) == oid


def test_lookup_unknown_returns_none(app_conn: psycopg.Connection):
    assert SessionStore(app_conn).lookup("nope") is None


def test_expired_session_is_invalid(app_conn: psycopg.Connection):
    oid = _make_operator(app_conn)
    # a clock fixed in the past so the created session is already expired
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    store = SessionStore(app_conn, now=lambda: past)
    token = store.create(oid)
    app_conn.commit()
    # look it up with the real clock -> expired
    assert SessionStore(app_conn).lookup(token) is None


def test_revoke_and_revoke_all(app_conn: psycopg.Connection):
    oid = _make_operator(app_conn)
    store = SessionStore(app_conn)
    t1 = store.create(oid)
    t2 = store.create(oid)
    app_conn.commit()
    store.revoke(t1)
    app_conn.commit()
    assert store.lookup(t1) is None
    assert store.lookup(t2) == oid
    store.revoke_all_for_operator(oid)
    app_conn.commit()
    assert store.lookup(t2) is None
