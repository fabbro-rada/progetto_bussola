"""Database connection configuration, from environment with dev-only defaults.

The defaults match docker-compose.yml so tests run out-of-the-box against a
local Postgres. In production every value is overridden via environment
variables; passwords are never committed.

A minimal, dependency-free ``.env`` loader runs at import time, before the
module reads any connection setting, so ``.env`` is the single source of
host configuration for both ``docker compose`` (which auto-reads ``.env``)
and this Python process (e.g. pytest). Real environment variables always
take precedence over ``.env`` values.
"""

from __future__ import annotations

import os

from psycopg.conninfo import make_conninfo

from bussola.env import load_project_dotenv

load_project_dotenv()

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
    """Build a libpq connection string for the given role.

    Uses psycopg's ``make_conninfo`` rather than raw string interpolation so
    values containing spaces or quotes (e.g. a real production password) are
    quoted/escaped correctly instead of producing a malformed DSN.
    """
    if role not in _ROLES:
        raise ValueError(f"unknown role: {role!r}")
    user, env_key, default = _ROLES[role]
    password = os.environ.get(env_key, default)
    database = dbname or _DBNAME
    return make_conninfo(host=_HOST, port=_PORT, dbname=database, user=user, password=password)
