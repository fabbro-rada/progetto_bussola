"""Constrained audit for auth events (§7.3). Details are a strict whitelist
(operator usernames + role only) — never free text or personal data. Appended
within the caller's transaction so the account change and its record are atomic."""

from __future__ import annotations

import psycopg

from bussola.data.audit import append_audit

# Fixed vocabulary of auth actions.
LOGIN_SUCCEEDED = "login_succeeded"
LOGIN_FAILED = "login_failed"
LOGOUT = "logout"
PASSWORD_CHANGED = "password_changed"
OPERATOR_CREATED = "operator_created"
OPERATOR_DISABLED = "operator_disabled"
OPERATOR_ENABLED = "operator_enabled"
OPERATOR_PASSWORD_RESET = "operator_password_reset"


def record_auth_event(
    conn: psycopg.Connection,
    *,
    action: str,
    actor: str | None,
    target_operator: str | None = None,
    role: str | None = None,
) -> None:
    details: dict[str, str] = {}
    if target_operator is not None:
        details["target_operator"] = target_operator
    if role is not None:
        details["role"] = role
    append_audit(
        conn,
        action=action,
        actor=actor,
        target_pseudonym=None,
        details=details,
        commit=False,
    )
