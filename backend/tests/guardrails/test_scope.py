from bussola.guardrails.prompts import scope_classifier_prompt
from bussola.guardrails.refusal import RefusalCategory
from bussola.guardrails.scope import ScopeGuard


def test_scope_prompt_treats_confirmation_and_correction_replies_as_in_scope():
    # A reply to a "…is it correct?" summary (yes / no / a correction) must be
    # allowed — otherwise a plain "no" during confirmation is wrongly refused.
    p = scope_classifier_prompt().lower()
    assert "confirm or correct" in p
    assert "in-scope" in p


def test_allows_in_scope(make_fake_llm):
    client = make_fake_llm(['{"allow": true, "category": null, "reason": "work"}'])
    decision = ScopeGuard(client).check("ho lavorato come cuoco", "it")
    assert decision.allow is True
    assert decision.category is None


def test_refuses_out_of_scope(make_fake_llm):
    client = make_fake_llm(['{"allow": false, "category": "out_of_scope", "reason": "medical"}'])
    decision = ScopeGuard(client).check("che medicine devo prendere?", "it")
    assert decision.allow is False
    assert decision.category is RefusalCategory.OUT_OF_SCOPE


def test_malformed_json_fails_safe_to_refuse(make_fake_llm):
    client = make_fake_llm(["not json at all"])
    decision = ScopeGuard(client).check("hi", "it")
    assert decision.allow is False
    assert decision.category is RefusalCategory.MANIPULATION


def test_json_wrapped_in_markdown_is_parsed(make_fake_llm):
    client = make_fake_llm(['```json\n{"allow": true, "category": null, "reason": "ok"}\n```'])
    assert ScopeGuard(client).check("aspirazioni lavorative", "it").allow is True


def test_includes_the_question_as_context_when_given(make_fake_llm):
    # A short answer that only makes sense with the question ("arabo" to "which
    # languages?") must be judged with the question in view.
    client = make_fake_llm(['{"allow": true, "category": null, "reason": "ok"}'])
    ScopeGuard(client).check("arabo", "it", question="Che lingue parli?")
    content = client.calls[0][1]["content"]
    assert "Che lingue parli?" in content and "arabo" in content


def test_without_a_question_the_content_is_just_the_message(make_fake_llm):
    client = make_fake_llm(['{"allow": true, "category": null, "reason": "ok"}'])
    ScopeGuard(client).check("ho fatto il cuoco", "it")
    content = client.calls[0][1]["content"]
    assert "assistant question" not in content
    assert "ho fatto il cuoco" in content


def test_too_long_input_refused_without_calling_llm(make_fake_llm):
    client = make_fake_llm([])  # no responses: LLM must NOT be called
    guard = ScopeGuard(client, max_input_chars=10)
    decision = guard.check("x" * 50, "it")
    assert decision.allow is False
    assert decision.category is RefusalCategory.INVALID_INPUT
    assert client.calls == []
