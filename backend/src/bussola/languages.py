"""Single source of truth for the five supported languages (§8).

A dependency-free module so any layer (guardrails, system, …) can import the
constant without creating cross-package coupling."""

from __future__ import annotations

SUPPORTED_LANGUAGES: tuple[str, ...] = ("it", "en", "fr", "es", "ar")

# English names of the supported languages, for LLM prompt directives. An
# explicit name ("Italian") steers the model to answer in that language far
# more reliably than a bare code ("it"), which it tends to ignore — the reason
# the interview summary/clarification used to come back in English (§7.1).
LANGUAGE_NAMES: dict[str, str] = {
    "it": "Italian",
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "ar": "Arabic",
}


def language_name(code: str) -> str:
    """English name of a supported language code (e.g. 'it' → 'Italian'), for
    use in LLM prompts. Falls back to the code itself for anything unknown."""
    return LANGUAGE_NAMES.get(code, code)
