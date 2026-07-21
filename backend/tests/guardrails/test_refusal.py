import pytest

from bussola.guardrails.refusal import (
    SUPPORTED_LANGUAGES,
    RefusalCategory,
    refusal_message,
)


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
@pytest.mark.parametrize("category", list(RefusalCategory))
def test_refusal_message_localized_and_nonempty(category, language):
    message = refusal_message(category, language)
    assert isinstance(message, str) and message.strip()


@pytest.mark.parametrize("category", list(RefusalCategory))
def test_unknown_language_falls_back_to_english(category):
    assert refusal_message(category, "de") == refusal_message(category, "en")


@pytest.mark.parametrize("category", list(RefusalCategory))
def test_messages_are_distinct_across_supported_languages(category):
    messages = {refusal_message(category, language) for language in SUPPORTED_LANGUAGES}
    assert len(messages) == len(SUPPORTED_LANGUAGES)
