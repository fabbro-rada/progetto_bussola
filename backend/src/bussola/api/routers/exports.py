"""Export-request endpoints. Requester = operator (EXPORT_DATA); approver =
supervisor (APPROVE_EXPORTS). Download is server-gated on approval + ownership (§7.3)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.export.errors import ExportNotApproved, ExportNotFound, ExportNotPending
from bussola.export.models import ExportFilters, ExportRequest
from bussola.export.service import ExportService
from bussola.profile.models import WorkProfile

router = APIRouter(prefix="/exports", tags=["exports"])
_request = require_permission(Permission.EXPORT_DATA)
_approve = require_permission(Permission.APPROVE_EXPORTS)


class CreateExportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: ExportFilters
    reason: str = Field(min_length=1, max_length=500)


class DenyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=500)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ExportRequest)
def create_export(
    body: CreateExportBody,
    operator: Operator = Depends(_request),
    conn: psycopg.Connection = Depends(get_conn),
) -> ExportRequest:
    return ExportService(conn).create_request(actor=operator.username, filters=body.filters, reason=body.reason)


@router.get("", response_model=list[ExportRequest])
def list_my_exports(
    operator: Operator = Depends(_request),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[ExportRequest]:
    return ExportService(conn).list_own(actor=operator.username)


@router.get("/pending", response_model=list[ExportRequest])
def list_pending_exports(
    operator: Operator = Depends(_approve),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[ExportRequest]:
    return ExportService(conn).list_pending()


@router.post("/{request_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
def approve_export(
    request_id: int,
    operator: Operator = Depends(_approve),
    conn: psycopg.Connection = Depends(get_conn),
) -> Response:
    try:
        ExportService(conn).approve(actor=operator.username, request_id=request_id)
    except ExportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "export request not found")
    except ExportNotPending:
        raise HTTPException(status.HTTP_409_CONFLICT, "export request already decided")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{request_id}/deny", status_code=status.HTTP_204_NO_CONTENT)
def deny_export(
    request_id: int,
    body: DenyBody,
    operator: Operator = Depends(_approve),
    conn: psycopg.Connection = Depends(get_conn),
) -> Response:
    try:
        ExportService(conn).deny(actor=operator.username, request_id=request_id, reason=body.reason)
    except ExportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "export request not found")
    except ExportNotPending:
        raise HTTPException(status.HTTP_409_CONFLICT, "export request already decided")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{request_id}/download", response_model=list[WorkProfile])
def download_export(
    request_id: int,
    operator: Operator = Depends(_request),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[WorkProfile]:
    try:
        return ExportService(conn).generate_payload(actor=operator.username, request_id=request_id)
    except ExportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "export request not found")
    except ExportNotApproved:
        raise HTTPException(status.HTTP_409_CONFLICT, "export request not approved")
