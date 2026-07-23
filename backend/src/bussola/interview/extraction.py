"""Per-section extraction via constrained decoding + Pydantic validation.

Fail-safe: an unparseable/invalid model yields an EMPTY section model (no
invented data), never an exception — the flow can re-ask if needed.
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from bussola.interview.sections import Section
from bussola.llm.client import LlmClient


def extract_section(client: LlmClient, section: Section, answer: str, language: str) -> BaseModel:
    schema = section.extraction_model.model_json_schema()
    raw = client.chat_json(
        [
            {"role": "system", "content": section.extraction_prompt},
            {"role": "user", "content": f"[reply, language={language}]\n{answer}"},
        ],
        json_schema=schema,
    )
    try:
        return section.extraction_model.model_validate(raw)
    except ValidationError:
        return section.extraction_model()  # fail-safe: empty, no invented data
