from datetime import datetime, timezone

import psycopg
import pytest

from bussola.data.audit import append_audit, list_audit, verify_audit_chain

pytestmark = pytest.mark.usefixtures("db")


def _seed(conn: psycopg.Connection) -> None:
    append_audit(conn, action="login_succeeded", actor="op1")
    append_audit(conn, action="profile_viewed", actor="op1", target_pseudonym="P-1")
    append_audit(conn, action="metrics_viewed", actor="sup1")


def test_lists_newest_first(app_conn: psycopg.Connection):
    _seed(app_conn)
    entries = list_audit(app_conn)
    assert [e.action for e in entries] == ["metrics_viewed", "profile_viewed", "login_succeeded"]
    # entry exposes who/what/when/details, not the hashes
    top = entries[0]
    assert top.actor == "sup1" and top.target_pseudonym is None
    assert set(top.model_dump()) == {
        "id",
        "occurred_at",
        "actor",
        "action",
        "target_pseudonym",
        "details",
    }


def test_cursor_before_and_limit_cap(app_conn: psycopg.Connection):
    _seed(app_conn)
    all_entries = list_audit(app_conn)
    second_id = all_entries[1].id
    older = list_audit(app_conn, before=all_entries[0].id)
    assert older[0].id == second_id  # excludes the newest
    assert len(list_audit(app_conn, limit=1)) == 1
    assert len(list_audit(app_conn, limit=9999)) <= 200  # cap enforced


def test_filters_actor_action_and_time(app_conn: psycopg.Connection):
    _seed(app_conn)
    assert all(e.actor == "op1" for e in list_audit(app_conn, actor="op1"))
    assert [e.action for e in list_audit(app_conn, action="metrics_viewed")] == ["metrics_viewed"]
    future = datetime(2999, 1, 1, tzinfo=timezone.utc)
    assert list_audit(app_conn, from_ts=future) == []


def test_verify_ok_on_intact_chain(app_conn: psycopg.Connection):
    _seed(app_conn)
    result = verify_audit_chain(app_conn)
    assert result.ok is True


def test_verify_detects_a_tampered_row(app_conn: psycopg.Connection):
    _seed(app_conn)
    # INSERT is permitted (only UPDATE/DELETE are trigger-blocked); a row with a
    # bogus prev_hash breaks the chain without touching existing rows.
    with app_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO audit.audit_log "
            "(occurred_at, actor, action, target_pseudonym, details, prev_hash, record_hash) "
            "VALUES (now(), 'x', 'tampered', NULL, '{}'::jsonb, 'wrongprev', 'wronghash') RETURNING id"
        )
        row = cur.fetchone()
    app_conn.commit()
    assert row is not None
    result = verify_audit_chain(app_conn)
    assert result.ok is False
    assert result.broken_at == row[0]
