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
    assert "<PHONE_NUMBER>" in out


def test_redacts_person_name_english(redactor):
    # Italian has no NER model (it_core_news_lg is CC BY-NC-SA, not
    # permissive, and has been removed — see pii.py docstring). English
    # NER (en_core_web_lg, MIT) is exercised here instead.
    out = redactor.redact("I worked with Marco Rossi in the kitchen", language="en")
    assert "Marco Rossi" not in out
    assert "<PERSON>" in out


def test_text_without_pii_is_unchanged(redactor):
    text = "esperienza in saldatura e carpenteria metallica"
    assert redactor.redact(text, language="it") == text


def test_empty_text_is_returned_as_is(redactor):
    assert redactor.redact("", language="it") == ""


@pytest.mark.parametrize("language", ["fr", "es", "ar"])
def test_redacts_email_in_all_supported_languages(redactor, language):
    # CLAUDE.md §8: all five supported languages must survive redaction —
    # pattern recognizers (email, phone, ...) are language-agnostic and only
    # need the language registered with a spaCy pipeline (blank is enough).
    # Before this fix, `redact(text, "fr"|"es"|"ar")` raised ValueError.
    out = redactor.redact("scrivimi a mario.rossi@example.com", language=language)
    assert "mario.rossi@example.com" not in out
    assert "<EMAIL_ADDRESS>" in out
