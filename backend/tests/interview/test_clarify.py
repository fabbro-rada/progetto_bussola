from bussola.interview.clarify import apply_recap_correction, find_section_clarification
from bussola.interview.sections import SECTIONS, ExperiencesExtraction
from bussola.interview.extraction import extract_section  # noqa: F401 (context)
from bussola.profile.models import WorkProfile


class _Json:
    def __init__(self, responses):
        self._r = list(responses)
        self.calls = []

    def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None):
        self.calls.append(messages)
        return self._r.pop(0)

    def chat(self, *a, **k):
        raise AssertionError("no text call")


EXPERIENCES = SECTIONS[1]  # key == "experiences"


def test_returns_question_when_ambiguous():
    client = _Json([{"needs_clarification": True, "question": "Che lavoro facevi di preciso?"}])
    q = find_section_clarification(
        client, EXPERIENCES, EXPERIENCES.extraction_model(), WorkProfile(pseudonym_id="P-1"), "it"
    )
    assert q == "Che lavoro facevi di preciso?"


def test_returns_none_when_clear():
    client = _Json([{"needs_clarification": False, "question": ""}])
    assert (
        find_section_clarification(
            client,
            EXPERIENCES,
            EXPERIENCES.extraction_model(),
            WorkProfile(pseudonym_id="P-1"),
            "it",
        )
        is None
    )


def test_fail_open_on_llm_error():
    class Boom:
        def chat_json(self, *a, **k):
            raise RuntimeError("down")

    assert (
        find_section_clarification(
            Boom(),
            EXPERIENCES,
            EXPERIENCES.extraction_model(),
            WorkProfile(pseudonym_id="P-1"),
            "it",
        )
        is None
    )


def test_apply_recap_correction_routes_and_reextracts():
    exp = {"experiences": [{"role": "consulente", "sector": "IT", "duration_months": 24}]}
    client = _Json([{"section": "experiences"}, exp])  # classify -> experiences ; re-extract
    out = apply_recap_correction(
        client, "il consulente era 2 anni non 2 mesi", WorkProfile(pseudonym_id="P-1"), "it"
    )
    assert isinstance(out, ExperiencesExtraction)
    assert out.experiences[0].role == "consulente" and out.experiences[0].duration_months == 24


def test_apply_recap_correction_none_when_unroutable():
    client = _Json([{"section": "none"}])
    assert apply_recap_correction(client, "boh", WorkProfile(pseudonym_id="P-1"), "it") is None
