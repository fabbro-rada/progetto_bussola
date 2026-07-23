import psycopg
import pytest

from bussola.auth import passwords
from bussola.auth.accounts import AccountRepository
from bussola.auth.errors import InvalidCredentials
from bussola.auth.rbac import Role
from bussola.auth.service import AuthService
from bussola.auth import config

pytestmark = pytest.mark.usefixtures("db")


def _seed(
    conn: psycopg.Connection, *, pw: str = "correct-horse", must_change: bool = False
) -> None:
    AccountRepository(conn).create(
        username="alice",
        display_name="Alice",
        role=Role.OPERATOR,
        password_hash=passwords.hash_password(pw),
        created_by="admin",
        must_change_password=must_change,
    )
    conn.commit()


def test_login_success_returns_token_and_operator(app_conn: psycopg.Connection):
    _seed(app_conn)
    result = AuthService(app_conn).login("alice", "correct-horse")
    assert result.token
    assert result.operator.username == "alice"
    assert AuthService(app_conn).authenticate(result.token).username == "alice"


def test_wrong_password_raises_generic(app_conn: psycopg.Connection):
    _seed(app_conn)
    with pytest.raises(InvalidCredentials):
        AuthService(app_conn).login("alice", "nope")


def test_unknown_user_raises_same_generic(app_conn: psycopg.Connection):
    with pytest.raises(InvalidCredentials):
        AuthService(app_conn).login("ghost", "whatever")


def test_lockout_after_repeated_failures(app_conn: psycopg.Connection):
    _seed(app_conn)
    svc = AuthService(app_conn)
    for _ in range(config.MAX_FAILED_ATTEMPTS):
        with pytest.raises(InvalidCredentials):
            svc.login("alice", "nope")
    # now locked: even the RIGHT password is refused during the lockout window
    with pytest.raises(InvalidCredentials):
        svc.login("alice", "correct-horse")


def test_login_success_is_audited(app_conn: psycopg.Connection):
    _seed(app_conn)
    AuthService(app_conn).login("alice", "correct-horse")
    with app_conn.cursor() as cur:
        cur.execute("SELECT action, actor FROM audit.audit_log ORDER BY id DESC LIMIT 1")
        action, actor = cur.fetchone()
    assert action == "login_succeeded"
    assert actor == "alice"


def test_logout_revokes_session(app_conn: psycopg.Connection):
    _seed(app_conn)
    svc = AuthService(app_conn)
    token = svc.login("alice", "correct-horse").token
    svc.logout(token)
    assert svc.authenticate(token) is None


def test_change_password_updates_and_clears_must_change(app_conn: psycopg.Connection):
    _seed(app_conn, must_change=True)
    svc = AuthService(app_conn)
    rec = AccountRepository(app_conn).get_by_username("alice")
    svc.change_password(rec.id, "correct-horse", "brand-new-pw")
    token = svc.login("alice", "brand-new-pw").token
    assert svc.authenticate(token).must_change_password is False
