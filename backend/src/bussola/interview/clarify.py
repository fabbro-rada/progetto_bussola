"""Per-section clarity check + recap-correction routing (§5/§7.1)."""

from __future__ import annotations

from pydantic import BaseModel

from bussola.interview.extraction import extract_section
from bussola.interview.sections import SECTIONS, Section
from bussola.languages import language_name
from bussola.llm.client import LlmClient
from bussola.profile.models import WorkProfile

_CLARIFY_SCHEMA = {
    "type": "object",
    "properties": {"needs_clarification": {"type": "boolean"}, "question": {"type": "string"}},
    "required": ["needs_clarification", "question"],
    "additionalProperties": False,
}

_ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "section": {
            "type": "string",
            "enum": ["skills", "experiences", "aspirations", "constraints", "preferences", "none"],
        }
    },
    "required": ["section"],
    "additionalProperties": False,
}
_SECTION_BY_KEY = {s.key: s for s in SECTIONS}


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
        "read aloud). The question MUST be concrete and about ONE specific thing, so a "
        "person with low literacy understands it at once with no ambiguity: ask plainly "
        "what they actually did, e.g. 'Che cosa facevi come custode nella scuola?'. Do "
        "NOT ask abstract or bureaucratic questions such as 'qual è la tua responsabilità "
        "nel ruolo di...' or 'qual è la relazione tra X e le tue esperienze'. "
        'Reply JSON {"needs_clarification": bool, "question": string}; '
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


def apply_recap_correction(
    client: LlmClient, reply: str, profile: WorkProfile, language: str
) -> BaseModel | None:
    """Route a free-text recap correction to a section and return its corrected
    extraction (constrained), or None if not routable/on error (§3 fail-closed:
    the caller keeps the recap unchanged)."""
    try:
        routed = client.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Which ONE profile section does this correction change? "
                        'Reply JSON {"section": one of '
                        "skills|experiences|aspirations|constraints|preferences|none}. "
                        "Use 'none' if it does not clearly map to a section."
                    ),
                },
                {
                    "role": "user",
                    "content": f"[current profile]\n{profile.model_dump_json()}\n[correction]\n{reply}",
                },
            ],
            json_schema=_ROUTE_SCHEMA,
        )
    except Exception:
        return None
    key = routed.get("section")
    section = _SECTION_BY_KEY.get(key) if isinstance(key, str) else None
    if section is None:
        return None
    # Re-extract the whole section from current data + the correction (extract_section
    # OVERWRITES the section via session.merge's first-interview semantics).
    context = (
        f"The person's current profile is: {profile.model_dump_json()}. "
        f"They correct the {section.key}: {reply}. Produce the corrected {section.key}."
    )
    try:
        return extract_section(client, section, context, language)
    except Exception:
        return None
