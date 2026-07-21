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


def test_unknown_language_falls_back_to_english():
    assert refusal_message(RefusalCategory.OUT_OF_SCOPE, "de").strip()
