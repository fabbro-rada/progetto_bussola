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
    def _make(username: str, role: Role = Role.OPERATOR) -> tuple[str, str]:
        _op, temp = AuthService(app_conn).create_operator(
            actor="bootstrap", username=username, display_name=username.title(), role=role
        )
        return username, temp

    return _make
