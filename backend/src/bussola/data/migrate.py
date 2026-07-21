"""Minimal, transparent SQL migration runner.

Applies *.sql files from a directory in filename order, recording applied
ones in bussola_meta.schema_migrations. Must run as the owner role (DDL).
"""

from __future__ import annotations

from pathlib import Path

import psycopg

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path | None = None) -> list[str]:
    """Apply pending migrations in filename order; return newly applied names."""
    directory = migrations_dir or _MIGRATIONS_DIR
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS bussola_meta")
        cur.execute(
            "CREATE TABLE IF NOT EXISTS bussola_meta.schema_migrations ("
            "name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT name FROM bussola_meta.schema_migrations")
        applied = {row[0] for row in cur.fetchall()}

    newly_applied: list[str] = []
    for path in sorted(directory.glob("*.sql")):
        if path.name in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO bussola_meta.schema_migrations (name) VALUES (%s)",
                (path.name,),
            )
        conn.commit()
        newly_applied.append(path.name)
    return newly_applied
