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
