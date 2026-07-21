"""Guarded conversation pipeline: input guard -> in-scope answer -> output guard.

Scope is enforced on the way IN and on the way OUT (§2). The output PII filter
(§7.3) redacts any personal data before the reply reaches the person.

The whole flow is wrapped in a graceful-degradation guard (§3.7): if the local
LLM server cannot be reached (`LlmUnavailable`), the exception is never
propagated and no content is ever let through — the person only ever sees a
controlled, localized "temporarily unavailable" reply.
"""

from __future__ import annotations

from dataclasses import dataclass

from bussola.guardrails.pii import PiiRedactor
from bussola.guardrails.prompts import system_prompt
from bussola.guardrails.refusal import RefusalCategory, refusal_message, unavailable_message
from bussola.guardrails.scope import ScopeGuard
from bussola.llm.client import LlmClient, LlmUnavailable


@dataclass(frozen=True)
class Reply:
    refused: bool
    text: str
    category: RefusalCategory | None


class GuardedConversation:
    def __init__(
        self,
        client: LlmClient,
        scope_guard: ScopeGuard,
        redactor: PiiRedactor,
        *,
        language: str = "it",
    ) -> None:
        self._client = client
        self._guard = scope_guard
        self._redactor = redactor
        self._language = language

    def _refuse(self, category: RefusalCategory) -> Reply:
        return Reply(True, refusal_message(category, self._language), category)

    def _unavailable(self) -> Reply:
        return Reply(True, unavailable_message(self._language), None)

    def ask(self, user_text: str) -> Reply:
        try:
            return self._ask(user_text)
        except LlmUnavailable:
            # Graceful degradation (§3.7): never propagate, never let
            # content through. The person only sees a controlled notice.
            return self._unavailable()

    def _ask(self, user_text: str) -> Reply:
        incoming = self._guard.check(user_text, self._language)
        if not incoming.allow:
            assert incoming.category is not None
            return self._refuse(incoming.category)

        answer = self._client.chat(
            [
                {"role": "system", "content": system_prompt(self._language)},
                {"role": "user", "content": f"[user message]\n{user_text}"},
            ],
            temperature=0.0,
        )

        outgoing = self._guard.check_output(answer, self._language)
        if not outgoing.allow:
            return self._refuse(outgoing.category or RefusalCategory.OUT_OF_SCOPE)

        return Reply(False, self._redactor.redact(answer, self._language), None)
