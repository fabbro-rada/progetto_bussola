from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview
from bussola.llm.client import LlmUnavailable
from bussola.profile.models import WorkProfile


class FakeRepo:
    def __init__(self) -> None:
        self.saved: list[WorkProfile] = []
        self._n = 0

    def create_new(self) -> str:
        self._n += 1
        return f"P-{self._n}"

    def save(self, profile: WorkProfile) -> WorkProfile:
        self.saved.append(profile)
        return profile


ALLOW = '{"allow": true, "category": null, "reason": "ok"}'
REFUSE = '{"allow": false, "category": "out_of_scope", "reason": "off"}'
COMP = {
    "skills": [{"name": "cooking", "kind": "technical", "evidence": "stated"}],
    "languages": [],
    "digital_literacy": None,
}


class _FakeRedactor:
    """Light outbound-redaction double: records the text it saw and blanks a
    sentinel, so tests stay fast (no NLP models) and can prove redaction ran."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def redact(self, text: str, language: str = "it") -> str:
        self.seen.append(text)
        return text.replace("mario@example.com", "<EMAIL_ADDRESS>")


def test_start_returns_first_question(make_fake_json_llm):
    client = make_fake_json_llm()
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it")
    step = itw.start()
    assert step.kind == "question"
    assert step.text.strip()


def test_off_topic_answer_is_refused_and_does_not_advance(make_fake_json_llm):
    # scope guard consulted first (text call) -> REFUSE
    client = make_fake_json_llm(text_responses=[REFUSE])
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it")
    itw.start()
    step = itw.submit("che tempo fa domani?")
    assert step.kind == "refusal"


def test_confirmed_section_persists_and_advances(make_fake_json_llm):
    repo = FakeRepo()
    # answer1: guard ALLOW (text), extract COMP (json), summary (text)
    # answer2 (confirm): interpret_confirmation True (json) -> save + advance ->
    # next question. NO per-section incongruence check (it runs once at the end).
    client = make_fake_json_llm(
        json_responses=[COMP, {"confirmed": True}],
        text_responses=[ALLOW, "Riepilogo: sai cucinare. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    s1 = itw.submit("so cucinare")
    assert s1.kind == "summary"
    s2 = itw.submit("sì")
    assert s2.kind == "question"  # advanced to the next section
    assert len(repo.saved) == 1
    assert repo.saved[0].skills[0].name == "cooking"


def test_llm_unavailable_yields_controlled_step(make_fake_json_llm):
    class Boom:
        def chat(self, *a, **k):
            raise LlmUnavailable("down")

        def chat_json(self, *a, **k):
            raise LlmUnavailable("down")

    itw = Interview(Boom(), ScopeGuard(Boom()), FakeRepo(), language="it")
    itw.start()
    step = itw.submit("so cucinare")
    assert step.kind == "unavailable"


def test_summarize_failure_does_not_leave_awaiting_confirmation():
    # guard ALLOW (text call #1), extract COMP (json call #1), then the
    # summarize text call fails -> unavailable, and NO state must have been
    # mutated: the next answer must be re-guarded from scratch, not treated
    # as a confirmation reply (which would call interpret_confirmation/
    # chat_json instead of the guard's chat).
    class SummarizeDown:
        def __init__(self) -> None:
            self._chat_queue: list[str | None] = [ALLOW, None, REFUSE]
            self._json_queue: list[dict] = [COMP]

        def chat(self, messages, *, temperature=0.0, max_tokens=None):
            value = self._chat_queue.pop(0)
            if value is None:
                raise LlmUnavailable("summarize down")
            return value

        def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None):
            if not self._json_queue:
                raise AssertionError(
                    "unexpected chat_json call: still awaiting confirmation after failure"
                )
            return self._json_queue.pop(0)

    client = SummarizeDown()
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it")
    itw.start()
    step1 = itw.submit("so cucinare")
    assert step1.kind == "unavailable"
    # The next answer must go through a fresh guarded turn (guard -> REFUSE),
    # not be interpreted as a confirmation reply.
    step2 = itw.submit("che tempo fa domani?")
    assert step2.kind == "refusal"


# Valid empty payloads for the 5 sections, in fixed order.
_EMPTY_EXTRACTIONS = [
    {"skills": [], "languages": [], "digital_literacy": None},
    {"experiences": []},
    {"fields_of_interest": [], "desired_training": []},
    {"availability": None, "constraints": []},
    {"operational_notes": []},
]


def _confirm_all_sections(json_responses, text_responses):
    """Extend the fake client's scripted responses to drive all 5 sections:
    each section answer needs guard ALLOW (text) + extraction (json) + summary
    (text); each confirmation needs interpret_confirmation True (json)."""
    for extraction in _EMPTY_EXTRACTIONS:
        text_responses.extend([ALLOW, "Riepilogo. Giusto?"])
        json_responses.extend([extraction, {"confirmed": True}])


def test_full_interview_runs_incongruence_once_at_end(make_fake_json_llm):
    repo = FakeRepo()
    json_responses: list[dict] = []
    text_responses: list[str] = []
    _confirm_all_sections(json_responses, text_responses)
    # Exactly ONE incongruence check, at the very end, on the whole profile.
    json_responses.append({"has_incongruence": False, "clarification": ""})
    client = make_fake_json_llm(json_responses=json_responses, text_responses=text_responses)
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()

    last = None
    for _ in range(5):
        s = itw.submit("una risposta di lavoro")
        assert s.kind == "summary"
        last = itw.submit("sì, è corretto")
    assert last is not None and last.kind == "completed"
    assert len(repo.saved) == 5  # one save per confirmed section
    # All json responses consumed: 5*(extraction+confirm) + 1 final incongruence.
    assert not client._json


def test_final_incongruence_surfaces_clarification_then_completes(make_fake_json_llm):
    repo = FakeRepo()
    json_responses: list[dict] = []
    text_responses: list[str] = []
    _confirm_all_sections(json_responses, text_responses)
    # A real contradiction is reported at the end -> gentle clarification.
    json_responses.append({"has_incongruence": True, "clarification": "Puoi chiarire la durata?"})
    # The person's clarification reply is guarded (text) -> ALLOW -> completed.
    text_responses.append(ALLOW)
    client = make_fake_json_llm(json_responses=json_responses, text_responses=text_responses)
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()

    clar = None
    for _ in range(5):
        itw.submit("una risposta di lavoro")
        clar = itw.submit("sì, è corretto")
    assert clar is not None and clar.kind == "clarification"
    assert "chiarire" in clar.text
    # Replying to the clarification (in scope) completes the interview.
    final = itw.submit("La durata è di due anni, chiarito.")
    assert final.kind == "completed"


def test_generated_summary_is_pii_redacted_before_display(make_fake_json_llm):
    # The LLM-generated summary leaks an email; the outbound redactor must
    # scrub it before it is shown to the person (§7.3 "prima di mostrare").
    redactor = _FakeRedactor()
    client = make_fake_json_llm(
        json_responses=[COMP],
        text_responses=[ALLOW, "Sai cucinare. Scrivimi a mario@example.com. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it", redactor=redactor)
    itw.start()
    step = itw.submit("so cucinare")
    assert step.kind == "summary"
    assert "mario@example.com" not in step.text
    assert "<EMAIL_ADDRESS>" in step.text
    assert redactor.seen  # the redactor was actually consulted
