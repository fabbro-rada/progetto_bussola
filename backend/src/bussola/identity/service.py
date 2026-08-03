"""Segregated pseudonym <-> matricola register (§5/§6/§7.3).

`identity.pseudonym_identity` is the ONLY link between a work profile's
pseudonym and a real person (matricola). It lives in its own schema, is
reachable only through this service, and every link/resolve is audited so
misuse is traceable (§6: the auditor role has no grant on this schema at
all — absence of grant, not a runtime check here, is the primary guard).

No commit here — the caller owns the transaction (mirrors
`bussola.followup.service.FollowupTokenService`), so a link/resolve and its
audit record commit atomically together with whatever else the caller does.
"""

from __future__ import annotations

from collections.abc import Callable

import psycopg
from psycopg.errors import UniqueViolation

from bussola.identity.errors import MatricolaAlreadyLinked

AuditFn = Callable[..., None]


class IdentityService:
    def __init__(self, conn: psycopg.Connection, *, audit: AuditFn | None = None) -> None:
        self._conn = conn
        self._audit = audit

    def link(self, pseudonym_id: str, matricola: str, *, actor: str) -> None:
        """Link a pseudonym to a matricola.

        Raises ``MatricolaAlreadyLinked`` on the UNIQUE violation (a profile
        already exists for this matricola). Postgres aborts the transaction
        on that error, so the caller must not commit afterwards — it should
        instead surface the conflict (e.g. HTTP 409) without committing.
        """
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO identity.pseudonym_identity "
                    "(pseudonym_id, matricola, created_by) VALUES (%s, %s, %s)",
                    (pseudonym_id, matricola, actor),
                )
        except UniqueViolation as exc:
            raise MatricolaAlreadyLinked(matricola) from exc
        if self._audit is not None:
            self._audit(action="identity_link_created", actor=actor, target_pseudonym=pseudonym_id)

    def resolve(self, pseudonym_id: str, *, actor: str) -> str | None:
        """Resolve a pseudonym to its matricola, or None if unlinked."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT matricola FROM identity.pseudonym_identity WHERE pseudonym_id = %s",
                (pseudonym_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        if self._audit is not None:
            self._audit(action="identity_resolved", actor=actor, target_pseudonym=pseudonym_id)
        return str(row[0])

    def resolve_matricola(self, matricola: str, *, actor: str) -> str | None:
        """Resolve a matricola to its pseudonym, or None if unknown."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT pseudonym_id FROM identity.pseudonym_identity WHERE matricola = %s",
                (matricola,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        pseudonym = str(row[0])
        if self._audit is not None:
            self._audit(action="identity_resolved", actor=actor, target_pseudonym=pseudonym)
        return pseudonym
