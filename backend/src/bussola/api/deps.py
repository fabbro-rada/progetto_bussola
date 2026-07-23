"""FastAPI dependencies: per-request DB connection, current operator from the
bearer token, and permission gating."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import psycopg
from fastapi import Depends, Header, HTTPException, status

from bussola.auth.models import Operator
from bussola.auth.rbac import Permission, has_permission
from bussola.auth.service import AuthService
from bussola.data import config


def _open_conn() -> psycopg.Connection:
    return psycopg.connect(config.dsn("app"))


def get_conn() -> Iterator[psycopg.Connection]:
    conn = _open_conn()
    try:
        yield conn
    finally:
        conn.close()


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    return authorization[len("Bearer ") :]


def raw_bearer(authorization: str | None = Header(default=None)) -> str:
    """The raw bearer token (for logout, which must revoke the exact token)."""
    return _bearer_token(authorization)


def current_operator(
    authorization: str | None = Header(default=None),
    conn: psycopg.Connection = Depends(get_conn),
) -> Operator:
    token = _bearer_token(authorization)
    operator = AuthService(conn).authenticate(token)
    if operator is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired session")
    return operator


def require_permission(permission: Permission) -> Callable[..., Operator]:
    def _dep(operator: Operator = Depends(current_operator)) -> Operator:
        if not has_permission(operator.role, permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient privileges")
        return operator

    return _dep
