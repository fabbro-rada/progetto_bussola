"""Deterministic interview orchestrator. The app drives the sections; the LLM
formulates, extracts, summarizes and checks incongruences. Degrades gracefully."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from bussola.guardrails.pii import PiiRedactor
from bussola.guardrails.refusal import RefusalCategory, refusal_message, unavailable_message
from bussola.guardrails.scope import ScopeGuard
from bussola.interview.clarify import apply_recap_correction, find_section_clarification
from bussola.interview.confirm import interpret_confirmation, summarize
from bussola.interview.extraction import extract_section
from bussola.interview.incongruence import find_incongruence
from bussola.interview.sections import Section, base_question
from bussola.interview.session import FollowupInterviewSession, InterviewSession
from bussola.llm.client import LlmClient, LlmUnavailable
from bussola.profile.models import WorkProfile


@dataclass(frozen=True)
class Step:
    kind: str  # question | summary | clarification | refusal | unavailable | completed | recap
    text: str
    recap: WorkProfile | None = None


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
        # Set once the interview has emitted the final RECAP step (§5): the
        # person is reviewing the whole confirmed profile before completion.
        # Confirming/correcting it is Task 4; this task only reaches and
        # carries it.
        self._awaiting_recap = False
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
        # Set while an open per-section clarification is pending a reply (§5/§7.1,
        # max ONE per section): kept True through the reply's guard check so
        # `_summarize_section`'s re-entry skips a second clarity check and goes
        # straight to the summary.
        self._awaiting_section_clarification = False
        # The open clarification question asked (if any), kept so the scope
        # guard can judge the reply as an answer to THAT question.
        self._section_clarification: str | None = None

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
        off-scope text.

        A trip is audited (`output_guard_blocked`, §7.3): a guardrail activation
        is a security-relevant event and must be accountable, not silent."""
        if not self._guard.check_output(text, self._language).allow:
            if self._audit is not None and self._session is not None:
                self._audit(
                    action="output_guard_blocked",
                    target_pseudonym=self._session.profile.pseudonym_id,
                )
            return None
        return self._redact(text)

    def _question_step(self) -> Step:
        section = self._session.current_section  # type: ignore[union-attr]
        assert section is not None
        return Step("question", base_question(section, self._language))

    def _unavailable(self) -> Step:
        return Step("unavailable", unavailable_message(self._language))

    def start(self) -> Step:
        """TEST-ONLY (re-identification, §5/§6): starts a FIRST interview on a
        freshly minted anonymous pseudonym. Production never takes this path —
        it would create a profile with no entry in the segregated identity
        register, unlinkable to any person. The kiosk provisions via an
        operator (start code) and starts with `start_on(pseudonym)`; this
        method is kept only for the section-flow unit tests."""
        pseudonym = self._repo.create_new()
        self._session = InterviewSession(pseudonym, self._language)
        self._awaiting_confirmation = False
        self._awaiting_final_clarification = False
        self._awaiting_recap = False
        self._section_answer = ""
        self._final_clarification = None
        self._last_summary = ""
        self._awaiting_section_clarification = False
        self._section_clarification = None
        return self._question_step()

    def start_on(self, pseudonym_id: str) -> Step:
        """Start a FIRST interview on a pre-created (empty) pseudonym (operator-
        provisioned). Full sections, overwrite merge — like start(), but the
        pseudonym/profile already exist, so we do not create a new one."""
        self._session = InterviewSession(pseudonym_id, self._language)
        self._awaiting_confirmation = False
        self._awaiting_final_clarification = False
        self._awaiting_recap = False
        self._section_answer = ""
        self._final_clarification = None
        self._last_summary = ""
        self._awaiting_section_clarification = False
        self._section_clarification = None
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
        self._awaiting_recap = False
        self._section_answer = ""
        self._final_clarification = None
        self._last_summary = ""
        self._awaiting_section_clarification = False
        self._section_clarification = None
        return self._question_step()

    def _finalize(self, session: InterviewSession) -> Step:
        """All sections confirmed: run the incongruence check ONCE on the whole
        profile. A real cross-section contradiction surfaces a gentle
        clarification; otherwise the interview enters the final recap (§5)."""
        clarification = find_incongruence(self._client, session.profile, self._language)
        if clarification is not None:
            shown = self._present(clarification)
            if shown is None:
                # The generated clarification failed the outbound scope guard —
                # never show it. It is an optional nicety, so skip it and go to
                # the recap rather than trap the person; the confirmed profile
                # stands (§3 degrado elegante).
                return self._enter_recap()
            self._awaiting_final_clarification = True
            self._final_clarification = clarification
            return Step("clarification", shown)
        return self._enter_recap()

    def _enter_recap(self) -> Step:
        """All sections confirmed and the incongruence check cleared (or was
        skipped/withheld): show the person a schematic recap of the whole
        saved profile before completion (§5 "riepilogo ... alla fine del
        colloquio"). Built directly from `session.profile` -- already
        PII-filtered on each section save -- so no LLM call is needed here.
        Confirming/correcting the recap is Task 4; this only reaches it."""
        session = self._session
        assert session is not None
        self._awaiting_recap = True
        return Step("recap", _recap_intro(self._language), recap=session.profile)

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
        # Recap surfaced (§5, terminal state): the person is confirming or
        # correcting the WHOLE saved profile. A confirmation completes the
        # interview; anything else is a free-text correction, routed to the
        # section it changes, re-extracted and re-shown as an updated recap
        # (never re-asked as a section question, never lost — fail-closed to
        # "keep the recap unchanged" if unroutable/on error).
        if self._awaiting_recap:
            if interpret_confirmation(self._client, answer, self._language):
                self._awaiting_recap = False
                return self._complete()
            decision = self._guard.check(
                answer, self._language, question=_recap_intro(self._language)
            )
            if not decision.allow:
                return Step(
                    "refusal",
                    refusal_message(
                        decision.category or RefusalCategory.OUT_OF_SCOPE, self._language
                    ),
                )
            if isinstance(session, FollowupInterviewSession):
                # Fail-closed (§3): `apply_recap_correction` re-extracts the
                # WHOLE routed section, but a follow-up session's `merge()`
                # uses APPEND/UPGRADE semantics. For experiences that is a
                # plain concatenation onto the baseline with NO dedup, so a
                # routed correction would silently duplicate the experience
                # (skills/aspirations happen to dedup by name/string, but the
                # risk is not section-specific and duplication must never
                # happen, §5). So no recap correction is ever applied on a
                # follow-up session: keep the recap unchanged and ask to
                # rephrase, exactly like the unroutable case.
                return Step("recap", _recap_retry(self._language), recap=session.profile)
            extracted = apply_recap_correction(
                self._client, answer, session.profile, self._language
            )
            if extracted is None:
                # not routable: keep the recap, ask to rephrase (static message)
                return Step("recap", _recap_retry(self._language), recap=session.profile)
            try:
                session.merge(extracted)
            except Exception:
                # The routed section is not one this session mode can merge
                # (e.g. a follow-up session, whose `merge()` only understands
                # experiences/skills/aspirations, routed to "constraints" or
                # "preferences"). Fail closed like the unroutable case: keep
                # the recap unchanged and ask to rephrase -- never crash to
                # `unavailable`, never lose the turn (§3).
                return Step("recap", _recap_retry(self._language), recap=session.profile)
            # `save` returns a re-validated, PII-redacted DEEP COPY (§7.3
            # "prima di mostrare") -- carry THAT forward, not the pre-save
            # profile, so the re-shown recap always reflects what was
            # actually persisted.
            session.profile = self._repo.save(session.profile)
            return Step("recap", _recap_intro(self._language), recap=session.profile)

        # Final incongruence surfaced: the person is replying to the gentle
        # clarification. Guard the reply, then enter the recap (surfacing the
        # question and hearing the person is the Fase-1 contract; targeted
        # re-extraction from a final clarification is Fase 2).
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
            return self._enter_recap()

        # Open per-section clarification surfaced: the person is replying to
        # it. Guard the reply against THAT question, append it to the
        # section's accumulated answer, and re-extract — `_awaiting_section_
        # clarification` stays True through this, so `_summarize_section`
        # skips a second clarity check (max ONE per section, §5/§7.1) and
        # goes straight to the summary (which clears the flag).
        if self._awaiting_section_clarification:
            section = session.current_section
            assert section is not None
            decision = self._guard.check(
                answer,
                self._language,
                question=self._section_clarification or base_question(section, self._language),
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

        if self._awaiting_confirmation:
            if interpret_confirmation(self._client, answer, self._language):
                # Confirmed by the person: persist this section and advance.
                # The incongruence check runs once at the end, on the whole
                # profile (contradictions are cross-section), NOT per section.
                # `save` returns a re-validated, PII-redacted DEEP COPY (§7.3
                # "prima di mostrare") -- carry THAT forward so the eventual
                # recap (and any later save) reflects what was persisted, not
                # the raw pre-save profile.
                session.profile = self._repo.save(session.profile)
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
        correction re-extracts from the full text (original + corrections).

        Before building the summary, checks whether the extraction is
        ambiguous (§5/§7.1): if so, and this isn't already the re-entry after
        that clarification's reply, it emits an open `clarification` step
        instead (max ONE per section — `_awaiting_section_clarification`
        stays True through the reply, so the re-entry falls straight through
        to the summary)."""
        extracted = extract_section(self._client, section, self._section_answer, self._language)
        if not self._awaiting_section_clarification:
            question = find_section_clarification(
                self._client, section, extracted, session.profile, self._language
            )
            if question is not None:
                shown = self._present(question)
                if shown is not None:  # off-scope generated text withheld (§9); else fall through
                    self._awaiting_section_clarification = True
                    self._section_clarification = question
                    return Step("clarification", shown)
        self._awaiting_section_clarification = False
        self._section_clarification = None
        summary_text = self._present(summarize(self._client, section, extracted, self._language))
        if summary_text is None:
            # The generated summary failed the outbound scope guard (§9, already
            # audited in `_present`). Rather than dead-end on `unavailable` — a
            # deterministic re-trip on the same input would soft-lock the section
            # — fall back to a safe, guaranteed-in-scope generic confirmation of
            # the extracted data. What was withheld is only the model's free-text
            # phrasing; the extracted data is schema-constrained and separately
            # validated, so confirming it stays sound (§3 degrado elegante).
            summary_text = _generic_confirmation(self._language)
        session.merge(extracted)
        self._awaiting_confirmation = True
        # Remember it so a correction reply is scope-judged against this summary.
        self._last_summary = summary_text
        return Step("summary", summary_text)


def _recap_intro(language: str) -> str:
    messages = {
        "it": "Ecco cosa ho capito del tuo profilo. Controlla che sia giusto.",
        "en": "Here's what I understood about your profile. Please check it's right.",
        "fr": "Voici ce que j'ai compris de ton profil. Vérifie que c'est correct.",
        "es": "Esto es lo que he entendido de tu perfil. Comprueba que esté bien.",
        "ar": "هذا ما فهمته عن ملفك. تحقّق من أنه صحيح.",
    }
    return messages.get(language, messages["en"])


def _recap_retry(language: str) -> str:
    messages = {
        "it": "Non ho capito la correzione. Puoi ridirla in modo semplice?",
        "en": "I didn't catch that correction. Can you say it again simply?",
        "fr": "Je n'ai pas compris la correction. Peux-tu la redire simplement ?",
        "es": "No he entendido la corrección. ¿Puedes repetirla de forma sencilla?",
        "ar": "لم أفهم التصحيح. هل يمكنك إعادته ببساطة؟",
    }
    return messages.get(language, messages["en"])


def _final_summary(language: str) -> str:
    messages = {
        "it": "Abbiamo finito, grazie! Ho raccolto il tuo profilo lavorativo.",
        "en": "We're done, thank you! I've gathered your work profile.",
        "fr": "C'est terminé, merci ! J'ai rassemblé ton profil professionnel.",
        "es": "Hemos terminado, ¡gracias! He reunido tu perfil laboral.",
        "ar": "لقد انتهينا، شكرًا لك! لقد جمعت ملفك المهني.",
    }
    return messages.get(language, messages["en"])


def _generic_confirmation(language: str) -> str:
    """Safe, author-controlled fallback shown when the outbound guard blocks a
    generated section summary: asks the person to confirm without echoing the
    (withheld) model text. Kept in the 5 supported languages like the other
    static messages; ar wording is provisional pending native-speaker review."""
    messages = {
        "it": "Ho registrato la tua risposta. È corretto?",
        "en": "I've noted your answer. Is that correct?",
        "fr": "J'ai bien noté ta réponse. C'est correct ?",
        "es": "He anotado tu respuesta. ¿Es correcto?",
        "ar": "لقد سجّلت إجابتك. هل هذا صحيح؟",
    }
    return messages.get(language, messages["en"])
