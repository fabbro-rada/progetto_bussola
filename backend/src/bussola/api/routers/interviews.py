"""Operator provisioning of a first interview (§5/§6/§7.2, Task 6).

An operator enters a `matricola`; this endpoint creates an empty work
profile under a fresh pseudonym, links pseudonym<->matricola in the
segregated identity register (`bussola.identity.service.IdentityService`),
and mints a one-time `start_code` that lets the person begin their
interview on a kiosk without ever typing identity data there. The response
returns ONLY the start_code — the pseudonym is never exposed to the caller,
by construction (§2/§5: operators never see the person's identity).

`create_empty_profile` is called directly (module-level function), NOT
`ProfileRepository.create_new()`: using the latter would first require
constructing a `ProfileRepository`, whose constructor takes a `PiiRedactor`
(loads spaCy) — a cost this operator-facing path has no reason to pay.

Atomic-audit idiom (mirrors `bussola.api.routers.followups`): the profile
creation, the identity link + its `identity_link_created` audit record, and
the start-code issuance all share one transaction. `IdentityService.link`
and `append_audit(commit=False)` never commit; this router commits once, at
the end. On `MatricolaAlreadyLinked` (duplicate matricola -> 409) the
transaction is rolled back instead of committed, so the profile created
earlier in the same transaction is discarded too.
"""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.data.profiles import create_empty_profile
from bussola.identity.errors import MatricolaAlreadyLinked
from bussola.identity.service import IdentityService
from bussola.startcode.service import StartCodeService

router = APIRouter(prefix="/interviews", tags=["interviews"])
_provision = require_permission(Permission.PROVISION_INTERVIEW)


class ProvisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matricola: str


class ProvisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_code: str


@router.post("/provision", status_code=status.HTTP_201_CREATED, response_model=ProvisionResponse)
def provision_interview(
    body: ProvisionBody,
    operator: Operator = Depends(_provision),
    conn: psycopg.Connection = Depends(get_conn),
) -> ProvisionResponse:
    pseudonym = create_empty_profile(conn)

    def audit(**kw: object) -> None:
        append_audit(conn, commit=False, **kw)  # type: ignore[arg-type]

    try:
        IdentityService(conn, audit=audit).link(pseudonym, body.matricola, actor=operator.username)
    except MatricolaAlreadyLinked:
        conn.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "a profile already exists for this matricola")
    code = StartCodeService(conn).issue(pseudonym)
    conn.commit()
    return ProvisionResponse(start_code=code)  # pseudonym intentionally NOT returned
