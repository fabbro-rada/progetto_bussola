"""Audit-log read endpoints (Auditor role, READ_AUDIT). Read-only: these
endpoints never append to the log (§6 — the auditor modifies nothing)."""

from __future__ import annotations

from datetime import datetime

import psycopg
from fastapi import APIRouter, Depends, Query

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import AuditEntry, VerificationResult, list_audit, verify_audit_chain

router = APIRouter(prefix="/audit", tags=["audit"])
_read = require_permission(Permission.READ_AUDIT)


@router.get("", response_model=list[AuditEntry])
def read_audit(
    before: int | None = None,
    limit: int = 50,
    actor: str | None = None,
    action: str | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    operator: Operator = Depends(_read),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[AuditEntry]:
    return list_audit(
        conn, before=before, limit=limit, actor=actor, action=action, from_ts=from_, to_ts=to
    )


@router.get("/verify", response_model=VerificationResult)
def verify(
    operator: Operator = Depends(_read),
    conn: psycopg.Connection = Depends(get_conn),
) -> VerificationResult:
    return verify_audit_chain(conn)
