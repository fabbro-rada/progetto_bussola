from bussola.interview.sections import SECTIONS, base_question


def test_five_sections_in_fixed_order():
    keys = [s.key for s in SECTIONS]
    assert keys == ["skills", "experiences", "aspirations", "constraints", "preferences"]


def test_every_section_has_all_five_languages():
    for section in SECTIONS:
        for lang in ("it", "en", "fr", "es", "ar"):
            assert section.base_question[lang].strip()


def test_base_question_falls_back_to_english():
    assert base_question(SECTIONS[0], "de") == SECTIONS[0].base_question["en"]


def test_base_question_returns_requested_language():
    assert base_question(SECTIONS[0], "it") == SECTIONS[0].base_question["it"]


def test_skills_extraction_keeps_the_persons_own_words():
    # The extraction must not rewrite plain job words into technical terms
    # (e.g. 'falegname' -> 'carpenteria'), so the person recognises the summary.
    skills = next(s for s in SECTIONS if s.key == "skills")
    prompt = skills.extraction_prompt.lower()
    assert "own everyday words" in prompt
    assert "falegname" in prompt and "carpenteria" in prompt


def test_extraction_models_forbid_extra_fields():
    import pytest
    from pydantic import ValidationError

    for section in SECTIONS:
        with pytest.raises(ValidationError):
            section.extraction_model(unexpected="x")
