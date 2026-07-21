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
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Load ``KEY=VALUE`` pairs from `path` into ``os.environ``.

    Blank lines and lines starting with ``#`` are ignored. Surrounding single
    or double quotes on the value are stripped. Existing environment
    variables are never overridden: the real environment always wins over
    ``.env``. A missing (or otherwise unreadable) file is a no-op; this
    function never raises.
    """
    try:
        contents = path.read_text(encoding="utf-8")
    except OSError:
        return

    for line in contents.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _find_dotenv(start: Path) -> Path | None:
    """Return the first ``.env`` file found walking up from `start` to the root."""
    for directory in (start, *start.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


_dotenv_path = _find_dotenv(Path.cwd())
if _dotenv_path is not None:
    _load_dotenv(_dotenv_path)

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
