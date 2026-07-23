"""Operator account management (Amministratore only)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import CreateOperatorRequest, Operator
from bussola.auth.rbac import Permission
from bussola.auth.service import AuthService

router = APIRouter(prefix="/operators", tags=["operators"])
_manage = require_permission(Permission.MANAGE_OPERATORS)


class CreatedOperator(BaseModel):
    operator: Operator
    temp_password: str


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatedOperator)
def create_operator(
    body: CreateOperatorRequest,
    admin: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> CreatedOperator:
    operator, temp = AuthService(conn).create_operator(
        actor=admin.username,
        username=body.username,
        display_name=body.display_name,
        role=body.role,
    )
    return CreatedOperator(operator=operator, temp_password=temp)


@router.get("", response_model=list[Operator])
def list_operators(
    admin: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[Operator]:
    from bussola.auth.accounts import AccountRepository

    return AccountRepository(conn).list_all()


@router.post("/{operator_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_operator(
    operator_id: int,
    admin: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> Response:
    AuthService(conn).disable_operator(actor=admin.username, operator_id=operator_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{operator_id}/enable", status_code=status.HTTP_204_NO_CONTENT)
def enable_operator(
    operator_id: int,
    admin: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> Response:
    AuthService(conn).enable_operator(actor=admin.username, operator_id=operator_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class ResetResponse(BaseModel):
    temp_password: str


@router.post("/{operator_id}/reset-password", response_model=ResetResponse)
def reset_password(
    operator_id: int,
    admin: Operator = Depends(_manage),
    conn: psycopg.Connection = Depends(get_conn),
) -> ResetResponse:
    temp = AuthService(conn).reset_password(actor=admin.username, operator_id=operator_id)
    return ResetResponse(temp_password=temp)
