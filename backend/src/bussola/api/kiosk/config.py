"""Kiosk API tunables, from environment with safe defaults."""

from __future__ import annotations

import os

from bussola.env import load_project_dotenv

load_project_dotenv()

# Pre-shared device token; empty = not configured = deny all (fail closed).
KIOSK_TOKEN = os.environ.get("BUSSOLA_KIOSK_TOKEN", "")
VOICE_TIMEOUT = float(os.environ.get("BUSSOLA_VOICE_TIMEOUT", "10.0"))
SESSION_TTL = int(os.environ.get("BUSSOLA_KIOSK_SESSION_TTL", "1800"))  # 30 min
