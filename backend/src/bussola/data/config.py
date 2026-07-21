"""Database connection configuration, from environment with dev-only defaults.

The defaults match docker-compose.yml so tests run out-of-the-box against a
local Postgres. In production every value is overridden via environment
variables; passwords are never committed.
"""

from __future__ import annotations

import os

_HOST = os.environ.get("BUSSOLA_DB_HOST", "127.0.0.1")
_PORT = os.environ.get("BUSSOLA_DB_PORT", "5432")
_DBNAME = os.environ.get("BUSSOLA_DB_NAME", "bussola")

# role -> (db user, password env var, dev-only default password)
_ROLES = {
    "owner": ("bussola_owner", "BUSSOLA_OWNER_PASSWORD", "owner_dev"),
    "app": ("bussola_app", "BUSSOLA_APP_PASSWORD", "app_dev"),
    "auditor": ("bussola_auditor", "BUSSOLA_AUDITOR_PASSWORD", "auditor_dev"),
    "superuser": ("postgres", "POSTGRES_SUPERUSER_PASSWORD", "postgres_dev"),
}


def dsn(role: str, dbname: str | None = None) -> str:
    """Build a libpq connection string for the given role."""
    if role not in _ROLES:
        raise ValueError(f"unknown role: {role!r}")
    user, env_key, default = _ROLES[role]
    password = os.environ.get(env_key, default)
    database = dbname or _DBNAME
    return f"host={_HOST} port={_PORT} dbname={database} user={user} password={password}"
