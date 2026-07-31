from bussola.languages import SUPPORTED_LANGUAGES, language_name


def test_supported_languages_is_the_canonical_five():
    assert SUPPORTED_LANGUAGES == ("it", "en", "fr", "es", "ar")


def test_language_name_maps_every_supported_code_to_an_english_name():
    assert language_name("it") == "Italian"
    assert language_name("en") == "English"
    assert language_name("fr") == "French"
    assert language_name("es") == "Spanish"
    assert language_name("ar") == "Arabic"


def test_language_name_falls_back_to_the_code_for_unknown():
    assert language_name("de") == "de"


def test_consumers_share_the_same_constant():
    from bussola.guardrails import refusal
    from bussola.system import service
    assert refusal.SUPPORTED_LANGUAGES is SUPPORTED_LANGUAGES
    assert service.SUPPORTED_LANGUAGES is SUPPORTED_LANGUAGES
