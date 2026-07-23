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
    """Return a gentle clarification question if the COMPLETED profile has a
    genuine contradiction, else None. Fail-safe: None (never block the flow).

    Run once on the whole profile at the end of the interview (contradictions
    are cross-section by nature). It flags only real contradictions between
    what the person actually said — never missing or empty fields, which are
    expected in an intentionally minimal profile (§5)."""
    prompt = (
        "You check a COMPLETED work profile for a GENUINE CONTRADICTION between "
        "information the person actually provided — for example a total work "
        "duration that cannot fit their stated timeline, or a claimed skill that "
        "directly conflicts with the described experiences. "
        "A MISSING, EMPTY or NOT-YET-PROVIDED field is NEVER an incongruence: the "
        "profile is intentionally minimal and incomplete data is expected and fine. "
        "Report an incongruence ONLY when two pieces of information the person gave "
        "clearly cannot both be true. When in doubt, report NONE. "
        "If (and only if) you find a real contradiction, write ONE gentle, "
        f"non-judgmental clarification question in the language with code '{language}' "
        "(never accuse; simply ask the person to clarify). "
        'Reply JSON {"has_incongruence": bool, "clarification": string}. '
        "Use has_incongruence=false with an empty clarification when there is no "
        "clear contradiction."
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
