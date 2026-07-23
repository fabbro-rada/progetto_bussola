"""Deterministic interview orchestrator. The app drives the sections; the LLM
formulates, extracts, summarizes and checks incongruences. Degrades gracefully."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

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
    ) -> None:
        self._client = client
        self._guard = scope_guard
        self._repo = repository
        self._audit = audit
        self._language = language
        self._session: InterviewSession | None = None
        self._awaiting_confirmation = False

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
        return self._question_step()

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
        section = session.current_section
        assert section is not None

        if self._awaiting_confirmation:
            if interpret_confirmation(self._client, answer, self._language):
                clarification = find_incongruence(self._client, session.profile, self._language)
                if clarification is not None:
                    # Re-open the section: the next submit is a fresh answer
                    # (guard -> extract -> summarize) that re-confirms.
                    self._awaiting_confirmation = False
                    return Step("clarification", clarification)
                self._repo.save(session.profile)
                if self._audit is not None:
                    self._audit(
                        action="interview_section_confirmed",
                        target_pseudonym=session.profile.pseudonym_id,
                    )
                self._awaiting_confirmation = False
                session.advance()
                if session.completed:
                    return Step("completed", _final_summary(self._language))
                return self._question_step()
            # not confirmed -> re-ask the section question
            self._awaiting_confirmation = False
            return self._question_step()

        # normal answer: guard -> extract -> summarize -> await confirmation
        decision = self._guard.check(answer, self._language)
        if not decision.allow:
            return Step(
                "refusal",
                refusal_message(decision.category or RefusalCategory.OUT_OF_SCOPE, self._language),
            )
        extracted = extract_section(self._client, section, answer, self._language)
        session.merge(extracted)
        self._awaiting_confirmation = True
        return Step("summary", summarize(self._client, section, extracted, self._language))


def _final_summary(language: str) -> str:
    messages = {
        "it": "Abbiamo finito, grazie! Ho raccolto il tuo profilo lavorativo.",
        "en": "We're done, thank you! I've gathered your work profile.",
        "fr": "C'est terminé, merci ! J'ai rassemblé ton profil professionnel.",
        "es": "Hemos terminado, ¡gracias! He reunido tu perfil laboral.",
        "ar": "لقد انتهينا، شكرًا لك! لقد جمعت ملفك المهني.",
    }
    return messages.get(language, messages["en"])
