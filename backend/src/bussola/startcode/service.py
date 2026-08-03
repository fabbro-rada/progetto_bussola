"""One-time, expiring start-codes (§5/§7.3): launch a FIRST interview on a
pre-created (empty) pseudonym without ever collecting identity/anagraphic
data during the interview itself. Directly mirrors
`bussola.followup.service.FollowupTokenService`: only the SHA-256 hash of
the opaque code is stored (`auth.sessions.hash_token`), so a DB leak cannot
hand out live codes.

`issue` mints the cleartext code once and returns it (shown to the operator
exactly once when provisioning a pseudonym; never persisted). No commit
here — the caller commits, so the INSERT and its audit record (the
provisioning endpoint audits the identity link, not this service) share one
transaction.

`consume` redeems a code exactly once: a single atomic UPDATE guarded by
`code_hash` + `used_at IS NULL` + `expires_at > now()` marks it used and
returns the pseudonym in the same statement. An unknown, already-used or
expired code fails closed to None — never raises."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import psycopg

from bussola.auth.sessions import hash_token


class StartCodeService:
    def __init__(
        self,
        conn: psycopg.Connection,
        *,
        ttl_seconds: int = 86400,
    ) -> None:
        self._conn = conn
        self._ttl_seconds = ttl_seconds

    def issue(self, pseudonym_id: str) -> str:
        code = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self._ttl_seconds)
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO startcode.start_code "
                "(code_hash, pseudonym_id, created_at, expires_at) "
                "VALUES (%s, %s, %s, %s)",
                (hash_token(code), pseudonym_id, now, expires_at),
            )
        return code

    def consume(self, code: str) -> str | None:
        now = datetime.now(timezone.utc)
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE startcode.start_code SET used_at = %s "
                "WHERE code_hash = %s AND used_at IS NULL AND expires_at > %s "
                "RETURNING pseudonym_id",
                (now, hash_token(code), now),
            )
            row = cur.fetchone()
            if cur.rowcount != 1 or row is None:
                return None
            return str(row[0])
