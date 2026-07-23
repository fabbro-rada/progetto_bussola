"""Profile consultation endpoints (operator role)."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from bussola.api.deps import get_conn, require_permission
from bussola.auth.models import Operator
from bussola.auth.rbac import Permission
from bussola.data.audit import append_audit
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.enums import Availability, OperationalNoteCategory
from bussola.profile.models import WorkProfile

router = APIRouter(prefix="/profiles", tags=["profiles"])
_read = require_permission(Permission.READ_PROFILES)


@router.get("", response_model=list[WorkProfile])
def search_profiles(
    availability: Availability | None = None,
    language: str | None = None,
    note: OperationalNoteCategory | None = None,
    skill_query: str | None = None,
    operator: Operator = Depends(_read),
    conn: psycopg.Connection = Depends(get_conn),
) -> list[WorkProfile]:
    results = ProfileRepository(conn, PiiRedactor()).search(
        availability=availability, language=language, note=note, skill_query=skill_query
    )
    # §6/§7.3: bulk enumeration is the most obvious misuse vector, so it must be
    # traceable — audit the applied filter *names* and result count only, never
    # any profile/PII data.
    applied = [
        name
        for name, value in (
            ("availability", availability),
            ("language", language),
            ("note", note),
            ("skill_query", skill_query),
        )
        if value is not None
    ]
    append_audit(
        conn,
        action="profiles_searched",
        actor=operator.username,
        details={"filters": ",".join(applied), "results": str(len(results))},
        target_pseudonym=None,
    )
    return results


@router.get("/{pseudonym}", response_model=WorkProfile)
def get_profile(
    pseudonym: str,
    operator: Operator = Depends(_read),
    conn: psycopg.Connection = Depends(get_conn),
) -> WorkProfile:
    profile = ProfileRepository(conn, PiiRedactor()).get(pseudonym)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile not found")
    append_audit(conn, action="profile_viewed", actor=operator.username, target_pseudonym=pseudonym)
    return profile
