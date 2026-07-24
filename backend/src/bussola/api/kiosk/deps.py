"""Kiosk request dependencies. `require_kiosk` gates every person-facing
endpoint with the pre-shared device token (constant-time compare)."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from bussola.api.kiosk import config


def require_kiosk(x_kiosk_token: str | None = Header(default=None)) -> None:
    expected = config.KIOSK_TOKEN
    if not expected or not x_kiosk_token or not secrets.compare_digest(x_kiosk_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "kiosk not authorized")
