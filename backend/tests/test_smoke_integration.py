"""End-to-end integration smoke.

Unlike the per-router unit tests (which inject one shared connection via a
get_conn override, so writes are visible without a commit), this exercises the
REAL wiring: deps.get_conn opens a fresh connection per request as the app role
and closes it WITHOUT committing. A service that forgot to commit fails here.

Path: bootstrap (real CLI) -> admin login -> forced password change -> admin
creates an operator -> operator authenticated write (committed, re-read on a
fresh request) -> RBAC deny -> audit rows persisted (read directly).
"""

from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient

from bussola.api.app import create_app
from bussola.auth import bootstrap
from bussola.auth.rbac import Role
from bussola.data import config


def test_full_stack_wiring_smoke(
    db: None, auditor_conn: psycopg.Connection, monkeypatch
) -> None:
    # Point the app's real get_conn (config.dsn("app"), no dbname) at the
    # migrated test DB, so we exercise real per-request connection management
    # instead of the shared app_conn override used by router unit tests.
    monkeypatch.setattr(config, "_DBNAME", "bussola_test")

    # 1. Bootstrap the first admin via the REAL CLI entrypoint (what a new PC runs).
    monkeypatch.setenv("BUSSOLA_ADMIN_USERNAME", "smoke_admin")
    monkeypatch.setenv("BUSSOLA_ADMIN_PASSWORD", "bootstrap-temp-pw-1")
    assert bootstrap.main() == 0

    client = TestClient(create_app())  # NO get_conn override: real wiring.

    # 2. Admin logs in with the temp password -> must change it.
    r = client.post(
        "/auth/login",
        json={"username": "smoke_admin", "password": "bootstrap-temp-pw-1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["must_change_password"] is True
    admin_token = r.json()["token"]

    # 3. Change the password.
    r = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"old_password": "bootstrap-temp-pw-1", "new_password": "admin-new-pw-123"},
    )
    assert r.status_code == 204, r.text

    # 4. Re-login with the new password.
    r = client.post(
        "/auth/login",
        json={"username": "smoke_admin", "password": "admin-new-pw-123"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["must_change_password"] is False
    admin_auth = {"Authorization": f"Bearer {r.json()['token']}"}

    # 5. Admin creates an operator; receives that operator's temp password.
    r = client.post(
        "/operators",
        headers=admin_auth,
        json={"username": "smoke_op", "display_name": "Smoke Op", "role": Role.OPERATOR.value},
    )
    assert r.status_code == 201, r.text
    op_temp = r.json()["temp_password"]

    # 6. Operator logs in and changes password.
    r = client.post("/auth/login", json={"username": "smoke_op", "password": op_temp})
    assert r.status_code == 200, r.text
    op_token = r.json()["token"]
    r = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {op_token}"},
        json={"old_password": op_temp, "new_password": "op-new-pw-123"},
    )
    assert r.status_code == 204, r.text
    r = client.post("/auth/login", json={"username": "smoke_op", "password": "op-new-pw-123"})
    assert r.status_code == 200, r.text
    assert r.json()["must_change_password"] is False
    op_auth = {"Authorization": f"Bearer {r.json()['token']}"}

    # 7. Operator performs an authenticated write that COMMITS.
    r = client.post(
        "/job-requests",
        headers=op_auth,
        json={"title": "Aiuto cuoco", "sector": "ristorazione"},
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    # 8. A separate request (fresh connection) sees the committed row -> proves
    #    the write was really committed, not just visible inside one transaction.
    r = client.get(f"/job-requests/{job_id}", headers=op_auth)
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Aiuto cuoco"

    # 9. RBAC: the operator cannot perform an admin-only action.
    r = client.post(
        "/operators",
        headers=op_auth,
        json={"username": "nope", "display_name": "Nope", "role": Role.OPERATOR.value},
    )
    assert r.status_code == 403, r.text

    # 10. Audit: the HTTP actions persisted immutable rows (read directly as auditor).
    auditor_conn.rollback()  # fresh snapshot: see everything committed above
    with auditor_conn.cursor() as cur:
        cur.execute("SELECT action FROM audit.audit_log")
        actions = {row[0] for row in cur.fetchall()}
    assert {"operator_created", "login_succeeded", "password_changed"} <= actions
