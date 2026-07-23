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
    # answer2 (confirm): interpret_confirmation True (json), incongruence none (json) -> save+advance -> next question
    client = make_fake_json_llm(
        json_responses=[
            COMP,
            {"confirmed": True},
            {"has_incongruence": False, "clarification": ""},
        ],
        text_responses=[ALLOW, "Riepilogo: sai cucinare. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it")
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
