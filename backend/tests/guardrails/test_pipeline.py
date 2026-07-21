import pytest

from bussola.guardrails.pii import PiiRedactor
from bussola.guardrails.pipeline import GuardedConversation
from bussola.guardrails.refusal import RefusalCategory, unavailable_message
from bussola.guardrails.scope import ScopeGuard
from bussola.llm.client import LlmUnavailable


@pytest.fixture(scope="session")
def redactor() -> PiiRedactor:
    return PiiRedactor()


ALLOW = '{"allow": true, "category": null, "reason": "ok"}'
REFUSE = '{"allow": false, "category": "out_of_scope", "reason": "off"}'


def test_in_scope_answer_flows_through(make_fake_llm, redactor):
    # input-guard ALLOW, main answer, output-guard ALLOW
    client = make_fake_llm([ALLOW, "Puoi puntare sulla ristorazione.", ALLOW])
    convo = GuardedConversation(client, ScopeGuard(client), redactor, language="it")
    reply = convo.ask("mi piace cucinare")
    assert reply.refused is False
    assert "ristorazione" in reply.text


def test_input_refusal_short_circuits_main_call(make_fake_llm, redactor):
    client = make_fake_llm([REFUSE])  # only the input guard is consulted
    convo = GuardedConversation(client, ScopeGuard(client), redactor, language="it")
    reply = convo.ask("che tempo fa domani?")
    assert reply.refused is True
    assert reply.category is RefusalCategory.OUT_OF_SCOPE
    assert len(client.calls) == 1  # main answer + output guard NOT reached


def test_output_drift_is_refused(make_fake_llm, redactor):
    # input ALLOW, main drifts off-topic, output-guard REFUSE
    client = make_fake_llm([ALLOW, "Ecco una ricetta medica dettagliata...", REFUSE])
    convo = GuardedConversation(client, ScopeGuard(client), redactor, language="it")
    reply = convo.ask("parlami di lavoro")
    assert reply.refused is True


def test_pii_in_answer_is_redacted(make_fake_llm, redactor):
    client = make_fake_llm([ALLOW, "scrivi a mario.rossi@example.com", ALLOW])
    convo = GuardedConversation(client, ScopeGuard(client), redactor, language="it")
    reply = convo.ask("come ti contatto?")
    assert reply.refused is False
    assert "mario.rossi@example.com" not in reply.text


class _UnavailableLlmClient:
    """LLM double that always raises LlmUnavailable (server unreachable)."""

    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages, *, temperature=0.0, max_tokens=None) -> str:
        self.calls.append(messages)
        raise LlmUnavailable("local LLM server unreachable")


def test_llm_unavailable_returns_controlled_reply_without_raising(redactor):
    # §3.7 graceful degradation: LlmUnavailable must never propagate and
    # must never let any content through.
    client = _UnavailableLlmClient()
    convo = GuardedConversation(client, ScopeGuard(client), redactor, language="it")
    reply = convo.ask("parlami delle mie esperienze di lavoro")
    assert reply.refused is True
    assert reply.category is None
    assert reply.text == unavailable_message("it")
