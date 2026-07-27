"""Operator-activity endpoint (supervisor role). Aggregate + staff-only (§2/§6)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from bussola.activity.service import OperatorActivity, compute_operator_activity
from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit

router = APIRouter(prefix="/operator-activity", tags=["activity"])
_view = require_permission(Permission.VIEW_OPERATOR_ACTIVITY)


@router.get("", response_model=list[OperatorActivity])
def get_operator_activity(
    operator: Operator = Depends(_view),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[OperatorActivity]:
    activity = compute_operator_activity(conn)
    append_audit(conn, action="operator_activity_viewed", actor=operator.username, target_pseudonym=None)
    return activity
