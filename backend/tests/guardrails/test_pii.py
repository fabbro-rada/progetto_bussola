import pytest

from bussola.guardrails.pii import PiiRedactor


@pytest.fixture(scope="session")
def redactor() -> PiiRedactor:
    # Expensive to build (loads NLP models); build once for the session.
    return PiiRedactor()


def test_redacts_email(redactor):
    out = redactor.redact("scrivimi a mario.rossi@example.com per info", language="it")
    assert "mario.rossi@example.com" not in out
    assert "<EMAIL_ADDRESS>" in out


def test_redacts_phone_number(redactor):
    out = redactor.redact("il mio numero e' +39 333 123 4567", language="it")
    assert "333 123 4567" not in out


def test_redacts_person_name_italian(redactor):
    out = redactor.redact("ho lavorato con Marco Rossi in cucina", language="it")
    assert "Marco Rossi" not in out


def test_text_without_pii_is_unchanged(redactor):
    text = "esperienza in saldatura e carpenteria metallica"
    assert redactor.redact(text, language="it") == text


def test_empty_text_is_returned_as_is(redactor):
    assert redactor.redact("", language="it") == ""
