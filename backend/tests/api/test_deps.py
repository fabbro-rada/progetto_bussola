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
    _op, temp = AuthService(app_conn).create_operator(
        actor="admin", username="op", display_name="O", role=Role.OPERATOR
    )
    session = AuthService(app_conn).login("op", temp).token
    r = _client(app_conn).get("/admin-only", headers={"Authorization": f"Bearer {session}"})
    assert r.status_code == 403
