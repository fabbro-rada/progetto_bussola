"""System status / configuration overview for the admin (§6), READ-ONLY.

Exposes only NON-SECRET config plus a live LLM reachability check. No secrets
(no DB password/DSN/token) and no security controls (guardrails/scope/PII stay
in code and are never exposed or editable, §2/§9)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
from pydantic import BaseModel, ConfigDict

from bussola.auth import config as auth_config
from bussola.llm import config as llm_config
from bussola.voice import config as voice_config

SUPPORTED_LANGUAGES = ("it", "en", "fr", "es", "ar")
_HEALTH_TIMEOUT = 2.0


class SystemConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm_model: str
    llm_base_url: str
    llm_timeout: float
    llm_reachable: bool
    languages: list[str]
    stt_model: str
    tts_voices: dict[str, bool]
    session_ttl_seconds: int
    session_idle_seconds: int
    max_failed_attempts: int
    lockout_seconds: int


def _default_llm_reachable() -> bool:
    """Live LLM reachability, fail-safe: any error/timeout → False."""
    try:
        response = httpx.get(f"{llm_config.BASE_URL}/health", timeout=_HEALTH_TIMEOUT)
        return response.status_code == 200
    except Exception:
        return False


def compute_system_config(
    *, llm_reachable: Callable[[], bool] = _default_llm_reachable
) -> SystemConfig:
    return SystemConfig(
        llm_model=llm_config.MODEL,
        llm_base_url=llm_config.BASE_URL,
        llm_timeout=llm_config.TIMEOUT,
        llm_reachable=llm_reachable(),
        languages=list(SUPPORTED_LANGUAGES),
        stt_model=voice_config.STT_MODEL,
        tts_voices={lang: lang in voice_config.PIPER_VOICES for lang in SUPPORTED_LANGUAGES},
        session_ttl_seconds=auth_config.SESSION_TTL_SECONDS,
        session_idle_seconds=auth_config.SESSION_IDLE_SECONDS,
        max_failed_attempts=auth_config.MAX_FAILED_ATTEMPTS,
        lockout_seconds=auth_config.LOCKOUT_SECONDS,
    )
