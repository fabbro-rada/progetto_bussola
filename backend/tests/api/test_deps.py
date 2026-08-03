import psycopg
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from bussola.api import deps
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission, Role
from bussola.auth.service import AuthService

pytestmark = pytest.mark.usefixtures("db")


def _client(app_conn: psycopg.Connection) -> TestClient:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(op: Operator = Depends(deps.current_operator)) -> dict:
        return {"username": op.username}

    @app.get("/admin-only")
    def admin_only(
        op: Operator = Depends(deps.require_permission(Permission.MANAGE_OPERATORS)),
    ) -> dict:
        return {"ok": True}

    # Route the request-scoped DB dependency to the test connection WITHOUT
    # closing it (get_conn would otherwise close the shared conn after req #1).
    def _test_conn():
        yield app_conn

    app.dependency_overrides[deps.get_conn] = _test_conn
    return TestClient(app)


def test_no_token_is_401(app_conn):
    assert _client(app_conn).get("/whoami").status_code == 401


def test_valid_session_reaches_route(app_conn):
    _op, temp = AuthService(app_conn).create_operator(
        actor="admin", username="alice", display_name="A", role=Role.OPERATOR
    )
    session = AuthService(app_conn).login("alice", temp).token
    r = _client(app_conn).get("/whoami", headers={"Authorization": f"Bearer {session}"})
    assert r.status_code == 200 and r.json()["username"] == "alice"


def test_permission_denied_is_403(app_conn):
    svc = AuthService(app_conn)
    op, temp = svc.create_operator(
        actor="admin", username="op", display_name="O", role=Role.OPERATOR
    )
    # Complete the first-login change so this hits the PERMISSION gate, not the
    # must-change gate below.
    svc.change_password(op.id, temp, "activated-pw-123")
    session = svc.login("op", "activated-pw-123").token
    r = _client(app_conn).get("/admin-only", headers={"Authorization": f"Bearer {session}"})
    assert r.status_code == 403


def test_must_change_password_blocks_business_endpoints(app_conn):
    # §7.3: an operator still on the temporary password is authenticated but may
    # not reach a permission-gated endpoint until the change is done (server-side
    # backstop, not just a client redirect). Grant enough role privilege that a
    # 403 here can only be the must-change gate, not a permission denial.
    svc = AuthService(app_conn)
    _op, temp = svc.create_operator(
        actor="admin", username="fresh", display_name="F", role=Role.ADMIN
    )
    session = svc.login("fresh", temp).token  # must_change_password still True
    client = _client(app_conn)
    # whoami (plain current_operator) stays reachable — the person must be able
    # to see their state and change the password.
    assert client.get("/whoami", headers={"Authorization": f"Bearer {session}"}).status_code == 200
    r = client.get("/admin-only", headers={"Authorization": f"Bearer {session}"})
    assert r.status_code == 403
    assert r.json()["detail"] == "password change required"


def test_password_change_unblocks_business_endpoints(app_conn):
    svc = AuthService(app_conn)
    op, temp = svc.create_operator(
        actor="admin", username="willchange", display_name="W", role=Role.ADMIN
    )
    svc.change_password(op.id, temp, "activated-pw-123")
    session = svc.login("willchange", "activated-pw-123").token  # must_change now False
    r = _client(app_conn).get("/admin-only", headers={"Authorization": f"Bearer {session}"})
    assert r.status_code == 200  # ADMIN has MANAGE_OPERATORS and the gate is cleared
