"""Tests for the shared .env loader/finder (bussola.env) and the DSN builder
(bussola.data.config).

Pure unit tests: no database, no network. Each test isolates the environment
via monkeypatch so nothing leaks into other tests or the real process env.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from psycopg.conninfo import conninfo_to_dict

from bussola.data.config import dsn
from bussola.env import _find_dotenv, load_project_dotenv


def test_populates_unset_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("BUSSOLA_TEST_KEY=from_dotenv\n")

    load_project_dotenv(env_file)

    assert os.environ.get("BUSSOLA_TEST_KEY") == "from_dotenv"
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)


def test_does_not_override_existing_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUSSOLA_TEST_KEY", "from_real_env")
    env_file = tmp_path / ".env"
    env_file.write_text("BUSSOLA_TEST_KEY=from_dotenv\n")

    load_project_dotenv(env_file)

    assert os.environ.get("BUSSOLA_TEST_KEY") == "from_real_env"


def test_ignores_comments_and_blank_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)
    monkeypatch.delenv("BUSSOLA_TEST_OTHER", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n"
        "# a comment line\n"
        "   \n"
        "BUSSOLA_TEST_KEY=value_one\n"
        "# BUSSOLA_TEST_OTHER=should_be_ignored\n"
    )

    load_project_dotenv(env_file)

    assert os.environ.get("BUSSOLA_TEST_KEY") == "value_one"
    assert os.environ.get("BUSSOLA_TEST_OTHER") is None
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)


def test_missing_file_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no `.env` is found anywhere up the tree, loading changes nothing.

    Forces the "not found" branch deterministically (rather than relying on
    the ambient assumption that no ancestor of `tmp_path` has a `.env`) by
    monkeypatching `_find_dotenv` itself.
    """
    monkeypatch.delenv("BUSSOLA_TEST_NOOP_SENTINEL", raising=False)
    monkeypatch.setattr("bussola.env._find_dotenv", lambda start=None: None)

    load_project_dotenv()  # must not raise

    assert "BUSSOLA_TEST_NOOP_SENTINEL" not in os.environ


def test_strips_surrounding_quotes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('BUSSOLA_TEST_KEY="quoted value"\n')

    load_project_dotenv(env_file)

    assert os.environ.get("BUSSOLA_TEST_KEY") == "quoted value"
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)


def test_asymmetric_quote_is_kept_literally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a single matching leading/trailing quote pair is stripped.

    A lone trailing quote with no matching leading quote is not a pair, so it
    must be kept as part of the literal value (matches the original
    `data/config.py._load_dotenv` behavior).
    """
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("BUSSOLA_TEST_KEY=hello'\n")

    load_project_dotenv(env_file)

    assert os.environ.get("BUSSOLA_TEST_KEY") == "hello'"
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)


def test_find_dotenv_finds_env_in_parent_directory(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("BUSSOLA_TEST_KEY=1\n")
    start = tmp_path / "sub" / "deeper"
    start.mkdir(parents=True)

    found = _find_dotenv(start)

    assert found == tmp_path / ".env"


def test_find_dotenv_returns_none_when_no_env_up_the_tree(tmp_path: Path) -> None:
    # tmp_path (and everything above it, up to the filesystem root) is
    # guaranteed not to contain a .env file for this test run.
    start = tmp_path / "sub" / "deeper"
    start.mkdir(parents=True)

    assert _find_dotenv(start) is None


def test_dsn_escapes_password_with_space_and_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    """A password containing a space and a quote must round-trip exactly.

    Raw f-string interpolation would produce a malformed/misparsed DSN for
    such a value; `make_conninfo` quotes/escapes it correctly instead.
    """
    tricky_password = 'sample password"with quote'
    monkeypatch.setenv("BUSSOLA_APP_PASSWORD", tricky_password)

    conninfo = dsn("app")
    parsed = conninfo_to_dict(conninfo)

    assert parsed["password"] == tricky_password
    assert parsed["host"] == "127.0.0.1"
    assert parsed["user"] == "bussola_app"
    assert parsed["dbname"] == "bussola"
