"""Follow-up token provisioning (operator role, Fase 2·A).

Issues a one-time token that re-links a returning person to their
pseudonymized profile (§5/§7.3) — never any identity/anagraphic data. The
INSERT (inside the service) and its `followup_provisioned` audit record
commit atomically in one transaction (pattern S5): the audit closure passes
`commit=False` and this router commits once, after `issue()` returns."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.followup.service import FollowupTokenService

router = APIRouter(prefix="/followups", tags=["followups"])
_provision = require_permission(Permission.PROVISION_FOLLOWUP)


class ProvisionFollowupBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pseudonym_id: str


class ProvisionFollowupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProvisionFollowupResponse)
def provision_followup(
    body: ProvisionFollowupBody,
    operator: Operator = Depends(_provision),
    conn: psycopg.Connection = Depends(get_conn),
) -> ProvisionFollowupResponse:
    def audit(**kw: object) -> None:
        append_audit(conn, commit=False, **kw)  # type: ignore[arg-type]

    token = FollowupTokenService(conn, audit=audit).issue(body.pseudonym_id, actor=operator.username)
    conn.commit()
    return ProvisionFollowupResponse(token=token)
