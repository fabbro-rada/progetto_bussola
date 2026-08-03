"""Summary and confirmation. The PERSON confirms or corrects (§5)."""

from __future__ import annotations

from pydantic import BaseModel

from bussola.interview.sections import Section
from bussola.languages import language_name
from bussola.llm.client import LlmClient

_CONFIRM_SCHEMA = {
    "type": "object",
    "properties": {"confirmed": {"type": "boolean"}},
    "required": ["confirmed"],
    "additionalProperties": False,
}


def summarize(client: LlmClient, section: Section, extracted: BaseModel, language: str) -> str:
    name = language_name(language)
    prompt = (
        f"You are a warm, non-judgmental assistant. Write your ENTIRE reply in {name} "
        f"(language code '{language}') — every word in {name}, never in English or any "
        "other language. In one or two short sentences, summarize back to the person what "
        f"you understood for the '{section.key}' section, then ask if it is correct. "
        "Use simple, everyday words that anyone can understand: reuse the plain words the "
        "person themselves would use, and NEVER replace them with a technical, specialised "
        "or fancier synonym (for example, if the data says a job like 'falegname', say "
        "'falegname', not 'carpenteria'). "
        "Do NOT use any emoji, emoticons or symbols — the text is read aloud, and a voice "
        "would speak the emoji's name. "
        "Be encouraging, never judgmental."
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
