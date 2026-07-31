from bussola.interview.confirm import interpret_confirmation, summarize
from bussola.interview.sections import SECTIONS
from bussola.interview.sections import SkillsExtraction


def test_summarize_returns_text(make_fake_json_llm):
    client = make_fake_json_llm(text_responses=["Hai detto che sai cucinare."])
    text = summarize(client, SECTIONS[0], SkillsExtraction(), "it")
    assert "cucinare" in text


def test_summarize_prompt_names_the_target_language(make_fake_json_llm):
    # The summary used to come back in English because the prompt only passed a
    # bare code ('it'). It must name the language explicitly (Italian / Arabic).
    for code, name in [("it", "Italian"), ("ar", "Arabic")]:
        client = make_fake_json_llm(text_responses=["ok"])
        summarize(client, SECTIONS[0], SkillsExtraction(), code)
        system = client.calls[0]["messages"][0]["content"]
        assert name in system


def test_interpret_confirmation_true(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[{"confirmed": True}])
    assert interpret_confirmation(client, "sì esatto", "it") is True


def test_interpret_confirmation_false_and_failsafe(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[{"confirmed": False}])
    assert interpret_confirmation(client, "no, ho detto altro", "it") is False
    client2 = make_fake_json_llm(json_responses=[{"weird": 1}])  # invalid -> fail-safe False
    assert interpret_confirmation(client2, "???", "it") is False
