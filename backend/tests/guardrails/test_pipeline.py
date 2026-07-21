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
    # Not just the flag: the drifted content must actually be absent, never
    # merely marked-and-passed-through.
    assert "ricetta" not in reply.text


@pytest.mark.parametrize("language", ["fr", "es", "ar"])
def test_in_scope_answer_flows_through_in_every_supported_language(
    make_fake_llm, redactor, language
):
    # Locks in Fix 1 at the pipeline level: the redactor must not raise for
    # any of the five supported languages (CLAUDE.md §8), so an in-scope
    # answer in fr/es/ar must flow through end to end (ALLOW -> answer ->
    # ALLOW -> redact) exactly like it does for it/en.
    client = make_fake_llm([ALLOW, "Puoi puntare sulla ristorazione.", ALLOW])
    convo = GuardedConversation(client, ScopeGuard(client), redactor, language=language)
    reply = convo.ask("mi piace cucinare")
    assert reply.refused is False
    assert "ristorazione" in reply.text


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


class _FlakyRedactor:
    """Stand-in for a redactor whose call raises a generic, unforeseen fault
    (a bug, not a modeled `LlmUnavailable`) mid-flow, on the output path."""

    def redact(self, text: str, language: str = "it") -> str:
        raise RuntimeError("boom: unexpected redaction failure")


def test_unexpected_exception_mid_flow_returns_controlled_reply_without_raising(make_fake_llm):
    # §7.1 "the conversation must never block": a fault that is NOT
    # LlmUnavailable (here, a generic RuntimeError raised by a broken
    # redactor) must still degrade to the controlled unavailable reply —
    # never propagate, never let model content through. If this broad net
    # were missing (or a bug reintroduced a narrower except clause), this
    # test would fail with an uncaught RuntimeError instead of getting a
    # Reply back.
    client = make_fake_llm([ALLOW, "Puoi puntare sulla ristorazione.", ALLOW])
    convo = GuardedConversation(client, ScopeGuard(client), _FlakyRedactor(), language="it")
    reply = convo.ask("mi piace cucinare")
    assert reply.refused is True
    assert reply.category is None
    assert reply.text == unavailable_message("it")
    assert "ristorazione" not in reply.text
