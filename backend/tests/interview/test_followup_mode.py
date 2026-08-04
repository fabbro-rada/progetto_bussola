"""Follow-up interview mode: starts on an EXISTING profile, walks a reduced
section order (experiences, skills, aspirations), and merges with
append/upgrade semantics — prior data must never be lost or downgraded
(nucleo §5). Mirrors the fakes used by test_interview.py, plus `get` on the
fake ProfileStore double."""

from __future__ import annotations

from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview
from bussola.profile.enums import DigitalLiteracy, EvidenceGrade, LanguageLevel, SkillKind
from bussola.profile.models import (
    Aspiration,
    DesiredTraining,
    LanguageKnown,
    Skill,
    WorkExperience,
    WorkProfile,
)


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
# The per-section clarity check (interview.py's `_summarize_section`) makes one
# extra `chat_json` call per extraction; these fakes script "no clarification
# needed" so the flow proceeds straight to the summary, as in normal use.
CLARITY_NO = {"needs_clarification": False, "question": ""}


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
        json_responses=[
            NEW_EXPERIENCE,
            CLARITY_NO,
            CONFIRM,
            SKILL_DEMONSTRATED,
            CLARITY_NO,
            CONFIRM,
        ],
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
        json_responses=[EMPTY_EXPERIENCE, CLARITY_NO, CONFIRM, SKILL_STATED, CLARITY_NO, CONFIRM],
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


def test_followup_reject_and_reanswer_never_accumulates_or_leaks_rejected_data(make_fake_json_llm):
    """§5-critical: the person may see the summary and CORRECT it before
    confirming (interview.py re-summarizes the SAME section without advancing,
    so `merge()` runs more than once for that section). The rejected answer's
    contribution must be fully REPLACED by the corrected one — never stacked
    (experiences), and never left behind as a stale skill/language/aspiration/
    digital_literacy from the rejected attempt — while the prior (pre-follow-up)
    baseline is still preserved and evidence upgrades still never downgrade."""
    existing = WorkProfile(
        pseudonym_id="P-x",
        experiences=[WorkExperience(role="magazziniere", sector="logistica", duration_months=12)],
        skills=[
            Skill(name="giardinaggio", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.STATED),
            Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED),
        ],
        languages=[LanguageKnown(language="italiano", level=LanguageLevel.NATIVE)],
        aspiration=Aspiration(fields_of_interest=["ristorazione"]),
        desired_training=[DesiredTraining(topic="sicurezza sul lavoro")],
    )
    repo = FakeRepo({"P-x": existing})

    # experiences: rejected "cameriere 6 mesi" -> corrected "cuoco 8 mesi"
    exp_rejected = {
        "experiences": [{"role": "cameriere", "sector": "ristorazione", "duration_months": 6}]
    }
    exp_final = {"experiences": [{"role": "cuoco", "sector": "ristorazione", "duration_months": 8}]}
    # skills: rejected adds a bogus skill, over-claims "cucina" evidence
    # (certified), a wrong language, and a too-high digital_literacy.
    skills_rejected = {
        "skills": [
            {"name": "barista", "kind": "technical", "evidence": "stated"},
            {"name": "cucina", "kind": "technical", "evidence": "certified"},
        ],
        "languages": [{"language": "spagnolo", "level": "basic"}],
        "digital_literacy": "advanced",
    }
    skills_final = {
        "skills": [{"name": "cucina", "kind": "technical", "evidence": "stated"}],
        "languages": [{"language": "francese", "level": "intermediate"}],
        "digital_literacy": "basic",
    }
    # aspirations: rejected field/course -> corrected field/course.
    asp_rejected = {
        "fields_of_interest": ["edilizia"],
        "desired_training": [{"topic": "corso saldatura"}],
    }
    asp_final = {
        "fields_of_interest": ["catering"],
        "desired_training": [{"topic": "corso HACCP"}],
    }

    json_responses = [
        exp_rejected,
        CLARITY_NO,
        {"confirmed": False},
        exp_final,
        CLARITY_NO,
        {"confirmed": True},
        skills_rejected,
        CLARITY_NO,
        {"confirmed": False},
        skills_final,
        CLARITY_NO,
        {"confirmed": True},
        asp_rejected,
        CLARITY_NO,
        {"confirmed": False},
        asp_final,
        CLARITY_NO,
        {"confirmed": True},
        {"has_incongruence": False, "clarification": ""},
    ]
    text_responses = [ALLOW, "Riepilogo. Giusto?"] * 6
    client = make_fake_json_llm(json_responses=json_responses, text_responses=text_responses)
    itw = Interview(client, ScopeGuard(client), repo, language="it")

    itw.start_followup("P-x")

    # A "not confirmed" reply is now a CORRECTION to the same section (§5): it
    # re-summarizes (stays on the section), it does NOT re-ask. So each section
    # is: answer (rejected data) -> correction (final data) -> confirm. The
    # follow-up merge recomputes from the baseline, so the rejected attempt's
    # data must never survive the correction.

    # experiences: answer (rejected) -> correction (final) -> confirm
    assert itw.submit("ho fatto il cameriere per 6 mesi").kind == "summary"
    assert itw.submit("scusa, in realtà ho fatto il cuoco per 8 mesi").kind == "summary"
    assert itw.submit("sì, corretto").kind == "question"

    # skills: answer (rejected) -> correction (final) -> confirm
    assert itw.submit("faccio il barista e parlo spagnolo").kind == "summary"
    assert itw.submit("scusa, correggo: so cucinare e parlo francese").kind == "summary"
    assert itw.submit("sì").kind == "question"

    # aspirations: answer (rejected) -> correction (final) -> confirm (last section)
    assert itw.submit("mi piacerebbe l'edilizia, corso di saldatura").kind == "summary"
    assert itw.submit("scusa, mi interessa il catering, corso HACCP").kind == "summary"
    final = itw.submit("sì, confermo")
    # The interview now ends at the RECAP step, not "completed" directly --
    # completing requires confirming the recap (Task 4). The merge assertions
    # below are unaffected: each section was already saved on confirmation.
    assert final.kind == "recap"

    saved = repo.get("P-x")
    assert saved is not None

    # experiences: baseline + ONLY the corrected answer, no accumulation of
    # the rejected "cameriere" experience.
    assert len(saved.experiences) == 2
    assert {e.role for e in saved.experiences} == {"magazziniere", "cuoco"}

    # skills: no stale "barista" from the rejected answer; "cucina"'s
    # evidence reflects the TRUE baseline (demonstrated) — neither
    # downgraded by the corrected (weaker, "stated") answer nor left at the
    # rejected (higher, bogus) "certified" grade.
    skill_names = {s.name for s in saved.skills}
    assert skill_names == {"giardinaggio", "cucina"}
    assert _evidence_of(saved, "cucina") == EvidenceGrade.DEMONSTRATED

    # languages: baseline preserved, rejected "spagnolo" absent, corrected
    # "francese" present.
    language_names = {lang.language for lang in saved.languages}
    assert language_names == {"italiano", "francese"}

    # digital_literacy: the corrected value, not the rejected one.
    assert saved.digital_literacy == DigitalLiteracy.BASIC

    # aspirations: baseline preserved, rejected field/course absent,
    # corrected field/course present.
    assert saved.aspiration is not None
    assert saved.aspiration.fields_of_interest == ["ristorazione", "catering"]
    training_topics = {t.topic for t in saved.desired_training}
    assert training_topics == {"sicurezza sul lavoro", "corso HACCP"}


