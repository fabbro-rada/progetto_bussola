"""Persist ONLY aggregate matching outcomes (per run): counts + gap frequencies.
Never a pseudonym or a per-person row (§5 minimization; avoids §2 profiling)."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb


def record_match_run(
    conn: psycopg.Connection,
    *,
    job_request_id: int,
    evaluated_count: int,
    compatible_count: int,
    gaps: dict[str, int],
) -> None:
    """Insert one aggregate row for a matching run (no commit — the caller commits,
    so this shares the caller's transaction, e.g. together with the audit entry)."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO matching.match_run "
            "(job_request_id, evaluated_count, compatible_count, gaps) VALUES (%s, %s, %s, %s)",
            (job_request_id, evaluated_count, compatible_count, Jsonb(gaps)),
        )
