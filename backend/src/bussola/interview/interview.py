"""Deterministic interview orchestrator. The app drives the sections; the LLM
formulates, extracts, summarizes and checks incongruences. Degrades gracefully."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from bussola.guardrails.pii import PiiRedactor
from bussola.guardrails.refusal import RefusalCategory, refusal_message, unavailable_message
from bussola.guardrails.scope import ScopeGuard
from bussola.interview.confirm import interpret_confirmation, summarize
from bussola.interview.extraction import extract_section
from bussola.interview.incongruence import find_incongruence
from bussola.interview.sections import base_question
from bussola.interview.session import InterviewSession
from bussola.llm.client import LlmClient, LlmUnavailable
from bussola.profile.models import WorkProfile


@dataclass(frozen=True)
class Step:
    kind: str  # question | summary | clarification | refusal | unavailable | completed
    text: str


class ProfileStore(Protocol):
    def create_new(self) -> str: ...
    def save(self, profile: WorkProfile) -> WorkProfile: ...


class TextRedactor(Protocol):
    def redact(self, text: str, language: str = ...) -> str: ...


AuditFn = Callable[..., None]


class Interview:
    def __init__(
        self,
        client: LlmClient,
        scope_guard: ScopeGuard,
        repository: ProfileStore,
        *,
        language: str = "it",
        audit: AuditFn | None = None,
        redactor: TextRedactor | None = None,
    ) -> None:
        self._client = client
        self._guard = scope_guard
        self._repo = repository
        self._audit = audit
        self._language = language
        # Outbound PII filter for LLM-generated text shown to the person
        # (§7.3 "prima di mostrare"). Built lazily on first use if not injected,
        # so redaction is on by default; tests inject a light double.
        self._redactor = redactor
        self._session: InterviewSession | None = None
        self._awaiting_confirmation = False
        self._awaiting_final_clarification = False

    def _redact(self, text: str) -> str:
        """Redact personal data from LLM-generated text before it is shown to
        the person (§7.3). The base questions and the static refusal/unavailable/
        completed messages are author-controlled and need no redaction."""
        if not text:
            return text
        if self._redactor is None:
            self._redactor = PiiRedactor()
        return self._redactor.redact(text, self._language)

    def _question_step(self) -> Step:
        section = self._session.current_section  # type: ignore[union-attr]
        assert section is not None
        return Step("question", base_question(section, self._language))

    def _unavailable(self) -> Step:
        return Step("unavailable", unavailable_message(self._language))

    def start(self) -> Step:
        pseudonym = self._repo.create_new()
        self._session = InterviewSession(pseudonym, self._language)
        self._awaiting_confirmation = False
        self._awaiting_final_clarification = False
        return self._question_step()

    def _finalize(self, session: InterviewSession) -> Step:
        """All sections confirmed: run the incongruence check ONCE on the whole
        profile. A real cross-section contradiction surfaces a gentle
        clarification; otherwise the interview completes."""
        clarification = find_incongruence(self._client, session.profile, self._language)
        if clarification is not None:
            self._awaiting_final_clarification = True
            return Step("clarification", self._redact(clarification))
        return Step("completed", _final_summary(self._language))

    def submit(self, answer: str) -> Step:
        session = self._session
        assert session is not None, "call start() first"
        try:
            return self._submit(session, answer)
        except LlmUnavailable:
            return self._unavailable()
        except Exception:
            return self._unavailable()

    def _submit(self, session: InterviewSession, answer: str) -> Step:
        # Final incongruence surfaced: the person is replying to the gentle
        # clarification. Guard the reply, then complete (surfacing the question
        # and hearing the person is the Fase-1 contract; targeted re-extraction
        # from a final clarification is Fase 2).
        if self._awaiting_final_clarification:
            decision = self._guard.check(answer, self._language)
            if not decision.allow:
                return Step(
                    "refusal",
                    refusal_message(
                        decision.category or RefusalCategory.OUT_OF_SCOPE, self._language
                    ),
                )
            self._awaiting_final_clarification = False
            return Step("completed", _final_summary(self._language))

        if self._awaiting_confirmation:
            if interpret_confirmation(self._client, answer, self._language):
                # Confirmed by the person: persist this section and advance.
                # The incongruence check runs once at the end, on the whole
                # profile (contradictions are cross-section), NOT per section.
                self._repo.save(session.profile)
                if self._audit is not None:
                    self._audit(
                        action="interview_section_confirmed",
                        target_pseudonym=session.profile.pseudonym_id,
                    )
                self._awaiting_confirmation = False
                session.advance()
                if session.completed:
                    return self._finalize(session)
                return self._question_step()
            # not confirmed -> re-ask the section question
            self._awaiting_confirmation = False
            return self._question_step()

        # normal answer: guard -> extract -> summarize -> await confirmation
        section = session.current_section
        assert section is not None
        decision = self._guard.check(answer, self._language)
        if not decision.allow:
            return Step(
                "refusal",
                refusal_message(decision.category or RefusalCategory.OUT_OF_SCOPE, self._language),
            )
        extracted = extract_section(self._client, section, answer, self._language)
        summary_text = self._redact(summarize(self._client, section, extracted, self._language))
        session.merge(extracted)
        self._awaiting_confirmation = True
        return Step("summary", summary_text)


def _final_summary(language: str) -> str:
    messages = {
        "it": "Abbiamo finito, grazie! Ho raccolto il tuo profilo lavorativo.",
        "en": "We're done, thank you! I've gathered your work profile.",
        "fr": "C'est terminé, merci ! J'ai rassemblé ton profil professionnel.",
        "es": "Hemos terminado, ¡gracias! He reunido tu perfil laboral.",
        "ar": "لقد انتهينا، شكرًا لك! لقد جمعت ملفك المهني.",
    }
    return messages.get(language, messages["en"])
