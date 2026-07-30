from __future__ import annotations

import psycopg
import pytest

from bussola.followup.service import FollowupTokenService

pytestmark = pytest.mark.usefixtures("db")


def test_issue_then_consume_returns_pseudonym_once(app_conn: psycopg.Connection):
    svc = FollowupTokenService(app_conn)
    tok = svc.issue("P-abc", actor="op1")
    app_conn.commit()
    assert svc.consume(tok) == "P-abc"  # first use OK
    app_conn.commit()
    assert svc.consume(tok) is None  # single-use: second use rejected


def test_only_hash_stored_never_cleartext(app_conn: psycopg.Connection):
    svc = FollowupTokenService(app_conn)
    tok = svc.issue("P-abc", actor="op1")
    app_conn.commit()
    with app_conn.cursor() as cur:
        cur.execute("SELECT token_hash FROM followup.followup_token")
        stored = cur.fetchone()[0]
    assert stored != tok and len(stored) == 64  # sha256 hex, not the token


def test_expired_token_rejected(app_conn: psycopg.Connection):
    svc = FollowupTokenService(app_conn, ttl_seconds=0)
    tok = svc.issue("P-abc", actor="op1")
    app_conn.commit()
    assert svc.consume(tok) is None  # already expired


def test_unknown_token_rejected(app_conn: psycopg.Connection):
    assert FollowupTokenService(app_conn).consume("nope") is None
