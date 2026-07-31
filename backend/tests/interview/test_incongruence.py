from bussola.interview.incongruence import find_incongruence
from bussola.profile.models import WorkProfile


def test_incongruence_found(make_fake_json_llm):
    client = make_fake_json_llm(
        json_responses=[
            {
                "has_incongruence": True,
                "clarification": "Hai detto 10 anni come cuoco ma hai 20 anni: puoi chiarire?",
            }
        ]
    )
    q = find_incongruence(client, WorkProfile(pseudonym_id="P-1"), "it")
    assert q and "chiarire" in q


def test_no_incongruence_and_failsafe(make_fake_json_llm):
    client = make_fake_json_llm(json_responses=[{"has_incongruence": False, "clarification": ""}])
    assert find_incongruence(client, WorkProfile(pseudonym_id="P-1"), "it") is None
    client2 = make_fake_json_llm(json_responses=[{"broken": 1}])  # invalid -> fail-safe None
    assert find_incongruence(client2, WorkProfile(pseudonym_id="P-1"), "it") is None


def test_clarification_prompt_names_the_target_language(make_fake_json_llm):
    # The clarification question must be asked in the person's language: the
    # prompt names it explicitly (French / Arabic), not just the bare code.
    for code, name in [("fr", "French"), ("ar", "Arabic")]:
        client = make_fake_json_llm(
            json_responses=[{"has_incongruence": False, "clarification": ""}]
        )
        find_incongruence(client, WorkProfile(pseudonym_id="P-1"), code)
        system = client.calls[0]["messages"][0]["content"]
        assert name in system
