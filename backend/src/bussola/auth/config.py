"""Auth tunables, from environment with safe defaults (§3)."""

from __future__ import annotations

import os

from bussola.env import load_project_dotenv

load_project_dotenv()

SESSION_TTL_SECONDS = int(os.environ.get("BUSSOLA_SESSION_TTL_SECONDS", "43200"))  # 12h
SESSION_IDLE_SECONDS = int(os.environ.get("BUSSOLA_SESSION_IDLE_SECONDS", "1800"))  # 30m
MAX_FAILED_ATTEMPTS = int(os.environ.get("BUSSOLA_MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_SECONDS = int(os.environ.get("BUSSOLA_LOCKOUT_SECONDS", "900"))  # 15m
