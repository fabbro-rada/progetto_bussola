from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from bussola.api import deps
from bussola.api.app import create_app
from bussola.auth.rbac import Role
from bussola.auth.service import AuthService


@pytest.fixture
def client(app_conn: psycopg.Connection) -> TestClient:
    # Route every request's DB connection to the test connection WITHOUT closing
    # it (the real get_conn would close the shared conn after the first request).
    app = create_app()

    def _test_conn():
        yield app_conn

    app.dependency_overrides[deps.get_conn] = _test_conn
    return TestClient(app)


@pytest.fixture
def make_operator(app_conn: psycopg.Connection):
    def _make(
        username: str, role: Role = Role.OPERATOR, *, activated: bool = True
    ) -> tuple[str, str]:
        """Create an operator and return (username, password).

        By default the operator is *activated*: the first-login password change
        is completed here, so `must_change_password` is False and the returned
        password is the post-change one. This mirrors a real operator doing
        their job — the state every business-endpoint test needs now that
        `require_password_changed` gates business access (§7.3). Pass
        `activated=False` for the auth-flow tests that must observe the fresh,
        must-change state on first login.
        """
        svc = AuthService(app_conn)
        op, temp = svc.create_operator(
            actor="bootstrap", username=username, display_name=username.title(), role=role
        )
        if not activated:
            return username, temp
        new_password = "activated-pw-123"  # >= 8 chars (ChangePasswordRequest)
        svc.change_password(op.id, temp, new_password)
        return username, new_password

    return _make
