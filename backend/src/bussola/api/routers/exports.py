"""Export-request endpoints. Requester = operator (EXPORT_DATA); approver =
supervisor (APPROVE_EXPORTS). Download is server-gated on approval + ownership (§7.3).

Exception: `kind='report'` requests (created via `POST /report/export`, S28)
are both requested AND approved by the supervisor (design-approved
relaxation — the payload is anonymous/aggregate). The download route
therefore can't gate on a single fixed permission: `kind='profiles'` still
requires EXPORT_DATA (unchanged); `kind='report'` requires APPROVE_EXPORTS
instead, so the supervisor never has to be granted EXPORT_DATA, which would
also open raw-profile export (§2/§6)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from bussola.api.deps import current_operator, get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission, has_permission
from bussola.export.errors import ExportNotApproved, ExportNotFound, ExportNotPending
from bussola.export.models import ExportFilters, ExportRequest
from bussola.export.service import ExportService
from bussola.profile.models import WorkProfile
from bussola.report.csv import report_to_csv
from bussola.report.models import Report

router = APIRouter(prefix="/exports", tags=["exports"])
_request = require_permission(Permission.EXPORT_DATA)
_approve = require_permission(Permission.APPROVE_EXPORTS)


def _download_permission(
    request_id: int,
    operator: Operator = Depends(current_operator),
    conn: psycopg.Connection = Depends(get_conn),
) -> Operator:
    kind = ExportService(conn).peek_kind(request_id=request_id)
    required = Permission.APPROVE_EXPORTS if kind == "report" else Permission.EXPORT_DATA
    if not has_permission(operator.role, required):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient privileges")
    return operator


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
    format: str | None = None,
    operator: Operator = Depends(_download_permission),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[WorkProfile] | Response:
    try:
        payload = ExportService(conn).generate_payload(actor=operator.username, request_id=request_id)
    except ExportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "export request not found")
    except ExportNotApproved:
        raise HTTPException(status.HTTP_409_CONFLICT, "export request not approved")
    if isinstance(payload, Report):
        # kind='report': materialize the aggregate/anonymous report on
        # demand (never stored) as the requested file format.
        if format == "csv":
            return Response(
                content=report_to_csv(payload),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=report.csv"},
            )
        return Response(
            content=payload.model_dump_json(),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=report.json"},
        )
    return payload  # kind='profiles': unchanged (response_model=list[WorkProfile])
