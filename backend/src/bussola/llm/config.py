"""LLM connection configuration (local llama-server, OpenAI-compatible)."""

from __future__ import annotations

import os

from bussola.env import load_project_dotenv

load_project_dotenv()

BASE_URL = os.environ.get("BUSSOLA_LLM_BASE_URL", "http://127.0.0.1:8080")
MODEL = os.environ.get("BUSSOLA_LLM_MODEL", "qwen2.5-7b-instruct")
TIMEOUT = float(os.environ.get("BUSSOLA_LLM_TIMEOUT", "120"))
