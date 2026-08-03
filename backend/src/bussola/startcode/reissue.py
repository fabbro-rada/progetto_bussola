"""Supervisor re-issue of a first-interview start_code (§6/§7.3, follow-up A1).

Recovery path for a lost or expired start_code. The matricola is UNIQUE in the
identity register, so an operator cannot simply re-provision it (that 409s).
Only the supervisor (`Permission.DEANONYMIZE`) may cross the register to find
the pseudonym behind a matricola; this re-issues a fresh start_code on the
EXISTING pseudonym — but ONLY while the profile is still empty (the interview
never ran). Once the interview has produced any content, re-issuing a
first-interview code would risk overwriting it, so this refuses
(`InterviewAlreadyStarted`) and the returning person is handled via the
follow-up flow instead.

Never returns the pseudonym: the supervisor gets only the new code, to hand to
the operator/person. The matricola->pseudonym resolution is audited
(`identity_resolved`, via `IdentityService`) and the re-issue itself is audited
(`start_code_reissued`). No commit here — the caller owns the transaction, so
both audit records and the code INSERT commit atomically (and are rolled back
together if the caller refuses on `InterviewAlreadyStarted`).
"""

from __future__ import annotations

from collections.abc import Callable

import psycopg

from bussola.data.profiles import get_profile, is_contentless
from bussola.identity.service import IdentityService
from bussola.startcode.errors import InterviewAlreadyStarted, MatricolaNotProvisioned
from bussola.startcode.service import StartCodeService

AuditFn = Callable[..., None]


def reissue_start_code(
    conn: psycopg.Connection,
    matricola: str,
    *,
    actor: str,
    audit: AuditFn | None = None,
) -> str:
    """Mint and return a fresh start_code for the (still-empty) profile behind
    ``matricola``. Raises ``MatricolaNotProvisioned`` if the matricola is not in
    the register, ``InterviewAlreadyStarted`` if its profile already has
    content."""
    pseudonym = IdentityService(conn, audit=audit).resolve_matricola(matricola, actor=actor)
    if pseudonym is None:
        raise MatricolaNotProvisioned(matricola)
    profile = get_profile(conn, pseudonym)
    if profile is None or not is_contentless(profile):
        raise InterviewAlreadyStarted(pseudonym)
    code = StartCodeService(conn).issue(pseudonym)
    if audit is not None:
        audit(action="start_code_reissued", actor=actor, target_pseudonym=pseudonym)
    return code
