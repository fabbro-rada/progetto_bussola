"""Per-section clarity check + recap-correction routing (§5/§7.1)."""

from __future__ import annotations

from pydantic import BaseModel

from bussola.interview.sections import Section
from bussola.languages import language_name
from bussola.llm.client import LlmClient
from bussola.profile.models import WorkProfile

_CLARIFY_SCHEMA = {
    "type": "object",
    "properties": {"needs_clarification": {"type": "boolean"}, "question": {"type": "string"}},
    "required": ["needs_clarification", "question"],
    "additionalProperties": False,
}


def find_section_clarification(
    client: LlmClient, section: Section, extracted: BaseModel, profile: WorkProfile, language: str
) -> str | None:
    """A gentle OPEN question if this section's extraction is ambiguous or
    incoherent with the profile so far, else None. Fail-open: None on any error
    (§3 — a clarity check must never block the turn)."""
    name = language_name(language)
    prompt = (
        "You review one section just extracted from a person's work interview. "
        "Ask a clarification ONLY IF a key field is ambiguous or clearly incoherent "
        "with what the person already said — for example a role that is a generic "
        "verb ('lavorato', 'fatto') instead of a job, a duration that cannot be "
        "right, or an experience that contradicts an earlier section. A MISSING or "
        "EMPTY field is NEVER a reason to ask (the profile is intentionally minimal). "
        "When in doubt, do NOT ask. If (and only if) needed, write ONE short, gentle, "
        f"non-judgmental OPEN question ENTIRELY in {name} (code '{language}') — every "
        "word in that language, simple everyday words, and NO emoji or symbols (it is "
        'read aloud). Reply JSON {"needs_clarification": bool, "question": string}; '
        "use false + empty question when no clarification is needed."
    )
    user = (
        f"[section]\n{section.key}\n[extracted]\n{extracted.model_dump_json()}\n"
        f"[profile so far]\n{profile.model_dump_json()}"
    )
    try:
        raw = client.chat_json(
            [{"role": "system", "content": prompt}, {"role": "user", "content": user}],
            json_schema=_CLARIFY_SCHEMA,
        )
    except Exception:
        return None
    if raw.get("needs_clarification") is True and isinstance(raw.get("question"), str):
        return raw["question"] or None
    return None
