"""Opaque pseudonym generation.

The pseudonym is the ONLY identifier inside the work profile. The link between a
pseudonym and a real person (matricola) lives in a SEPARATE, segregated register
(schema `identity`), readable only by the supervisor role and fully audited (§5/§6/§7.3).
"""

from __future__ import annotations

import secrets

_PREFIX = "P-"


def generate_pseudonym() -> str:
    """Return a new opaque, unguessable pseudonym (e.g. 'P-a1b2c3...')."""
    return _PREFIX + secrets.token_hex(8)  # 'P-' + 16 hex chars = 18 chars
