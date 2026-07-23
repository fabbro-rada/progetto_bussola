from bussola.interview.extraction import extract_section
from bussola.interview.sections import SECTIONS


def test_extracts_and_validates_section(make_fake_json_llm):
    client = make_fake_json_llm(
        json_responses=[
            {
                "skills": [{"name": "cooking", "kind": "technical", "evidence": "demonstrated"}],
                "languages": [],
                "digital_literacy": None,
            }
        ]
    )
    result = extract_section(client, SECTIONS[0], "so cucinare", "it")
    assert result.skills[0].name == "cooking"


def test_invalid_extraction_is_fail_safe_empty(make_fake_json_llm):
    # extra field not in schema -> validation fails -> empty model (no invented data)
    client = make_fake_json_llm(json_responses=[{"unexpected": "x"}])
    result = extract_section(client, SECTIONS[0], "boh", "it")
    assert result.skills == []
    assert result.languages == []
