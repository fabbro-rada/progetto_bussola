from bussola.languages import SUPPORTED_LANGUAGES


def test_supported_languages_is_the_canonical_five():
    assert SUPPORTED_LANGUAGES == ("it", "en", "fr", "es", "ar")


def test_consumers_share_the_same_constant():
    from bussola.guardrails import refusal
    from bussola.system import service
    assert refusal.SUPPORTED_LANGUAGES is SUPPORTED_LANGUAGES
    assert service.SUPPORTED_LANGUAGES is SUPPORTED_LANGUAGES
