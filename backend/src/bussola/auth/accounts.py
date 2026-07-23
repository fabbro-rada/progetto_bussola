"""CRUD for operator accounts (auth.operator). No internal commit: the caller
owns the transaction, so an account change and its audit record commit together."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg

from bussola.auth.errors import UsernameExists
from bussola.auth.models import Operator, OperatorRecord
from bussola.auth.rbac import Role

_RECORD_COLS = (
    "id, username, display_name, role, is_active, must_change_password, "
    "password_hash, failed_attempts, locked_until"
)


def _to_record(row: tuple[Any, ...]) -> OperatorRecord:
    return OperatorRecord(
        id=row[0],
        username=row[1],
        display_name=row[2],
        role=Role(row[3]),
        is_active=row[4],
        must_change_password=row[5],
        password_hash=row[6],
        failed_attempts=row[7],
        locked_until=row[8],
    )


def _to_operator(rec: OperatorRecord) -> Operator:
    return Operator(
        id=rec.id,
        username=rec.username,
        display_name=rec.display_name,
        role=rec.role,
        is_active=rec.is_active,
        must_change_password=rec.must_change_password,
    )


class AccountRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(
        self,
        *,
        username: str,
        display_name: str,
        role: Role,
        password_hash: str,
        created_by: str,
        must_change_password: bool = True,
    ) -> Operator:
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth.operator "
                    "(username, display_name, password_hash, role, must_change_password, created_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING " + _RECORD_COLS,
                    (
                        username,
                        display_name,
                        password_hash,
                        role.value,
                        must_change_password,
                        created_by,
                    ),
                )
                row = cur.fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise UsernameExists(username) from exc
        assert row is not None
        return _to_operator(_to_record(row))

    def get_by_username(self, username: str) -> OperatorRecord | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT " + _RECORD_COLS + " FROM auth.operator WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
        return _to_record(row) if row is not None else None

    def get_by_id(self, operator_id: int) -> OperatorRecord | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT " + _RECORD_COLS + " FROM auth.operator WHERE id = %s",
                (operator_id,),
            )
            row = cur.fetchone()
        return _to_record(row) if row is not None else None

    def list_all(self) -> list[Operator]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT " + _RECORD_COLS + " FROM auth.operator ORDER BY username")
            rows = cur.fetchall()
        return [_to_operator(_to_record(r)) for r in rows]

    def set_active(self, operator_id: int, active: bool, *, by: str) -> None:
        with self._conn.cursor() as cur:
            if active:
                cur.execute(
                    "UPDATE auth.operator SET is_active = true, disabled_at = NULL, "
                    "disabled_by = NULL, failed_attempts = 0, locked_until = NULL WHERE id = %s",
                    (operator_id,),
                )
            else:
                cur.execute(
                    "UPDATE auth.operator SET is_active = false, disabled_at = now(), "
                    "disabled_by = %s WHERE id = %s",
                    (by, operator_id),
                )

    def set_password(self, operator_id: int, password_hash: str, *, must_change: bool) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.operator SET password_hash = %s, must_change_password = %s, "
                "failed_attempts = 0, locked_until = NULL WHERE id = %s",
                (password_hash, must_change, operator_id),
            )

    def record_failed_attempt(
        self, operator_id: int, attempts: int, locked_until: datetime | None
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.operator SET failed_attempts = %s, locked_until = %s WHERE id = %s",
                (attempts, locked_until, operator_id),
            )

    def clear_failures(self, operator_id: int) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.operator SET failed_attempts = 0, locked_until = NULL WHERE id = %s",
                (operator_id,),
            )
