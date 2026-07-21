"""Guarded conversation pipeline: input guard -> in-scope answer -> output guard.

Scope is enforced on the way IN and on the way OUT (§2). The output PII filter
(§7.3) redacts any personal data before the reply reaches the person.

The whole flow is wrapped in a graceful-degradation guard (§3.7 / §7.1 "the
conversation must never block"): if the local LLM server cannot be reached
(`LlmUnavailable`), or if *anything else* in the flow fails unexpectedly
(a redaction bug, an HTTP 5xx surfacing as `httpx.HTTPStatusError`, a
malformed LLM response raising `KeyError`/`IndexError`, ...), the exception
is never propagated and no model content is ever let through — the person
only ever sees a controlled, localized "temporarily unavailable" reply. This
is a deliberate fail-closed net: an unforeseen fault degrades the
conversation, it does not crash it and it does not leak whatever partial
content was in flight.
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
        except Exception:
            # Broad fail-closed net (§7.1 "never blocks"): ANY other
            # unforeseen fault in the flow (a redaction bug, an HTTP 5xx
            # surfacing as httpx.HTTPStatusError, a malformed LLM response
            # raising KeyError/IndexError, ...) must degrade the same way
            # as a known-unavailable server — never propagate, never let
            # model content through. This is deliberately unspecific: the
            # whole point is to catch faults we did not anticipate.
            return self._unavailable()

    def _ask(self, user_text: str) -> Reply:
        incoming = self._guard.check(user_text, self._language)
        if not incoming.allow:
            # `RefusalCategory.OUT_OF_SCOPE` fallback mirrors the output-path
            # handling below: fail-safe on a missing category rather than
            # relying on `assert`, which is stripped under `python -O`.
            return self._refuse(incoming.category or RefusalCategory.OUT_OF_SCOPE)

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
