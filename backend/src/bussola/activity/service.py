"""Operator-activity summary for the supervisor (§6): aggregate work-action
counts per actor from the audit log. Aggregate + staff-only, no PII (§2)."""

from __future__ import annotations

from datetime import datetime

import psycopg
from pydantic import BaseModel, ConfigDict

# Work actions counted as operator activity. These are operator-exclusive by
# RBAC (READ_PROFILES / RUN_MATCHING / EXPORT_DATA) — the classification is by
# ACTION, not by the actor's role, so keep this list to operator-only actions:
# granting any of these permissions to another role would surface it here.
_WORK_ACTIONS = (
    "profile_viewed",
    "profiles_searched",
    "matching_run",
    "export_requested",
    "export_downloaded",
)


class OperatorActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str
    profiles_viewed: int
    profiles_searched: int
    matchings_run: int
    exports_requested: int
    exports_downloaded: int
    last_active: datetime


def compute_operator_activity(conn: psycopg.Connection) -> list[OperatorActivity]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT actor, "
            "COUNT(*) FILTER (WHERE action = 'profile_viewed'), "
            "COUNT(*) FILTER (WHERE action = 'profiles_searched'), "
            "COUNT(*) FILTER (WHERE action = 'matching_run'), "
            "COUNT(*) FILTER (WHERE action = 'export_requested'), "
            "COUNT(*) FILTER (WHERE action = 'export_downloaded'), "
            "MAX(occurred_at) "
            "FROM audit.audit_log "
            "WHERE actor IS NOT NULL AND action = ANY(%s) "
            "GROUP BY actor "
            "ORDER BY MAX(occurred_at) DESC",
            (list(_WORK_ACTIONS),),
        )
        rows = cur.fetchall()
    return [
        OperatorActivity(
            actor=r[0],
            profiles_viewed=int(r[1]),
            profiles_searched=int(r[2]),
            matchings_run=int(r[3]),
            exports_requested=int(r[4]),
            exports_downloaded=int(r[5]),
            last_active=r[6],
        )
        for r in rows
    ]
