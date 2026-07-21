"""Shared, dependency-free `.env` loader.

Loaded once at import by the config modules so that a single project `.env`
drives both docker compose and the Python processes. Real environment
variables always win over `.env`.
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_dotenv(start: Path | None = None) -> Path | None:
    """Walk up from `start` (or the current directory) looking for a `.env`."""
    directory = start or Path.cwd()
    for candidate in (directory, *directory.parents):
        dotenv = candidate / ".env"
        if dotenv.is_file():
            return dotenv
    return None


def load_project_dotenv(start: Path | None = None) -> None:
    """Populate os.environ from the nearest `.env` (walking up), without
    overriding variables already set. Missing file is a no-op."""
    dotenv = _find_dotenv(start)
    if dotenv is None:
        return
    try:
        content = dotenv.read_text(encoding="utf-8")
    except OSError:
        return
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
