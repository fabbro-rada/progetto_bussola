import psycopg
import pytest

from bussola.auth import bootstrap
from bussola.auth.errors import AuthError

pytestmark = pytest.mark.usefixtures("db")


def test_creates_first_admin(app_conn: psycopg.Connection):
    admin = bootstrap.create_first_admin(
        app_conn, username="root", display_name="Root", password="a-strong-pw"
    )
    assert admin.role.value == "admin"
    assert admin.must_change_password is True


def test_refuses_when_an_admin_already_exists(app_conn: psycopg.Connection):
    bootstrap.create_first_admin(
        app_conn, username="root", display_name="Root", password="pw12345678"
    )
    with pytest.raises(AuthError):
        bootstrap.create_first_admin(
            app_conn, username="root2", display_name="Root2", password="pw12345678"
        )
    app_conn.rollback()
