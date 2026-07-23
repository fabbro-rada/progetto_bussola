"""Voice domain models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Transcription(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str
    language: str
