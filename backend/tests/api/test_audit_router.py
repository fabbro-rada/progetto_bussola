import psycopg
import pytest

from bussola.auth.rbac import Role
from bussola.data.audit import append_audit

pytestmark = pytest.mark.usefixtures("db")


def _login(client, user: str, temp: str) -> str:
    return client.post("/auth/login", json={"username": user, "password": temp}).json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auditor_reads_entries_newest_first(client, make_operator, app_conn: psycopg.Connection):
    # Operator creation + login each append their own audit row (operator_created,
    # login_succeeded), so they happen first; the two manual entries below are then
    # the newest, with "metrics_viewed" last.
    user, temp = make_operator("aud1", Role.AUDITOR)
    tok = _login(client, user, temp)
    append_audit(app_conn, action="profile_viewed", actor="op1", target_pseudonym="P-1")
    append_audit(app_conn, action="metrics_viewed", actor="sup1")
    r = client.get("/audit", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    # newest first; entries expose no internal hashes
    assert body[0]["action"] == "metrics_viewed"
    assert "record_hash" not in body[0] and "prev_hash" not in body[0]


def test_non_auditor_roles_are_forbidden(client, make_operator):
    for name, role in [("op1", Role.OPERATOR), ("sup1", Role.SUPERVISOR), ("adm1", Role.ADMIN)]:
        user, temp = make_operator(name, role)
        tok = _login(client, user, temp)
        assert client.get("/audit", headers=_auth(tok)).status_code == 403
        assert client.get("/audit/verify", headers=_auth(tok)).status_code == 403


def test_filters_and_cursor_are_applied(client, make_operator, app_conn: psycopg.Connection):
    append_audit(app_conn, action="profile_viewed", actor="op1")
    append_audit(app_conn, action="metrics_viewed", actor="sup1")
    user, temp = make_operator("aud1", Role.AUDITOR)
    tok = _login(client, user, temp)
    only = client.get("/audit?action=metrics_viewed", headers=_auth(tok)).json()
    assert [e["action"] for e in only] == ["metrics_viewed"]
    assert all(e["actor"] == "op1" for e in client.get("/audit?actor=op1", headers=_auth(tok)).json())
    one = client.get("/audit?limit=1", headers=_auth(tok)).json()
    assert len(one) == 1


def test_reading_the_log_does_not_write_to_it(client, make_operator, app_conn: psycopg.Connection):
    user, temp = make_operator("aud1", Role.AUDITOR)
    tok = _login(client, user, temp)  # login writes an audit row; count AFTER it
    with app_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log")
        before = cur.fetchone()[0]
    client.get("/audit", headers=_auth(tok))
    client.get("/audit/verify", headers=_auth(tok))
    with app_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit.audit_log")
        after = cur.fetchone()[0]
    assert after == before  # §6: the auditor's reads modify nothing


def test_verify_reports_intact_chain(client, make_operator, app_conn: psycopg.Connection):
    append_audit(app_conn, action="login_succeeded", actor="op1")
    user, temp = make_operator("aud1", Role.AUDITOR)
    tok = _login(client, user, temp)
    r = client.get("/audit/verify", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["ok"] is True
