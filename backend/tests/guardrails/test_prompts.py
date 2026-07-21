"""Anti-injection hardening must cover all three prompts, including the
output classifier, which evaluates the assistant's own (possibly
injection-tainted) reply."""

from __future__ import annotations

from bussola.guardrails.prompts import (
    output_classifier_prompt,
    scope_classifier_prompt,
    system_prompt,
)

_JSON_CONTRACT_FRAGMENTS = (
    '"allow": bool',
    '"category": "out_of_scope"|"manipulation"|null',
    '"reason": string',
)


def test_system_prompt_has_injection_clause():
    prompt = system_prompt("it").lower()
    assert "untrusted" in prompt
    assert "never follow" in prompt


def test_scope_classifier_prompt_has_injection_clause():
    prompt = scope_classifier_prompt().lower()
    assert "untrusted" in prompt
    assert "never follow" in prompt


def test_output_classifier_prompt_has_anti_injection_hardening():
    """Reviewed finding: the output classifier evaluates the ASSISTANT's own
    reply, the exact place a successful injection would surface. It must
    treat that reply as untrusted data and refuse to follow instructions
    embedded in it."""
    prompt = output_classifier_prompt().lower()
    assert "untrusted" in prompt
    assert "never follow" in prompt
    assert "instructions" in prompt


def test_output_classifier_prompt_keeps_json_contract():
    prompt = output_classifier_prompt()
    for fragment in _JSON_CONTRACT_FRAGMENTS:
        assert fragment in prompt


def test_output_classifier_prompt_still_checks_scope_and_leaks():
    prompt = output_classifier_prompt().lower()
    assert "work" in prompt and "training" in prompt
    assert "system instructions" in prompt
    assert "personal data" in prompt
