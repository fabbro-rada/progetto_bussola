"""Single source of truth for the five supported languages (§8).

A dependency-free module so any layer (guardrails, system, …) can import the
constant without creating cross-package coupling."""

from __future__ import annotations

SUPPORTED_LANGUAGES: tuple[str, ...] = ("it", "en", "fr", "es", "ar")
