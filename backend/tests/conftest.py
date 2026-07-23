"""Shared test fixtures for the whole `tests/` tree.

Database fixtures live here (rather than under `tests/data/`) so both the
data-layer tests and the interview live-integration test can reuse them.
They require a running Postgres:
    docker compose up -d db

The `requires_db` collection marker stays in `tests/data/conftest.py` (data
tests import it directly); these fixtures instead skip at setup time if the
server is unreachable, so any test that consumes them degrades to a clean
skip regardless of which directory it lives in.
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest

from bussola.data import config
from bussola.data.migrate import apply_migrations

_TEST_DB = "bussola_test"


def _server_reachable() -> bool:
    try:
        with psycopg.connect(config.dsn("superuser", dbname="postgres"), connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def test_database() -> Iterator[None]:
    # Recreate a clean test database owned by bussola_owner.
    if not _server_reachable():
        pytest.skip("Postgres non raggiungibile (avvia: docker compose up -d db)")
    with psycopg.connect(config.dsn("superuser", dbname="postgres")) as su:
        su.autocommit = True
        with su.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (_TEST_DB,),
            )
            cur.execute(f"DROP DATABASE IF EXISTS {_TEST_DB}")
            cur.execute(f"CREATE DATABASE {_TEST_DB} OWNER bussola_owner")
            cur.execute(f"GRANT CONNECT ON DATABASE {_TEST_DB} TO bussola_app, bussola_auditor")
    with psycopg.connect(config.dsn("owner", dbname=_TEST_DB)) as owner:
        apply_migrations(owner)
    yield


@pytest.fixture
def db(test_database: None) -> Iterator[None]:
    # Truncate mutable tables between tests. TRUNCATE bypasses the append-only
    # row trigger, and owner owns the tables. Guarded so it works before the
    # profiles/audit tables exist (Task 3 only has schemas).
    with psycopg.connect(config.dsn("owner", dbname=_TEST_DB)) as owner:
        with owner.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('audit.audit_log'), to_regclass('profiles.work_profile')"
            )
            audit_tbl, profiles_tbl = cur.fetchone()
            if audit_tbl is not None:
                cur.execute("TRUNCATE audit.audit_log RESTART IDENTITY")
            if profiles_tbl is not None:
                cur.execute("TRUNCATE profiles.work_profile")
            cur.execute("SELECT to_regclass('auth.session'), to_regclass('auth.operator')")
            session_tbl, operator_tbl = cur.fetchone()
            if session_tbl is not None:
                cur.execute("TRUNCATE auth.session RESTART IDENTITY")
            if operator_tbl is not None:
                cur.execute("TRUNCATE auth.operator RESTART IDENTITY CASCADE")
        owner.commit()
    yield


def _role_conn(role: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(config.dsn(role, dbname=_TEST_DB)) as conn:
        yield conn


@pytest.fixture
def owner_conn(db: None) -> Iterator[psycopg.Connection]:
    yield from _role_conn("owner")


@pytest.fixture
def app_conn(db: None) -> Iterator[psycopg.Connection]:
    yield from _role_conn("app")


@pytest.fixture
def auditor_conn(db: None) -> Iterator[psycopg.Connection]:
    yield from _role_conn("auditor")
