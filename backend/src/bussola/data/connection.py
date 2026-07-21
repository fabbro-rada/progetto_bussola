"""Thin psycopg3 connection helper."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from bussola.data import config


@contextmanager
def connect(role: str, dbname: str | None = None) -> Iterator[psycopg.Connection]:
    """Open a connection for the given role; close it on exit."""
    conn = psycopg.connect(config.dsn(role, dbname))
    try:
        yield conn
    finally:
        conn.close()
