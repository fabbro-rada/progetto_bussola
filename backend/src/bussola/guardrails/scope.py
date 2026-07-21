"""Independent scope/safety guard backed by an LLM classifier.

Fail-safe: any uncertainty (unparseable classifier output) results in a
REFUSAL, never in letting content through.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from bussola.guardrails.prompts import output_classifier_prompt, scope_classifier_prompt
from bussola.guardrails.refusal import RefusalCategory
from bussola.llm.client import LlmClient


@dataclass(frozen=True)
class GuardDecision:
    allow: bool
    category: RefusalCategory | None
    reason: str


def _extract_json(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _to_decision(raw: dict[str, Any] | None) -> GuardDecision:
    if raw is None or not isinstance(raw.get("allow"), bool):
        # Fail-safe: unparseable/ambiguous classifier output => refuse.
        return GuardDecision(False, RefusalCategory.MANIPULATION, "unparseable classifier output")
    if raw["allow"]:
        return GuardDecision(True, None, str(raw.get("reason", "")))
    try:
        category = RefusalCategory(raw.get("category") or "out_of_scope")
    except ValueError:
        category = RefusalCategory.OUT_OF_SCOPE
    return GuardDecision(False, category, str(raw.get("reason", "")))


class ScopeGuard:
    def __init__(self, client: LlmClient, *, max_input_chars: int = 2000) -> None:
        self._client = client
        self._max = max_input_chars

    def _classify(self, system: str, content: str) -> GuardDecision:
        raw = self._client.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": content}],
            temperature=0.0,
        )
        return _to_decision(_extract_json(raw))

    def check(self, text: str, language: str) -> GuardDecision:
        if not text.strip() or len(text) > self._max:
            return GuardDecision(False, RefusalCategory.INVALID_INPUT, "empty or too long")
        return self._classify(scope_classifier_prompt(), f"[user message]\n{text}")

    def check_output(self, reply: str, language: str) -> GuardDecision:
        return self._classify(output_classifier_prompt(), f"[assistant reply]\n{reply}")
