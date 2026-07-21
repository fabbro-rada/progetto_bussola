"""Fixtures for data-layer tests. Require a running Postgres:
    docker compose up -d db
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
