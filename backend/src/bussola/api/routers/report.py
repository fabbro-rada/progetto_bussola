"""Aggregate/anonymous report endpoint (supervisor role). §2/§7.2/§7.3."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
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
