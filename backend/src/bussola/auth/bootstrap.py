"""Create the very first Amministratore. No default credentials are shipped:
the deployer runs `python -m bussola.auth.bootstrap` with the account details
in the environment. Refuses if an admin already exists."""

from __future__ import annotations

import os
import sys

import psycopg

from bussola.auth import auth_audit, passwords
from bussola.auth.accounts import AccountRepository
from bussola.auth.errors import AuthError
from bussola.auth.models import Operator
from bussola.auth.rbac import Role
from bussola.data import config


def _admin_exists(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM auth.operator WHERE role = %s LIMIT 1", (Role.ADMIN.value,))
        return cur.fetchone() is not None


def create_first_admin(
    conn: psycopg.Connection, *, username: str, display_name: str, password: str
) -> Operator:
    if _admin_exists(conn):
        raise AuthError("an administrator already exists; bootstrap refused")
    operator = AccountRepository(conn).create(
        username=username,
        display_name=display_name,
        role=Role.ADMIN,
        password_hash=passwords.hash_password(password),
        created_by="bootstrap",
        must_change_password=True,
    )
    auth_audit.record_auth_event(
        conn,
        action=auth_audit.OPERATOR_CREATED,
        actor="bootstrap",
        target_operator=username,
        role=Role.ADMIN.value,
    )
    conn.commit()
    return operator


def main() -> int:
    username = os.environ.get("BUSSOLA_ADMIN_USERNAME")
    display_name = os.environ.get("BUSSOLA_ADMIN_DISPLAY_NAME", username or "")
    password = os.environ.get("BUSSOLA_ADMIN_PASSWORD")
    if not username or not password:
        print(
            "Set BUSSOLA_ADMIN_USERNAME and BUSSOLA_ADMIN_PASSWORD in the environment.",
            file=sys.stderr,
        )
        return 2
    with psycopg.connect(config.dsn("app")) as conn:
        try:
            operator = create_first_admin(
                conn, username=username, display_name=display_name, password=password
            )
        except AuthError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    print(f"Created administrator '{operator.username}' (must change password at first login).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
