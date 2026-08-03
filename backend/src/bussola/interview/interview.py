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
from bussola.interview.sections import Section, base_question
from bussola.interview.session import FollowupInterviewSession, InterviewSession
from bussola.llm.client import LlmClient, LlmUnavailable
from bussola.profile.models import WorkProfile


@dataclass(frozen=True)
class Step:
    kind: str  # question | summary | clarification | refusal | unavailable | completed
    text: str


class ProfileStore(Protocol):
    def create_new(self) -> str: ...
    def save(self, profile: WorkProfile) -> WorkProfile: ...
    def get(self, pseudonym_id: str) -> WorkProfile | None: ...


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
        # The current section's answer text, accumulated across corrections: a
        # "not confirmed" reply is a correction to the SAME section, so we keep
        # the original answer plus each correction and re-extract from the whole
        # (§5 "confermare o correggere") instead of re-asking and losing it.
        self._section_answer = ""
        # The final clarification question we asked (if any), kept so the scope
        # guard can judge the reply as an answer to THAT question.
        self._final_clarification: str | None = None
        # The last summary shown ("I understood X. Is it correct?"), kept so a
        # correction reply is scope-judged as an answer to THAT confirmation —
        # otherwise a plain "no"/short correction is measured against the section
        # question and wrongly refused as off-topic.
        self._last_summary: str = ""

    def _redact(self, text: str) -> str:
        """Redact personal data from LLM-generated text before it is shown to
        the person (§7.3). The base questions and the static refusal/unavailable/
        completed messages are author-controlled and need no redaction."""
        if not text:
            return text
        if self._redactor is None:
            self._redactor = PiiRedactor()
        return self._redactor.redact(text, self._language)

    def _present(self, text: str) -> str | None:
        """Outbound gate for LLM-generated, person-facing text (summaries and
        clarifications): scope-check the OUTPUT (§9, fail-closed) THEN redact PII
        (§7.3 "prima di mostrare"). Returns the safe text to show, or None if the
        output scope guard tripped — the model produced off-scope content, which
        must never be shown. Defense in depth: the person's input was already
        scope-checked and the summary is built from constrained extraction, so
        this should essentially never trip in normal use; it exists so a
        manipulated/malfunctioning model cannot make the assistant emit
        off-scope text."""
        if not self._guard.check_output(text, self._language).allow:
            return None
        return self._redact(text)

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
        self._section_answer = ""
        self._final_clarification = None
        self._last_summary = ""
        return self._question_step()

    def start_on(self, pseudonym_id: str) -> Step:
        """Start a FIRST interview on a pre-created (empty) pseudonym (operator-
        provisioned). Full sections, overwrite merge — like start(), but the
        pseudonym/profile already exist, so we do not create a new one."""
        self._session = InterviewSession(pseudonym_id, self._language)
        self._awaiting_confirmation = False
        self._awaiting_final_clarification = False
        self._section_answer = ""
        self._final_clarification = None
        self._last_summary = ""
        return self._question_step()

    def start_followup(self, pseudonym_id: str) -> Step:
        """Start a follow-up interview on an EXISTING pseudonym's profile:
        a reduced section order, append/upgrade merge (§5, never lose prior
        data). Fails closed on an unknown pseudonym — never raises to the
        caller."""
        profile = self._repo.get(pseudonym_id)
        if profile is None:
            return self._unavailable()
        self._session = InterviewSession.for_followup(profile, self._language)
        self._awaiting_confirmation = False
        self._awaiting_final_clarification = False
        self._section_answer = ""
        self._final_clarification = None
        self._last_summary = ""
        return self._question_step()

    def _finalize(self, session: InterviewSession) -> Step:
        """All sections confirmed: run the incongruence check ONCE on the whole
        profile. A real cross-section contradiction surfaces a gentle
        clarification; otherwise the interview completes."""
        clarification = find_incongruence(self._client, session.profile, self._language)
        if clarification is not None:
            shown = self._present(clarification)
            if shown is None:
                # The generated clarification failed the outbound scope guard —
                # never show it. It is an optional nicety, so skip it and finish
                # rather than trap the person; the confirmed profile stands (§3
                # degrado elegante).
                return self._complete()
            self._awaiting_final_clarification = True
            self._final_clarification = clarification
            return Step("clarification", shown)
        return self._complete()

    def _complete(self) -> Step:
        """Common completion path (reached either directly from `_finalize`,
        or after the person clears a final clarification in `_submit`).

        A FOLLOW-UP session additionally gets a `followup_completed` audit
        event (§7.3 accountability): an auditor must be able to tell "this
        follow-up ran to completion" apart from "confirmed some sections and
        walked away", which the existing per-section
        `interview_section_confirmed` audit alone cannot distinguish. The
        first-interview flow is deliberately unaffected — it never emitted a
        completion audit before this and still doesn't, so S4 behavior is
        unchanged."""
        session = self._session
        if self._audit is not None and isinstance(session, FollowupInterviewSession):
            self._audit(
                action="followup_completed",
                target_pseudonym=session.profile.pseudonym_id,
            )
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
            decision = self._guard.check(answer, self._language, question=self._final_clarification)
            if not decision.allow:
                return Step(
                    "refusal",
                    refusal_message(
                        decision.category or RefusalCategory.OUT_OF_SCOPE, self._language
                    ),
                )
            self._awaiting_final_clarification = False
            return self._complete()

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
                self._section_answer = ""
                session.advance()
                if session.completed:
                    return self._finalize(session)
                return self._question_step()
            # Not confirmed -> the reply is a CORRECTION to the SAME section
            # (§5 "confermare o correggere"), NOT a request to start over. Guard
            # it, append it to the section's accumulated answer, re-extract from
            # the whole thing, and re-summarize — so an addition/change is folded
            # in and nothing already said is lost. We stay on the section.
            section = session.current_section
            assert section is not None
            # Judge the correction as a reply to the summary it corrects ("…Giusto?"),
            # not to the section question — else a plain "no" is refused as off-topic.
            decision = self._guard.check(
                answer,
                self._language,
                question=self._last_summary or base_question(section, self._language),
            )
            if not decision.allow:
                return Step(
                    "refusal",
                    refusal_message(
                        decision.category or RefusalCategory.OUT_OF_SCOPE, self._language
                    ),
                )
            self._section_answer = f"{self._section_answer}\n{answer}".strip()
            return self._summarize_section(session, section)

        # normal answer: guard -> extract -> summarize -> await confirmation
        section = session.current_section
        assert section is not None
        decision = self._guard.check(
            answer, self._language, question=base_question(section, self._language)
        )
        if not decision.allow:
            return Step(
                "refusal",
                refusal_message(decision.category or RefusalCategory.OUT_OF_SCOPE, self._language),
            )
        self._section_answer = answer
        return self._summarize_section(session, section)

    def _summarize_section(self, session: InterviewSession, section: Section) -> Step:
        """Extract from the section's accumulated answer, merge it into the
        partial profile, and return the summary step, awaiting confirmation.
        Shared by a first answer and every subsequent correction, so a
        correction re-extracts from the full text (original + corrections)."""
        extracted = extract_section(
            self._client, section, self._section_answer, self._language
        )
        summary_text = self._present(summarize(self._client, section, extracted, self._language))
        if summary_text is None:
            # The generated summary failed the outbound scope guard (§9): never
            # show it, and mutate no state (no merge, not awaiting) — the person
            # simply gets the graceful-degrade step and can answer again.
            return self._unavailable()
        session.merge(extracted)
        self._awaiting_confirmation = True
        # Remember it so a correction reply is scope-judged against this summary.
        self._last_summary = summary_text
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
