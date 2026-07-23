"""Data-layer test marker.

The database FIXTURES now live in the shared `tests/conftest.py` (reused by
the interview live test too). This module keeps only the `requires_db`
collection marker, which the data-layer test modules import directly
(`from .conftest import requires_db`) to skip at collection time when Postgres
is not running.
"""

from __future__ import annotations

import psycopg
import pytest

from bussola.data import config


def _server_reachable() -> bool:
    try:
        with psycopg.connect(config.dsn("superuser", dbname="postgres"), connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _server_reachable(),
    reason="Postgres non raggiungibile (avvia: docker compose up -d db)",
)
