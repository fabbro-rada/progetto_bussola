"""In-memory registry of live interview sessions. Each session owns resources
(e.g. a DB connection) closed via `on_evict` when the session ends, expires
(TTL since last activity), or is discarded. Single-process (one kiosk); not
multi-worker (Fase 2)."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _noop() -> None:
    return None


@dataclass
class _Entry:
    value: object
    on_evict: Callable[[], None]
    last_seen: datetime


class InterviewRegistry:
    def __init__(self, *, ttl_seconds: int, now: Callable[[], datetime] | None = None) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._now = now or _utcnow
        self._entries: dict[str, _Entry] = {}

    def _sweep(self) -> None:
        cutoff = self._now() - self._ttl
        for token in [t for t, e in self._entries.items() if e.last_seen < cutoff]:
            self._entries.pop(token).on_evict()

    def create(self, value: object, on_evict: Callable[[], None] = _noop) -> str:
        self._sweep()
        token = secrets.token_urlsafe(32)
        self._entries[token] = _Entry(value=value, on_evict=on_evict, last_seen=self._now())
        return token

    def get(self, token: str) -> object | None:
        self._sweep()
        entry = self._entries.get(token)
        if entry is None:
            return None
        entry.last_seen = self._now()
        return entry.value

    def discard(self, token: str) -> None:
        entry = self._entries.pop(token, None)
        if entry is not None:
            entry.on_evict()

    def active_count(self) -> int:
        self._sweep()
        return len(self._entries)