def test_start_followup_unknown_pseudonym_is_unavailable(make_fake_json_llm):
    client = make_fake_json_llm()
    repo = FakeRepo()  # empty: no profile under "P-none"
    itw = Interview(client, ScopeGuard(client), repo, language="it")
    step = itw.start_followup("P-none")
    assert step.kind == "unavailable"


class AuditRecorder:
    """Records every audit call verbatim (as kwargs), so tests can assert
    exactly which actions fired and with what `target_pseudonym`."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def __call__(self, **kwargs: object) -> None:
        self.events.append(kwargs)


EMPTY_ASPIRATION = {"fields_of_interest": [], "desired_training": []}


def test_followup_completion_emits_followup_completed_audit_once(make_fake_json_llm):
    """§7.3 accountability: an auditor must be able to tell a follow-up ran to
    completion apart from "confirmed some sections and walked away". Drives all
    three follow-up sections (empty answers, just to reach the recap), then
    confirms the recap too (Task 4's confirm path) and asserts the
    `followup_completed` audit fires EXACTLY ONCE, at `_complete()`."""
    repo = FakeRepo({"P-x": _existing_profile()})
    json_responses = [
        EMPTY_EXPERIENCE,
        CLARITY_NO,
        CONFIRM,
        SKILL_STATED,
        CLARITY_NO,
        CONFIRM,
        EMPTY_ASPIRATION,
        CLARITY_NO,
        CONFIRM,
        {"has_incongruence": False, "clarification": ""},
        {"confirmed": True},  # recap confirm
    ]
    text_responses = [ALLOW, "Riepilogo. Giusto?"] * 3
    client = make_fake_json_llm(json_responses=json_responses, text_responses=text_responses)
    audit = AuditRecorder()
    itw = Interview(client, ScopeGuard(client), repo, language="it", audit=audit)

    itw.start_followup("P-x")
    final = None
    for _ in range(3):
        itw.submit("una risposta")
        final = itw.submit("sì")
    assert final is not None and final.kind == "recap"

    final = itw.submit("sì, confermo il riepilogo")
    assert final.kind == "completed"

    completed = [e for e in audit.events if e["action"] == "followup_completed"]
    assert len(completed) == 1  # fires exactly once, at recap confirmation


def test_first_interview_completion_does_not_emit_followup_completed_audit(make_fake_json_llm):
    """S4's first-interview flow must stay unaffected: it never emitted a
    completion audit before this task and still doesn't -- only a follow-up
    session's completion gets `followup_completed`. `interview_section_confirmed`
    (pre-existing, per confirmed section) is unaffected and still fires."""
    repo = FakeRepo()
    json_responses: list[dict] = []
    text_responses: list[str] = []
    empty_first_interview_extractions = [
        {"skills": [], "languages": [], "digital_literacy": None},
        {"experiences": []},
        {"fields_of_interest": [], "desired_training": []},
        {"availability": None, "constraints": []},
        {"operational_notes": []},
    ]
    for extraction in empty_first_interview_extractions:
        text_responses.extend([ALLOW, "Riepilogo. Giusto?"])
        json_responses.extend([extraction, CLARITY_NO, CONFIRM])
    json_responses.append({"has_incongruence": False, "clarification": ""})
    client = make_fake_json_llm(json_responses=json_responses, text_responses=text_responses)
    audit = AuditRecorder()
    itw = Interview(client, ScopeGuard(client), repo, language="it", audit=audit)

    itw.start()
    final = None
    for _ in range(5):
        itw.submit("una risposta")
        final = itw.submit("sì")
    # The interview now ends at the RECAP step, not "completed" directly
    # (Task 4 completes after the recap is confirmed).
    assert final is not None and final.kind == "recap"

    assert not any(e["action"] == "followup_completed" for e in audit.events)
    assert len([e for e in audit.events if e["action"] == "interview_section_confirmed"]) == 5


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
            CLARITY_NO,
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


def test_followup_recap_correction_routed_to_unsupported_section_fails_closed(make_fake_json_llm):
    """§3 fail-closed: apply_recap_correction can route a recap correction to
    ANY of the 5 sections, but FollowupInterviewSession.merge() only
    understands experiences/skills/aspirations -- constraints/preferences are
    first-interview-only and raise TypeError for a follow-up session. Routing
    a follow-up recap correction to "constraints" must NOT crash to
    `unavailable`: it must keep the recap unchanged (nothing new persisted)
    and ask the person to rephrase, exactly like the unroutable case."""
    repo = FakeRepo({"P-x": _existing_profile()})
    json_responses = [
        EMPTY_EXPERIENCE,
        CLARITY_NO,
        CONFIRM,
        SKILL_STATED,
        CLARITY_NO,
        CONFIRM,
        EMPTY_ASPIRATION,
        CLARITY_NO,
        CONFIRM,
        {"has_incongruence": False, "clarification": ""},
        {"confirmed": False},  # recap: not a confirmation -> correction
        {"section": "constraints"},  # routed to a section unsupported in follow-up mode
        {"availability": "full_time", "constraints": []},  # re-extract (never merged)
    ]
    text_responses = [ALLOW, "Riepilogo. Giusto?"] * 3
    client = make_fake_json_llm(
        json_responses=json_responses, text_responses=[*text_responses, ALLOW]
    )
    itw = Interview(client, ScopeGuard(client), repo, language="it")

    itw.start_followup("P-x")
    final = None
    for _ in range(3):
        itw.submit("una risposta")
        final = itw.submit("sì")
    assert final is not None and final.kind == "recap"

    saves_before = len(repo.saved)
    step = itw.submit("niente più turni di notte")
    assert step.kind == "recap"
    assert step.text != final.text  # the static retry message, not the recap intro again
    assert len(repo.saved) == saves_before  # fail-closed: nothing new persisted
    assert step.recap is final.recap  # session.profile untouched by the failed merge
