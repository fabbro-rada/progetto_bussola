"""Authentication endpoints: login, logout, whoami, self password change."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from bussola.api.deps import current_operator, get_conn, raw_bearer
from bussola.auth.models import ChangePasswordRequest, LoginRequest, Operator
from bussola.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginResponse(BaseModel):
    token: str
    operator: Operator
    must_change_password: bool


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, conn: psycopg.Connection = Depends(get_conn)) -> LoginResponse:
    result = AuthService(conn).login(body.username, body.password)
    return LoginResponse(
        token=result.token,
        operator=result.operator,
        must_change_password=result.must_change_password,
    )


@router.get("/me", response_model=Operator)
def me(operator: Operator = Depends(current_operator)) -> Operator:
    return operator


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    token: str = Depends(raw_bearer),
    conn: psycopg.Connection = Depends(get_conn),
    operator: Operator = Depends(current_operator),
) -> Response:
    AuthService(conn).logout(token, actor=operator.username)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    conn: psycopg.Connection = Depends(get_conn),
    operator: Operator = Depends(current_operator),
) -> Response:
    AuthService(conn).change_password(operator.id, body.old_password, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
