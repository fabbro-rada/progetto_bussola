"""Follow-up interview mode: starts on an EXISTING profile, walks a reduced
section order (experiences, skills, aspirations), and merges with
append/upgrade semantics — prior data must never be lost or downgraded
(nucleo §5). Mirrors the fakes used by test_interview.py, plus `get` on the
fake ProfileStore double."""

from __future__ import annotations

from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview
from bussola.profile.enums import EvidenceGrade, SkillKind
from bussola.profile.models import Skill, WorkExperience, WorkProfile


class FakeRepo:
    """Fake ProfileStore: supports both first-interview (`create_new`) and
    follow-up (`get`) construction paths."""

    def __init__(self, profiles: dict[str, WorkProfile] | None = None) -> None:
        self.saved: list[WorkProfile] = []
        self._profiles: dict[str, WorkProfile] = dict(profiles or {})
        self._n = 0
        self.created = 0

    def create_new(self) -> str:
        self._n += 1
        self.created += 1
        pseudonym = f"P-{self._n}"
        self._profiles[pseudonym] = WorkProfile(pseudonym_id=pseudonym)
        return pseudonym

    def save(self, profile: WorkProfile) -> WorkProfile:
        self.saved.append(profile)
        self._profiles[profile.pseudonym_id] = profile
        return profile

    def get(self, pseudonym_id: str) -> WorkProfile | None:
        return self._profiles.get(pseudonym_id)


ALLOW = '{"allow": true, "category": null, "reason": "ok"}'

# Section extraction payloads (reduced follow-up order: experiences, skills,
# aspirations).
NEW_EXPERIENCE = {
    "experiences": [{"role": "cameriere", "sector": "ristorazione", "duration_months": 6}]
}
EMPTY_EXPERIENCE: dict = {"experiences": []}
SKILL_DEMONSTRATED = {
    "skills": [{"name": "cucina", "kind": "technical", "evidence": "demonstrated"}],
    "languages": [],
    "digital_literacy": None,
}
SKILL_STATED = {
    "skills": [{"name": "cucina", "kind": "technical", "evidence": "stated"}],
    "languages": [],
    "digital_literacy": None,
}
CONFIRM = {"confirmed": True}


def _existing_profile(pseudonym: str = "P-x") -> WorkProfile:
    return WorkProfile(
        pseudonym_id=pseudonym,
        experiences=[WorkExperience(role="magazziniere", sector="logistica", duration_months=12)],
        skills=[
            Skill(name="giardinaggio", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED),
        ],
    )


def _evidence_of(profile: WorkProfile, name: str) -> EvidenceGrade:
    for skill in profile.skills:
        if skill.name.strip().lower() == name.strip().lower():
            return skill.evidence
    raise AssertionError(f"skill {name!r} not found in profile")


def test_followup_appends_experience_and_upgrades_evidence(make_fake_json_llm):
    existing = _existing_profile()
    existing.skills.append(
        Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED)
    )
    repo = FakeRepo({"P-x": existing})
    client = make_fake_json_llm(
        json_responses=[NEW_EXPERIENCE, CONFIRM, SKILL_DEMONSTRATED, CONFIRM],
        text_responses=[
            ALLOW,
            "Riepilogo esperienza. Giusto?",
            ALLOW,
            "Riepilogo competenze. Giusto?",
        ],
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it")

    step = itw.start_followup("P-x")
    assert step.kind == "question"

    s1 = itw.submit("ho fatto il cameriere per 6 mesi")
    assert s1.kind == "summary"
    s2 = itw.submit("sì")
    assert s2.kind == "question"  # advanced from experiences to skills

    s3 = itw.submit("so cucinare bene, l'ho dimostrato")
    assert s3.kind == "summary"
    itw.submit("sì")

    saved = repo.get("P-x")
    assert saved is not None
    assert len(saved.experiences) == 2  # old + new, nothing lost
    roles = {e.role for e in saved.experiences}
    assert roles == {"magazziniere", "cameriere"}
    assert _evidence_of(saved, "cucina") == EvidenceGrade.DEMONSTRATED  # upgraded
    assert (
        len([s for s in saved.skills if s.name.strip().lower() == "cucina"]) == 1
    )  # not duplicated


def test_followup_never_downgrades_or_drops(make_fake_json_llm):
    existing = _existing_profile()
    existing.skills.append(
        Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
    )
    repo = FakeRepo({"P-x": existing})
    client = make_fake_json_llm(
        json_responses=[EMPTY_EXPERIENCE, CONFIRM, SKILL_STATED, CONFIRM],
        text_responses=[ALLOW, "Riepilogo. Giusto?", ALLOW, "Riepilogo. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it")

    itw.start_followup("P-x")
    itw.submit("nessuna nuova esperienza")
    itw.submit("sì")
    itw.submit("so cucinare")
    itw.submit("sì")

    saved = repo.get("P-x")
    assert saved is not None
    # Prior experience absent from the follow-up answer is preserved.
    assert len(saved.experiences) == 1
    assert saved.experiences[0].role == "magazziniere"
    # "cucina" was already demonstrated; a re-stated (weaker) mention must
    # NOT downgrade it.
    assert _evidence_of(saved, "cucina") == EvidenceGrade.DEMONSTRATED
    # A prior skill absent from the follow-up extraction is preserved too.
    assert any(s.name == "giardinaggio" for s in saved.skills)


def test_start_followup_unknown_pseudonym_is_unavailable(make_fake_json_llm):
    client = make_fake_json_llm()
    repo = FakeRepo()  # empty: no profile under "P-none"
    itw = Interview(client, ScopeGuard(client), repo, language="it")
    step = itw.start_followup("P-none")
    assert step.kind == "unavailable"


def test_first_interview_mode_unchanged(make_fake_json_llm):
    # Smoke test: start() still creates a fresh pseudonym and walks the full
    # (5-section) SECTIONS order with overwrite merge — follow-up mode must
    # not have touched this path at all.
    repo = FakeRepo()
    client = make_fake_json_llm(
        json_responses=[
            {
                "skills": [{"name": "cooking", "kind": "technical", "evidence": "stated"}],
                "languages": [],
                "digital_literacy": None,
            },
            CONFIRM,
        ],
        text_responses=[ALLOW, "Riepilogo. Giusto?"],
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it")
    step = itw.start()
    assert step.kind == "question"
    assert repo.created == 1  # fresh pseudonym via create_new(), not get()

    s1 = itw.submit("so cucinare")
    assert s1.kind == "summary"
    s2 = itw.submit("sì")
    assert s2.kind == "question"  # advanced within the full 5-section order

    saved = repo.get(repo.saved[0].pseudonym_id)
    assert saved is not None
    assert saved.skills[0].name == "cooking"
