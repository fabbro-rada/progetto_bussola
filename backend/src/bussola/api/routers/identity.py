"""Supervisor-only, audited de-anonymization (§6/§7.3, Task 7).

Only `Role.SUPERVISOR` holds `Permission.DEANONYMIZE`: resolving a
pseudonym to its matricola (for match delivery) or a matricola to its
pseudonym (for follow-up targeting) is the one place the segregated
pseudonym<->matricola register (`bussola.identity.service.IdentityService`)
is deliberately crossed by a human. Every successful resolution audits
`identity_resolved`; an unknown pseudonym/matricola is never audited
(nothing was resolved).

Atomic-audit idiom (mirrors `bussola.api.routers.followups`/`interviews`):
the audit closure passes `commit=False` and this router commits once, after
all resolutions for the request have been attempted.
"""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.identity.service import IdentityService

router = APIRouter(prefix="/identity", tags=["identity"])
_resolve = require_permission(Permission.DEANONYMIZE)


class ResolveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pseudonym_ids: list[str]


class ResolveItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pseudonym_id: str
    matricola: str


class ResolveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[ResolveItem]


class ResolveMatricolaBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matricola: str


class ResolveMatricolaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pseudonym_id: str


@router.post("/resolve", response_model=ResolveResponse)
def resolve(
    body: ResolveBody,
    operator: Operator = Depends(_resolve),
    conn: psycopg.Connection = Depends(get_conn),
) -> ResolveResponse:
    def audit(**kw: object) -> None:
        append_audit(conn, commit=False, **kw)  # type: ignore[arg-type]

    svc = IdentityService(conn, audit=audit)
    items = []
    for pseudonym_id in body.pseudonym_ids:
        matricola = svc.resolve(pseudonym_id, actor=operator.username)
        if matricola is not None:
            items.append(ResolveItem(pseudonym_id=pseudonym_id, matricola=matricola))
    conn.commit()
    return ResolveResponse(results=items)


@router.post("/resolve-matricola", response_model=ResolveMatricolaResponse)
def resolve_matricola(
    body: ResolveMatricolaBody,
    operator: Operator = Depends(_resolve),
    conn: psycopg.Connection = Depends(get_conn),
) -> ResolveMatricolaResponse:
    def audit(**kw: object) -> None:
        append_audit(conn, commit=False, **kw)  # type: ignore[arg-type]

    pseudonym_id = IdentityService(conn, audit=audit).resolve_matricola(
        body.matricola, actor=operator.username
    )
    if pseudonym_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no profile for this matricola")
    conn.commit()
    return ResolveMatricolaResponse(pseudonym_id=pseudonym_id)
