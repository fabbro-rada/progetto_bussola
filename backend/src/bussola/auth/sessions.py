"""Server-side sessions. Only the SHA-256 of the opaque token is stored, so a
DB leak cannot hand out live sessions. No internal commit (caller owns the tx)."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import psycopg

from bussola.auth import config


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionStore:
    def __init__(
        self, conn: psycopg.Connection, *, now: Callable[[], datetime] | None = None
    ) -> None:
        self._conn = conn
        self._now = now or _utcnow

    def create(self, operator_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = self._now()
        expires_at = now + timedelta(seconds=config.SESSION_TTL_SECONDS)
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO auth.session (token_hash, operator_id, created_at, expires_at, last_seen_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (hash_token(token), operator_id, now, expires_at, now),
            )
        return token

    def lookup(self, token: str) -> int | None:
        now = self._now()
        idle_cutoff = now - timedelta(seconds=config.SESSION_IDLE_SECONDS)
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, operator_id FROM auth.session "
                "WHERE token_hash = %s AND revoked_at IS NULL "
                "AND expires_at > %s AND last_seen_at > %s",
                (hash_token(token), now, idle_cutoff),
            )
            row = cur.fetchone()
            if row is None:
                return None
            session_id, operator_id = row
            cur.execute(
                "UPDATE auth.session SET last_seen_at = %s WHERE id = %s", (now, session_id)
            )
        return int(operator_id)

    def revoke(self, token: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.session SET revoked_at = %s WHERE token_hash = %s AND revoked_at IS NULL",
                (self._now(), hash_token(token)),
            )

    def revoke_all_for_operator(self, operator_id: int) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.session SET revoked_at = %s WHERE operator_id = %s AND revoked_at IS NULL",
                (self._now(), operator_id),
            )
