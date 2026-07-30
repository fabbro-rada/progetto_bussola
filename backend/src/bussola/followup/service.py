"""One-time follow-up interview tokens (§5/§7.3): re-link a returning person to
their pseudonymized profile without ever storing identity/anagraphic data.
Only the SHA-256 hash of the opaque token is stored (mirrors
`auth.sessions.hash_token`), so a DB leak cannot hand out live tokens.

`issue` mints the cleartext token once and returns it (shown to the operator
exactly once; never persisted). No commit here — the caller commits, so the
INSERT and its audit record share one transaction (like other services).

`consume` redeems a token exactly once: a single atomic UPDATE guarded by
`token_hash` + `used_at IS NULL` + `expires_at > now()` marks it used and
returns the pseudonym in the same statement. An unknown, already-used or
expired token fails closed to None — never raises. Because the guard lives
in the UPDATE's WHERE clause, two concurrent `consume` calls for the same
token race for the row lock: only the one that commits first can flip
`used_at`, so the loser's `rowcount` is 0 and it correctly gets None."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import psycopg

from bussola.auth.sessions import hash_token

AuditFn = Callable[..., None]


class FollowupTokenService:
    def __init__(
        self,
        conn: psycopg.Connection,
        *,
        ttl_seconds: int = 86400,
        audit: AuditFn | None = None,
    ) -> None:
        self._conn = conn
        self._ttl_seconds = ttl_seconds
        self._audit = audit

    def issue(self, pseudonym_id: str, *, actor: str) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self._ttl_seconds)
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO followup.followup_token "
                "(token_hash, pseudonym_id, created_at, expires_at) "
                "VALUES (%s, %s, %s, %s)",
                (hash_token(token), pseudonym_id, now, expires_at),
            )
        if self._audit is not None:
            self._audit(
                action="followup_provisioned",
                actor=actor,
                target_pseudonym=pseudonym_id,
            )
        return token

    def consume(self, token: str) -> str | None:
        now = datetime.now(timezone.utc)
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE followup.followup_token SET used_at = %s "
                "WHERE token_hash = %s AND used_at IS NULL AND expires_at > %s "
                "RETURNING pseudonym_id",
                (now, hash_token(token), now),
            )
            row = cur.fetchone()
            if cur.rowcount != 1 or row is None:
                return None
            return str(row[0])
