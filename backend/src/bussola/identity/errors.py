"""Errors raised by the identity register service (§5/§6)."""

from __future__ import annotations


class MatricolaAlreadyLinked(Exception):
    """A profile already exists for this matricola (use follow-up to update it)."""
