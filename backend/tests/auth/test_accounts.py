import psycopg
import pytest

from bussola.auth.accounts import AccountRepository
from bussola.auth.errors import UsernameExists
from bussola.auth.rbac import Role

pytestmark = pytest.mark.usefixtures("db")


def _repo(app_conn: psycopg.Connection) -> AccountRepository:
    return AccountRepository(app_conn)


def test_create_and_get(app_conn: psycopg.Connection):
    repo = _repo(app_conn)
    op = repo.create(
        username="alice",
        display_name="Alice",
        role=Role.OPERATOR,
        password_hash="h",
        created_by="admin",
    )
    app_conn.commit()
    assert op.username == "alice"
    assert op.role is Role.OPERATOR
    assert op.is_active is True
    assert op.must_change_password is True
    rec = repo.get_by_username("alice")
    assert rec is not None and rec.password_hash == "h"


def test_duplicate_username_rejected(app_conn: psycopg.Connection):
    repo = _repo(app_conn)
    repo.create(
        username="bob", display_name="Bob", role=Role.ADMIN, password_hash="h", created_by="admin"
    )
    app_conn.commit()
    with pytest.raises(UsernameExists):
        repo.create(
            username="bob",
            display_name="Bob2",
            role=Role.ADMIN,
            password_hash="h2",
            created_by="admin",
        )
    app_conn.rollback()


def test_disable_and_list(app_conn: psycopg.Connection):
    repo = _repo(app_conn)
    op = repo.create(
        username="carl",
        display_name="Carl",
        role=Role.OPERATOR,
        password_hash="h",
        created_by="admin",
    )
    app_conn.commit()
    repo.set_active(op.id, False, by="admin")
    app_conn.commit()
    rec = repo.get_by_id(op.id)
    assert rec is not None and rec.is_active is False
    assert any(o.username == "carl" for o in repo.list_all())


def test_get_missing_returns_none(app_conn: psycopg.Connection):
    assert _repo(app_conn).get_by_username("nobody") is None
