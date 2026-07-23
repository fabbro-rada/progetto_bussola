"""Matching endpoint (operator role)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.guardrails.pii import PiiRedactor
from bussola.llm.client import HttpxLlmClient
from bussola.matching.models import MatchResult
from bussola.matching.service import MatchingService

router = APIRouter(prefix="/job-requests", tags=["matching"])
_run = require_permission(Permission.RUN_MATCHING)


@router.post("/{job_id}/match", response_model=list[MatchResult])
def run_match(
    job_id: int,
    operator: Operator = Depends(_run),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[MatchResult]:
    def audit(**kw: object) -> None:
        append_audit(conn, commit=False, **kw)  # type: ignore[arg-type]

    service = MatchingService(conn, HttpxLlmClient(), PiiRedactor(), audit=audit)
    return service.match(job_id, actor=operator.username)
