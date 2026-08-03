"""Aggregate/anonymous report endpoint (supervisor role). §2/§7.2/§7.3."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, status

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.export.models import ExportFilters, ExportRequest
from bussola.export.service import ExportService
from bussola.report.models import Report
from bussola.report.service import compute_report

router = APIRouter(prefix="/report", tags=["report"])
_view = require_permission(Permission.VIEW_METRICS)


@router.get("", response_model=Report)
def get_report(
    operator: Operator = Depends(_view),
    conn: psycopg.Connection = Depends(get_conn),
) -> Report:
    report = compute_report(conn)
    append_audit(conn, action="report_viewed", actor=operator.username, target_pseudonym=None)
    return report


@router.post("/export", status_code=status.HTTP_201_CREATED, response_model=ExportRequest)
def create_report_export(
    operator: Operator = Depends(_view),
    conn: psycopg.Connection = Depends(get_conn),
) -> ExportRequest:
    """Create a `kind='report'` export request, gated on VIEW_METRICS (the
    supervisor's own permission) rather than EXPORT_DATA — so the
    supervisor can request the anonymous report export without gaining
    EXPORT_DATA, which would also open raw-profile export (§2/§6).

    Auto-approved in the same call: for `kind='report'` the requester and the
    approver are the same authority (the supervisor), so a separate manual
    approval step is redundant friction. The approval still HAPPENS and is
    audited (`export_requested` + `export_approved`, §7.3 «ogni export passa da
    un'approvazione») — it is just no longer a second click. The returned
    request is already `approved`, so the UI can download it immediately. The
    profiles-export flow (operator requests, supervisor approves) is untouched:
    there the two roles differ and the manual approval is the real control."""
    svc = ExportService(conn)
    request = svc.create_request(
        actor=operator.username,
        filters=ExportFilters(),
        reason="report finale",
        kind="report",
    )
    svc.approve(actor=operator.username, request_id=request.id)
    approved = svc.get(request_id=request.id)
    assert approved is not None
    return approved
