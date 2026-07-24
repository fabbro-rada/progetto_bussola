"""Kiosk request dependencies. `require_kiosk` gates every person-facing
endpoint with the pre-shared device token (constant-time compare).

Also builds the `Interview` factory used by the interview router: each kiosk
session owns its own DB connection (opened here, closed by the registry's
`on_evict` or explicitly on completion), while the expensive `PiiRedactor` is
shared across sessions (spaCy load cost)."""

from __future__ import annotations

import secrets
from collections.abc import Callable

import psycopg
from fastapi import Header, HTTPException, status

from bussola.api.kiosk import config
from bussola.api.kiosk.session import InterviewRegistry
from bussola.data import config as db_config
from bussola.data.audit import append_audit
from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview
from bussola.llm.client import HttpxLlmClient


def require_kiosk(x_kiosk_token: str | None = Header(default=None)) -> None:
    expected = config.KIOSK_TOKEN
    if not expected or not x_kiosk_token or not secrets.compare_digest(x_kiosk_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "kiosk not authorized")


REGISTRY = InterviewRegistry(ttl_seconds=config.SESSION_TTL)

_redactor: PiiRedactor | None = None


def _shared_redactor() -> PiiRedactor:
    global _redactor
    if _redactor is None:
        _redactor = PiiRedactor()
    return _redactor


def build_interview(language: str) -> tuple[Interview, Callable[[], None]]:
    conn = psycopg.connect(db_config.dsn("app"))
    redactor = _shared_redactor()
    llm = HttpxLlmClient()

    def audit(**kwargs: object) -> None:
        append_audit(conn, actor="kiosk", **kwargs)  # type: ignore[arg-type]

    interview = Interview(
        llm,
        ScopeGuard(llm),
        ProfileRepository(conn, redactor, language),
        language=language,
        redactor=redactor,
        audit=audit,
    )
    return interview, conn.close
