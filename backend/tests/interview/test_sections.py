from bussola.interview.sections import SECTIONS, base_question


def test_five_sections_in_fixed_order():
    keys = [s.key for s in SECTIONS]
    assert keys == ["competenze", "esperienze", "aspirazioni", "vincoli", "preferenze"]


def test_every_section_has_all_five_languages():
    for section in SECTIONS:
        for lang in ("it", "en", "fr", "es", "ar"):
            assert section.base_question[lang].strip()


def test_base_question_falls_back_to_english():
    assert base_question(SECTIONS[0], "de") == SECTIONS[0].base_question["en"]


def test_extraction_models_forbid_extra_fields():
    import pytest
    from pydantic import ValidationError

    model = SECTIONS[0].extraction_model
    with pytest.raises(ValidationError):
        model(secret="x")
