"""Summary and confirmation. The PERSON confirms or corrects (§5)."""

from __future__ import annotations

from pydantic import BaseModel

from bussola.interview.sections import Section
from bussola.llm.client import LlmClient

_CONFIRM_SCHEMA = {
    "type": "object",
    "properties": {"confirmed": {"type": "boolean"}},
    "required": ["confirmed"],
    "additionalProperties": False,
}


def summarize(client: LlmClient, section: Section, extracted: BaseModel, language: str) -> str:
    prompt = (
        "You are a warm, non-judgmental assistant. In one or two short sentences, in the "
        f"language '{language}', summarize back to the person what you understood for the "
        f"'{section.key}' section, then ask if it is correct. Be encouraging, never judgmental."
    )
    return client.chat(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"[extracted data]\n{extracted.model_dump_json()}"},
        ],
        temperature=0.0,
    )


def interpret_confirmation(client: LlmClient, answer: str, language: str) -> bool:
    """True if the person confirms; False if they correct/deny (fail-safe: False)."""
    try:
        raw = client.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Does the person's reply CONFIRM the summary was correct? "
                        'Reply JSON {"confirmed": bool}.'
                    ),
                },
                {"role": "user", "content": f"[reply, language={language}]\n{answer}"},
            ],
            json_schema=_CONFIRM_SCHEMA,
        )
    except Exception:
        return False
    return raw.get("confirmed") is True
