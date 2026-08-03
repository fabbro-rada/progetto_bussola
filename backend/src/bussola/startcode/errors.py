"""Errors for the supervisor start-code re-issue (follow-up A1)."""

from __future__ import annotations


class MatricolaNotProvisioned(Exception):
    """No pseudonym is linked to this matricola — nothing to re-issue for."""


class InterviewAlreadyStarted(Exception):
    """The profile already has content, so a FIRST-interview start_code must not
    be re-issued (it could overwrite what the interview produced). The returning
    person is handled via the follow-up flow instead."""
