"""AuthService: login, session auth, logout, self password change. Every login
outcome is audited; account state and audit commit in ONE transaction. Login
failures are generic (no user-enumeration) with timing equalized via dummy-verify."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psycopg

from bussola.auth import auth_audit, config, passwords
from bussola.auth.accounts import AccountRepository
from bussola.auth.errors import InvalidCredentials
from bussola.auth.models import Operator, OperatorRecord
from bussola.auth.sessions import SessionStore


@dataclass(frozen=True)
class LoginResult:
    token: str
    operator: Operator
    must_change_password: bool


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn
        self._accounts = AccountRepository(conn)
        self._sessions = SessionStore(conn)

    def _fail(self, actor: str | None) -> None:
        auth_audit.record_auth_event(self._conn, action=auth_audit.LOGIN_FAILED, actor=actor)
        self._conn.commit()
        raise InvalidCredentials()

    def login(self, username: str, password: str) -> LoginResult:
        rec = self._accounts.get_by_username(username)
        now = _utcnow()
        if rec is None or not rec.is_active:
            passwords.dummy_verify()
            self._fail(username)
        assert rec is not None
        if rec.locked_until is not None and rec.locked_until > now:
            passwords.dummy_verify()
            self._fail(username)
        if not passwords.verify_password(rec.password_hash, password):
            attempts = rec.failed_attempts + 1
            locked_until = (
                now + timedelta(seconds=config.LOCKOUT_SECONDS)
                if attempts >= config.MAX_FAILED_ATTEMPTS
                else rec.locked_until
            )
            self._accounts.record_failed_attempt(rec.id, attempts, locked_until)
            self._fail(username)
        # success
        self._accounts.clear_failures(rec.id)
        token = self._sessions.create(rec.id)
        auth_audit.record_auth_event(
            self._conn, action=auth_audit.LOGIN_SUCCEEDED, actor=rec.username
        )
        self._conn.commit()
        return LoginResult(
            token=token,
            operator=_operator_from_record(rec),
            must_change_password=rec.must_change_password,
        )

    def authenticate(self, token: str) -> Operator | None:
        operator_id = self._sessions.lookup(token)
        if operator_id is None:
            self._conn.commit()  # persist last_seen_at update (no-op if none)
            return None
        rec = self._accounts.get_by_id(operator_id)
        self._conn.commit()
        if rec is None or not rec.is_active:
            return None
        return _operator_from_record(rec)

    def logout(self, token: str) -> None:
        self._sessions.revoke(token)
        auth_audit.record_auth_event(self._conn, action=auth_audit.LOGOUT, actor=None)
        self._conn.commit()

    def change_password(self, operator_id: int, old_password: str, new_password: str) -> None:
        rec = self._accounts.get_by_id(operator_id)
        if rec is None or not passwords.verify_password(rec.password_hash, old_password):
            raise InvalidCredentials()
        self._accounts.set_password(
            operator_id, passwords.hash_password(new_password), must_change=False
        )
        self._sessions.revoke_all_for_operator(operator_id)
        auth_audit.record_auth_event(
            self._conn, action=auth_audit.PASSWORD_CHANGED, actor=rec.username
        )
        self._conn.commit()


def _operator_from_record(rec: OperatorRecord) -> Operator:
    return Operator(
        id=rec.id,
        username=rec.username,
        display_name=rec.display_name,
        role=rec.role,
        is_active=rec.is_active,
        must_change_password=rec.must_change_password,
    )
