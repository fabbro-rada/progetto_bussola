"""Append-only, tamper-evident audit log (hash-chained)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict

_CHAIN_LOCK_KEY = 4242  # advisory-lock key serializing audit appends


def _record_hash(
    occurred_at: datetime,
    actor: str | None,
    action: str,
    target_pseudonym: str | None,
    details: dict[str, Any],
    prev_hash: str | None,
) -> str:
    canonical = json.dumps(
        {
            "occurred_at": occurred_at.astimezone(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "target_pseudonym": target_pseudonym,
            "details": details,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_audit(
    conn: psycopg.Connection,
    *,
    action: str,
    actor: str | None = None,
    target_pseudonym: str | None = None,
    details: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    """Append one audit record, chained to the previous one.

    When ``commit`` is False the record is appended within the caller's
    transaction (no own commit), so an operation and its audit record commit
    atomically together.
    """
    payload = details or {}
    occurred_at = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_CHAIN_LOCK_KEY,))
        cur.execute("SELECT record_hash FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        prev_hash = row[0] if row is not None else None
        record_hash = _record_hash(occurred_at, actor, action, target_pseudonym, payload, prev_hash)
        cur.execute(
            "INSERT INTO audit.audit_log "
            "(occurred_at, actor, action, target_pseudonym, details, prev_hash, record_hash) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (occurred_at, actor, action, target_pseudonym, Jsonb(payload), prev_hash, record_hash),
        )
    if commit:
        conn.commit()


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    broken_at: int | None = None
    reason: str | None = None


def verify_audit_chain(conn: psycopg.Connection) -> VerificationResult:
    """Walk the chain in id order; report the first record that breaks it."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, occurred_at, actor, action, target_pseudonym, details, prev_hash, record_hash "
            "FROM audit.audit_log ORDER BY id ASC"
        )
        rows = cur.fetchall()

    expected_prev: str | None = None
    for rid, occurred_at, actor, action, target, details, prev_hash, record_hash in rows:
        if prev_hash != expected_prev:
            return VerificationResult(ok=False, broken_at=rid, reason="prev_hash mismatch")
        if _record_hash(occurred_at, actor, action, target, details, prev_hash) != record_hash:
            return VerificationResult(ok=False, broken_at=rid, reason="record_hash mismatch")
        expected_prev = record_hash
    return VerificationResult(ok=True)


class AuditEntry(BaseModel):
    """Read-only view of one audit row (hashes are internal, not exposed)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    occurred_at: datetime
    actor: str | None
    action: str
    target_pseudonym: str | None
    details: dict[str, Any]


def list_audit(
    conn: psycopg.Connection,
    *,
    before: int | None = None,
    limit: int = 50,
    actor: str | None = None,
    action: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> list[AuditEntry]:
    """Read audit entries, newest first, id-cursor paginated. Read-only."""
    capped = max(1, min(limit, 200))
    clauses: list[str] = []
    params: list[object] = []
    if before is not None:
        clauses.append("id < %s")
        params.append(before)
    if actor is not None:
        clauses.append("actor = %s")
        params.append(actor)
    if action is not None:
        clauses.append("action = %s")
        params.append(action)
    if from_ts is not None:
        clauses.append("occurred_at >= %s")
        params.append(from_ts)
    if to_ts is not None:
        clauses.append("occurred_at <= %s")
        params.append(to_ts)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(capped)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, occurred_at, actor, action, target_pseudonym, details "
            "FROM audit.audit_log" + where + " ORDER BY id DESC LIMIT %s",
            params,
        )
        rows = cur.fetchall()
    return [
        AuditEntry(
            id=r[0], occurred_at=r[1], actor=r[2], action=r[3], target_pseudonym=r[4], details=r[5]
        )
        for r in rows
    ]
