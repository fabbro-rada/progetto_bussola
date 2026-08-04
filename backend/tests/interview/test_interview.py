from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview
from bussola.interview.sections import SECTIONS, base_question
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


def test_start_on_uses_the_given_pseudonym_without_creating_a_new_one(make_fake_json_llm):
    repo = FakeRepo()
    itw = Interview(make_fake_json_llm(), ScopeGuard(make_fake_json_llm()), repo, language="it")
    step = itw.start_on("P-fixed")
    assert step.kind == "question"
    assert repo.saved == []  # nothing saved yet
    # first confirmed section must persist under P-fixed (not a create_new pseudonym)


def test_start_on_confirmed_section_persists_under_the_given_pseudonym(make_fake_json_llm):
    repo = FakeRepo()
    client = make_fake_json_llm(
        json_responses=[COMP, {"needs_clarification": False, "question": ""}, {"confirmed": True}],
        text_responses=[ALLOW, "Riepilogo: sai cucinare. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it")
    itw.start_on("P-fixed")
    s1 = itw.submit("so cucinare")
    assert s1.kind == "summary"
    s2 = itw.submit("sì")
    assert s2.kind == "question"  # advanced to the next section
    assert len(repo.saved) == 1
    # start_on must NOT have called repo.create_new(): the saved profile is
    # keyed by the pseudonym we passed in, not a freshly minted one.
    assert repo.saved[0].pseudonym_id == "P-fixed"


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
        json_responses=[COMP, {"needs_clarification": False, "question": ""}, {"confirmed": True}],
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


def test_correction_updates_the_same_section_without_re_asking(make_fake_json_llm):
    # The person answers, sees the summary, and instead of confirming ADDS
    # something ("ho fatto anche il cameriere"). That reply must update the same
    # section (re-extract from original + correction, re-summarize), NOT re-ask
    # the section question and discard the correction.
    repo = FakeRepo()
    two_skills = {
        "skills": [
            {"name": "falegname", "kind": "technical", "evidence": "stated"},
            {"name": "muratore", "kind": "technical", "evidence": "stated"},
        ],
        "languages": [],
        "digital_literacy": None,
    }
    three_skills = {
        "skills": two_skills["skills"]
        + [
            {"name": "cameriere", "kind": "technical", "evidence": "stated"},
        ],
        "languages": [],
        "digital_literacy": None,
    }
    client = make_fake_json_llm(
        # a1: guard ALLOW(text) + extract two_skills(json) + clarity NO(json) + summary(text)
        # a2 (correction): interpret_confirmation False(json) + guard ALLOW(text)
        #                  + re-extract three_skills(json) + clarity NO(json) + summary(text)
        # a3 (confirm):    interpret_confirmation True(json) -> save + advance
        json_responses=[
            two_skills,
            {"needs_clarification": False, "question": ""},
            {"confirmed": False},
            three_skills,
            {"needs_clarification": False, "question": ""},
            {"confirmed": True},
        ],
        text_responses=[
            ALLOW,
            "So fare il falegname e il muratore. Giusto?",
            ALLOW,
            "Falegname, muratore e cameriere. Giusto?",
        ],
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    s1 = itw.submit("faccio il falegname e il muratore")
    assert s1.kind == "summary"
    s2 = itw.submit("ho fatto anche il cameriere")
    assert s2.kind == "summary"  # stayed on the section, did NOT re-ask
    s3 = itw.submit("sì")
    assert s3.kind == "question"  # confirmed -> advanced
    assert len(repo.saved) == 1
    saved_skills = {s.name for s in repo.saved[0].skills}
    assert saved_skills == {"falegname", "muratore", "cameriere"}  # correction kept + added


def test_scope_guard_judges_the_answer_with_the_question_as_context(make_fake_json_llm):
    # The guard must see the section question, so a short answer that only makes
    # sense against it is judged in context (§2/§9), not on the answer alone.
    client = make_fake_json_llm(
        json_responses=[COMP, {"needs_clarification": False, "question": ""}],
        text_responses=[ALLOW, "Riepilogo. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it", redactor=_FakeRedactor())
    itw.start()
    itw.submit("arabo")
    guard_call = client.calls[0]  # first call is the scope guard (chat/text)
    assert guard_call["kind"] == "text"
    assert base_question(SECTIONS[0], "it") in guard_call["messages"][1]["content"]


def test_correction_is_scope_judged_against_the_summary_not_the_question(make_fake_json_llm):
    # A correction reply ("no, anche cameriere") must be judged as an answer to
    # the summary it corrects ("…Giusto?"), so a short/negative reply is NOT
    # refused as off-topic against the section question.
    repo = FakeRepo()
    skills = {
        "skills": [{"name": "falegname", "kind": "technical", "evidence": "stated"}],
        "languages": [],
        "digital_literacy": None,
    }
    client = make_fake_json_llm(
        json_responses=[
            skills,
            {"needs_clarification": False, "question": ""},
            {"confirmed": False},
            skills,
            {"needs_clarification": False, "question": ""},
        ],
        text_responses=[
            ALLOW,
            "Ho capito: falegname. Giusto?",
            ALLOW,
            "Ho capito: falegname. Giusto?",
        ],
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    itw.submit("faccio il falegname")  # -> summary "Ho capito: falegname. Giusto?"
    itw.submit("no, anche cameriere")  # correction
    # calls: 0 guard(a1,text) 1 extract(json) 2 clarity(json) 3 summary(text)
    #        4 interpret(json) 5 guard(correction,text) ...
    guard_correction = client.calls[5]
    assert guard_correction["kind"] == "text"
    assert "Ho capito: falegname. Giusto?" in guard_correction["messages"][1]["content"]


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
    each section answer needs guard ALLOW (text) + extraction (json) + clarity
    check "no clarification needed" (json) + summary (text); each confirmation
    needs interpret_confirmation True (json)."""
    for extraction in _EMPTY_EXTRACTIONS:
        text_responses.extend([ALLOW, "Riepilogo. Giusto?"])
        json_responses.extend(
            [extraction, {"needs_clarification": False, "question": ""}, {"confirmed": True}]
        )


def test_interview_ends_with_a_recap_carrying_the_profile(make_fake_json_llm):
    repo = FakeRepo()
    json_responses, text_responses = [], []
    _confirm_all_sections(
        json_responses, text_responses
    )  # each section: extract + clarity(false) + confirm
    json_responses.append({"has_incongruence": False, "clarification": ""})
    client = make_fake_json_llm(json_responses=json_responses, text_responses=text_responses)
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    last = None
    for _ in range(5):
        assert itw.submit("una risposta di lavoro").kind == "summary"
        last = itw.submit("sì, è corretto")
    assert last is not None and last.kind == "recap"
    assert last.recap is not None and last.recap.pseudonym_id  # carries the saved profile


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
    # The interview now ends at the RECAP step (not "completed"): completing
    # requires confirming the recap, which is Task 4.
    assert last is not None and last.kind == "recap"
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
    # Replying to the clarification (in scope) now yields the RECAP step (not
    # "completed" directly) -- completing requires confirming the recap (Task 4).
    final = itw.submit("La durata è di due anni, chiarito.")
    assert final.kind == "recap"


def test_generated_summary_is_pii_redacted_before_display(make_fake_json_llm):
    # The LLM-generated summary leaks an email; the outbound redactor must
    # scrub it before it is shown to the person (§7.3 "prima di mostrare").
    redactor = _FakeRedactor()
    client = make_fake_json_llm(
        json_responses=[COMP, {"needs_clarification": False, "question": ""}],
        text_responses=[ALLOW, "Sai cucinare. Scrivimi a mario@example.com. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it", redactor=redactor)
    itw.start()
    step = itw.submit("so cucinare")
    assert step.kind == "summary"
    assert "mario@example.com" not in step.text
    assert "<EMAIL_ADDRESS>" in step.text
    assert redactor.seen  # the redactor was actually consulted


def test_blocked_summary_falls_back_to_generic_confirmation_and_audits(make_fake_json_llm):
    # §9 "guardrail in uscita": the generated summary is scope-checked on the way
    # out. When it is blocked, the model's off-scope phrasing must be WITHHELD —
    # but rather than dead-end on `unavailable` (a deterministic re-trip would
    # soft-lock the section), the person gets a safe generic confirmation of the
    # (schema-constrained) extracted data, and the trip is audited (§7.3).
    events: list[dict] = []
    repo = FakeRepo()
    client = make_fake_json_llm(
        json_responses=[COMP, {"needs_clarification": False, "question": ""}, {"confirmed": True}],
        text_responses=[ALLOW, "Riepilogo con contenuto fuori ambito. Giusto?"],
        output_responses=[REFUSE],  # the OUTBOUND guard rejects the generated summary
    )
    itw = Interview(
        client,
        ScopeGuard(client),
        repo,
        language="it",
        audit=lambda **kw: events.append(kw),
        redactor=_FakeRedactor(),
    )
    itw.start()
    step = itw.submit("so cucinare")
    assert step.kind == "summary"  # NOT unavailable — the flow continues
    assert step.text.strip()
    assert step.text != "Riepilogo con contenuto fuori ambito. Giusto?"  # off-scope text withheld
    # the outbound guard ran on the generated summary text, and the trip was audited
    assert client.output_calls
    assert any(e["action"] == "output_guard_blocked" for e in events)
    # the person can confirm normally -> the schema-constrained data is persisted
    s2 = itw.submit("sì")
    assert s2.kind == "question"  # advanced to the next section
    assert repo.saved and repo.saved[0].skills[0].name == "cooking"


def test_final_clarification_failing_outbound_scope_guard_is_skipped_and_completes(
    make_fake_json_llm,
):
    # If the generated final clarification fails the outbound scope guard, it is
    # skipped and the interview completes (the confirmed profile stands) rather
    # than showing off-scope text or trapping the person (§3/§9).
    repo = FakeRepo()
    json_responses: list[dict] = []
    text_responses: list[str] = []
    _confirm_all_sections(json_responses, text_responses)
    json_responses.append({"has_incongruence": True, "clarification": "Testo fuori ambito?"})
    # 5 section summaries pass the outbound guard; the final clarification (6th
    # outbound check) is rejected.
    output_responses = [ALLOW, ALLOW, ALLOW, ALLOW, ALLOW, REFUSE]
    events: list[dict] = []
    client = make_fake_json_llm(
        json_responses=json_responses,
        text_responses=text_responses,
        output_responses=output_responses,
    )
    itw = Interview(
        client,
        ScopeGuard(client),
        repo,
        language="it",
        audit=lambda **kw: events.append(kw),
        redactor=_FakeRedactor(),
    )
    itw.start()
    last = None
    for _ in range(5):
        assert itw.submit("una risposta di lavoro").kind == "summary"
        last = itw.submit("sì, è corretto")
    # clarification skipped (not shown), so the interview falls straight through
    # to the recap step (not "completed" -- Task 4 completes after confirmation).
    assert last is not None and last.kind == "recap"
    # the clarification trip is audited too (§7.3), like the summary trip
    assert any(e["action"] == "output_guard_blocked" for e in events)


def test_ambiguous_section_asks_one_open_clarification_then_summarizes(make_fake_json_llm):
    # answer -> guard ALLOW(text) + extract(json) + clarity NEEDS(json) -> clarification step;
    # reply -> guard ALLOW(text) + re-extract(json) + clarity SKIPPED (only once) -> summary(text)
    skills = {"skills": [], "languages": [], "digital_literacy": None}
    client = make_fake_json_llm(
        json_responses=[
            skills,
            {"needs_clarification": True, "question": "Che sai fare di preciso?"},
            skills,
        ],
        text_responses=[ALLOW, ALLOW, "Ho capito. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it", redactor=_FakeRedactor())
    itw.start()
    s1 = itw.submit("boh, cose")
    assert s1.kind == "clarification" and "preciso" in s1.text
    s2 = itw.submit("so cucinare")
    assert s2.kind == "summary"  # one clarification only, then summary


def test_clear_section_skips_clarification(make_fake_json_llm):
    skills = {
        "skills": [{"name": "cucina", "kind": "technical", "evidence": "stated"}],
        "languages": [],
        "digital_literacy": None,
    }
    client = make_fake_json_llm(
        json_responses=[skills, {"needs_clarification": False, "question": ""}],
        text_responses=[ALLOW, "Sai cucinare. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), FakeRepo(), language="it", redactor=_FakeRedactor())
    itw.start()
    assert itw.submit("so cucinare").kind == "summary"


def test_recap_confirm_completes(make_fake_json_llm):
    repo = FakeRepo()
    json_responses, text_responses = [], []
    _confirm_all_sections(json_responses, text_responses)
    json_responses.append({"has_incongruence": False, "clarification": ""})
    json_responses.append({"confirmed": True})  # recap confirm
    client = make_fake_json_llm(json_responses=json_responses, text_responses=text_responses)
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    for _ in range(5):
        itw.submit("una risposta di lavoro")
        itw.submit("sì, è corretto")
    assert itw.submit("sì, è tutto giusto").kind == "completed"


def test_recap_correction_reextracts_and_reshows(make_fake_json_llm):
    repo = FakeRepo()
    json_responses, text_responses = [], []
    _confirm_all_sections(json_responses, text_responses)
    json_responses.append({"has_incongruence": False, "clarification": ""})
    json_responses.append({"confirmed": False})  # not a confirmation -> correction
    json_responses.append({"section": "experiences"})  # routing
    json_responses.append(
        {"experiences": [{"role": "consulente", "sector": "IT", "duration_months": 24}]}
    )  # re-extract
    client = make_fake_json_llm(
        json_responses=json_responses, text_responses=[*text_responses, ALLOW]
    )  # guard on the correction
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    for _ in range(5):
        itw.submit("una risposta di lavoro")
        itw.submit("sì, è corretto")
    step = itw.submit("no, il consulente era 2 anni")
    assert step.kind == "recap"
    assert any(e.role == "consulente" and e.duration_months == 24 for e in step.recap.experiences)


def test_recap_off_scope_reply_is_refused(make_fake_json_llm):
    # While awaiting the recap, a reply the scope guard REJECTS must be a
    # refusal -- neither treated as a confirmation (it isn't one) nor as a
    # correction to route (it must never reach apply_recap_correction).
    repo = FakeRepo()
    json_responses, text_responses = [], []
    _confirm_all_sections(json_responses, text_responses)
    json_responses.append({"has_incongruence": False, "clarification": ""})
    json_responses.append({"confirmed": False})  # not a confirmation -> guard next
    client = make_fake_json_llm(
        json_responses=json_responses, text_responses=[*text_responses, REFUSE]
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    for _ in range(5):
        itw.submit("una risposta di lavoro")
        itw.submit("sì, è corretto")
    step = itw.submit("che tempo fa domani?")
    assert step.kind == "refusal"


class _SanitizingRepo(FakeRepo):
    """Fake repo whose save() returns a DISTINCT sanitized deep copy, like the
    real ProfileRepository.save (§7.3 "prima di mostrare"): PII redaction runs
    on a copy, never on the object the caller passed in. Proves the interview
    must carry the RETURNED profile forward, not the pre-save one."""

    def save(self, profile: WorkProfile) -> WorkProfile:
        clean = profile.model_copy(deep=True)
        for skill in clean.skills:
            skill.name = "<REDACTED>"
        for experience in clean.experiences:
            experience.role = "<REDACTED>"
        self.saved.append(clean)
        return clean


def test_recap_shows_the_sanitized_profile_returned_by_confirmation_save(make_fake_json_llm):
    # The section-confirmation save site must flow save()'s return value back
    # into the session, so the eventual recap reflects what was actually
    # persisted (sanitized), not the raw pre-save profile.
    repo = _SanitizingRepo()
    skills_with_name = {
        "skills": [{"name": "cucina", "kind": "technical", "evidence": "stated"}],
        "languages": [],
        "digital_literacy": None,
    }
    json_responses: list[dict] = []
    text_responses: list[str] = []
    for extraction in [skills_with_name, *_EMPTY_EXTRACTIONS[1:]]:
        text_responses.extend([ALLOW, "Riepilogo. Giusto?"])
        json_responses.extend(
            [extraction, {"needs_clarification": False, "question": ""}, {"confirmed": True}]
        )
    json_responses.append({"has_incongruence": False, "clarification": ""})
    client = make_fake_json_llm(json_responses=json_responses, text_responses=text_responses)
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    last = None
    for _ in range(5):
        itw.submit("una risposta di lavoro")
        last = itw.submit("sì, è corretto")
    assert last is not None and last.kind == "recap"
    assert last.recap is not None
    assert last.recap.skills and last.recap.skills[0].name == "<REDACTED>"


def test_recap_correction_shows_the_sanitized_profile_returned_by_save(make_fake_json_llm):
    # The recap-correction save site must ALSO flow save()'s return value back
    # into the re-shown recap, not the pre-save (freshly merged) profile.
    repo = _SanitizingRepo()
    json_responses, text_responses = [], []
    _confirm_all_sections(json_responses, text_responses)
    json_responses.append({"has_incongruence": False, "clarification": ""})
    json_responses.append({"confirmed": False})  # not a confirmation -> correction
    json_responses.append({"section": "experiences"})  # routing
    json_responses.append(
        {"experiences": [{"role": "consulente", "sector": "IT", "duration_months": 24}]}
    )  # re-extract
    client = make_fake_json_llm(
        json_responses=json_responses, text_responses=[*text_responses, ALLOW]
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it", redactor=_FakeRedactor())
    itw.start()
    for _ in range(5):
        itw.submit("una risposta di lavoro")
        itw.submit("sì, è corretto")
    step = itw.submit("no, il consulente era 2 anni")
    assert step.kind == "recap"
    assert step.recap is not None
    assert step.recap.experiences and all(e.role == "<REDACTED>" for e in step.recap.experiences)
