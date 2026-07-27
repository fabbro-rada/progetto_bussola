"""Quality-metrics endpoint (supervisor role). Aggregate + anonymous (§2/§7.2)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.metrics.service import Metrics, compute_metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])
_view = require_permission(Permission.VIEW_METRICS)


@router.get("", response_model=Metrics)
def get_metrics(
    operator: Operator = Depends(_view),
    conn: psycopg.Connection = Depends(get_conn),
) -> Metrics:
    metrics = compute_metrics(conn)
    append_audit(conn, action="metrics_viewed", actor=operator.username, target_pseudonym=None)
    return metrics
