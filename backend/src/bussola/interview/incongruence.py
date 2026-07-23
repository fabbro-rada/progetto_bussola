"""Semantic incongruence detection + gentle clarification (§5, §4)."""

from __future__ import annotations

from bussola.llm.client import LlmClient
from bussola.profile.models import WorkProfile

_SCHEMA = {
    "type": "object",
    "properties": {
        "has_incongruence": {"type": "boolean"},
        "clarification": {"type": "string"},
    },
    "required": ["has_incongruence", "clarification"],
    "additionalProperties": False,
}


def find_incongruence(client: LlmClient, profile: WorkProfile, language: str) -> str | None:
    """Return a gentle clarification question if the profile has a semantic
    incongruence, else None. Fail-safe: None (never block the flow)."""
    prompt = (
        "You check a WORK profile for a SEMANTIC incongruence (e.g. a duration that "
        "doesn't add up, a skill that contradicts the experiences). If found, write a "
        f"gentle, non-judgmental clarification question in the language '{language}'. "
        'Reply JSON {"has_incongruence": bool, "clarification": string}.'
    )
    try:
        raw = client.chat_json(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"[profile]\n{profile.model_dump_json()}"},
            ],
            json_schema=_SCHEMA,
        )
    except Exception:
        return None
    if raw.get("has_incongruence") is True and isinstance(raw.get("clarification"), str):
        return raw["clarification"] or None
    return None
