"""Opaque pseudonym generation.

The pseudonym is the ONLY identifier of a work profile. The system never
stores the link between a pseudonym and a real person — that register lives
outside the system.
"""

from __future__ import annotations

import secrets

_PREFIX = "P-"


def generate_pseudonym() -> str:
    """Return a new opaque, unguessable pseudonym (e.g. 'P-a1b2c3...')."""
    return _PREFIX + secrets.token_hex(8)  # 'P-' + 16 hex chars = 18 chars
