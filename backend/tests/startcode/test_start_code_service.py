from __future__ import annotations

import psycopg
import pytest

from bussola.auth.sessions import hash_token
from bussola.startcode.service import StartCodeService

pytestmark = pytest.mark.usefixtures("db")


def test_issue_then_consume_returns_pseudonym_once(app_conn: psycopg.Connection):
    svc = StartCodeService(app_conn)
    code = svc.issue("P-abc")
    app_conn.commit()
    assert svc.consume(code) == "P-abc"  # first use OK
    app_conn.commit()
    assert svc.consume(code) is None  # single-use: second use rejected


def test_expired_code_is_rejected(app_conn: psycopg.Connection):
    svc = StartCodeService(app_conn, ttl_seconds=-1)
    code = svc.issue("P-exp")
    app_conn.commit()
    assert StartCodeService(app_conn).consume(code) is None


def test_stores_only_the_hash(app_conn: psycopg.Connection):
    svc = StartCodeService(app_conn)
    code = svc.issue("P-h")
    app_conn.commit()
    with app_conn.cursor() as cur:
        cur.execute("SELECT code_hash FROM startcode.start_code WHERE pseudonym_id='P-h'")
        assert cur.fetchone()[0] == hash_token(code)


def test_unknown_code_rejected(app_conn: psycopg.Connection):
    assert StartCodeService(app_conn).consume("nope") is None
