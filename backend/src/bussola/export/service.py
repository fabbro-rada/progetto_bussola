"""Export-request workflow: create → approve/deny → download (on-demand).

State transitions and their audit records commit in ONE transaction
(pattern S5). The `kind` column (default 'profiles') discriminates what the
download materializes: `kind='profiles'` re-runs the profile search — no
payload is ever stored (minimization, §5/§7.3); `kind='report'` recomputes
the aggregate/anonymous report on demand instead. The state machine itself
(pending → approved/denied, ownership, audit) stays kind-agnostic — only
`generate_payload`'s materialization step branches on it."""

from __future__ import annotations

from typing import Any

import psycopg

from bussola.data.audit import append_audit
from bussola.data.profiles import ProfileRepository
from bussola.export.errors import ExportNotApproved, ExportNotFound, ExportNotPending
from bussola.export.models import ExportFilters, ExportRequest
from bussola.guardrails.pii import PiiRedactor
from bussola.profile.models import WorkProfile
from bussola.report.models import Report
from bussola.report.service import compute_report

_COLUMNS = (
    "id, requested_by, filters, reason, status, "
    "decided_by, decided_at, decision_reason, created_at, kind"
)


def _row_to_request(row: tuple[Any, ...]) -> ExportRequest:
    return ExportRequest(
        id=row[0],
        requested_by=row[1],
        filters=ExportFilters.model_validate(row[2]),
        reason=row[3],
        status=row[4],
        decided_by=row[5],
        decided_at=row[6],
        decision_reason=row[7],
        created_at=row[8],
        kind=row[9],
    )


def _applied_filter_names(filters: ExportFilters) -> str:
    return ",".join(
        name
        for name, value in (
            ("availability", filters.availability),
            ("language", filters.language),
            ("note", filters.note),
            ("skill_query", filters.skill_query),
        )
        if value is not None
    )


class ExportService:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create_request(
        self, *, actor: str, filters: ExportFilters, reason: str, kind: str = "profiles"
    ) -> ExportRequest:
        from psycopg.types.json import Jsonb

        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO export.export_request (requested_by, filters, reason, kind) "
                "VALUES (%s, %s, %s, %s) RETURNING " + _COLUMNS,
                (actor, Jsonb(filters.model_dump(mode="json", exclude_none=True)), reason, kind),
            )
            row = cur.fetchone()
        assert row is not None
        append_audit(
            self._conn,
            action="export_requested",
            actor=actor,
            details={"filters": _applied_filter_names(filters)},
            commit=False,
        )
        self._conn.commit()
        return _row_to_request(row)

    def get(self, *, request_id: int) -> ExportRequest | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT " + _COLUMNS + " FROM export.export_request WHERE id = %s",
                (request_id,),
            )
            row = cur.fetchone()
        return _row_to_request(row) if row is not None else None

    def list_own(self, *, actor: str) -> list[ExportRequest]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT " + _COLUMNS + " FROM export.export_request "
                "WHERE requested_by = %s ORDER BY created_at DESC, id DESC",
                (actor,),
            )
            rows = cur.fetchall()
        return [_row_to_request(r) for r in rows]

    def list_pending(self) -> list[ExportRequest]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT " + _COLUMNS + " FROM export.export_request "
                "WHERE status = 'pending' ORDER BY created_at ASC, id ASC"
            )
            rows = cur.fetchall()
        return [_row_to_request(r) for r in rows]

    def approve(self, *, actor: str, request_id: int) -> None:
        self._decide(actor=actor, request_id=request_id, status="approved", reason=None)

    def deny(self, *, actor: str, request_id: int, reason: str) -> None:
        self._decide(actor=actor, request_id=request_id, status="denied", reason=reason)

    def _decide(self, *, actor: str, request_id: int, status: str, reason: str | None) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE export.export_request "
                "SET status = %s, decided_by = %s, decided_at = now(), decision_reason = %s "
                "WHERE id = %s AND status = 'pending'",
                (status, actor, reason, request_id),
            )
            if cur.rowcount == 0:
                cur.execute("SELECT 1 FROM export.export_request WHERE id = %s", (request_id,))
                if cur.fetchone() is None:
                    raise ExportNotFound(str(request_id))
                raise ExportNotPending(str(request_id))
        append_audit(
            self._conn,
            action=("export_approved" if status == "approved" else "export_denied"),
            actor=actor,
            details={"request_id": str(request_id)},
            commit=False,
        )
        self._conn.commit()

    def peek_kind(self, *, request_id: int) -> str | None:
        """The request's `kind`, or None if it doesn't exist.

        Used by the download route to pick the permission required
        BEFORE the approved+ownership gate below: a `kind='report'`
        request needs APPROVE_EXPORTS, not EXPORT_DATA (the supervisor
        must never gain EXPORT_DATA, which would open raw-profile
        export — §2/§6). Read-only, no audit: revealing a bare `kind`
        string carries no profile data.
        """
        with self._conn.cursor() as cur:
            cur.execute("SELECT kind FROM export.export_request WHERE id = %s", (request_id,))
            row = cur.fetchone()
        return row[0] if row else None

    def generate_payload(self, *, actor: str, request_id: int) -> list[WorkProfile] | Report:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT requested_by, filters, status, kind FROM export.export_request WHERE id = %s",
                (request_id,),
            )
            row = cur.fetchone()
        if row is None or row[0] != actor:
            raise ExportNotFound(str(request_id))
        if row[2] != "approved":
            raise ExportNotApproved(str(request_id))
        if row[3] == "report":
            report = compute_report(self._conn)
            append_audit(
                self._conn,
                action="export_downloaded",
                actor=actor,
                details={"request_id": str(request_id), "kind": "report"},
            )
            return report
        filters = ExportFilters.model_validate(row[1])
        profiles = ProfileRepository(self._conn, PiiRedactor()).search(
            availability=filters.availability,
            language=filters.language,
            note=filters.note,
            skill_query=filters.skill_query,
        )
        append_audit(
            self._conn,
            action="export_downloaded",
            actor=actor,
            details={
                "request_id": str(request_id),
                "filters": _applied_filter_names(filters),
                "count": str(len(profiles)),
            },
        )
        return profiles
