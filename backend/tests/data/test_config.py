"""Tests for the minimal, dependency-free .env loader in bussola.data.config.

Pure unit tests: no database, no network. Each test isolates the environment
via monkeypatch so nothing leaks into other tests or the real process env.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bussola.data.config import _load_dotenv


def test_populates_unset_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("BUSSOLA_TEST_KEY=from_dotenv\n")

    _load_dotenv(env_file)

    assert os.environ.get("BUSSOLA_TEST_KEY") == "from_dotenv"
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)


def test_does_not_override_existing_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUSSOLA_TEST_KEY", "from_real_env")
    env_file = tmp_path / ".env"
    env_file.write_text("BUSSOLA_TEST_KEY=from_dotenv\n")

    _load_dotenv(env_file)

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

    _load_dotenv(env_file)

    assert os.environ.get("BUSSOLA_TEST_KEY") == "value_one"
    assert os.environ.get("BUSSOLA_TEST_OTHER") is None
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)


def test_missing_file_is_a_noop(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist" / ".env"

    _load_dotenv(missing)  # must not raise


def test_strips_surrounding_quotes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('BUSSOLA_TEST_KEY="quoted value"\n')

    _load_dotenv(env_file)

    assert os.environ.get("BUSSOLA_TEST_KEY") == "quoted value"
    monkeypatch.delenv("BUSSOLA_TEST_KEY", raising=False)
