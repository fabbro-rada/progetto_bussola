"""End-to-end matching against the real local LLM (Qwen2.5) + Postgres.

Skips unless a llama-server answers on /health (`requires_llm`); the DB fixture
skips on its own if Postgres is down. Synthetic personas only (§9). Asserts the
deterministic hard-constraint gate holds (a night-shift-incompatible candidate
is excluded) and the semantic judgment is GROUNDED (evidence cites the profile)
with a real formative gap. Do NOT weaken the assertions to make a flaky model
pass — investigate the semantic prompt instead.
"""

from __future__ import annotations

import httpx
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.llm.client import HttpxLlmClient
from bussola.matching.models import JobRequestCreate, RequiredLanguage
from bussola.matching.requests import JobRequestRepository
from bussola.matching.service import MatchingService
from bussola.profile.enums import (
    Availability,
    EvidenceGrade,
    LanguageLevel,
    SkillKind,
    WorkConstraint,
)
from bussola.profile.models import Aspiration, LanguageKnown, Skill, WorkProfile

pytestmark = pytest.mark.usefixtures("db")


def _llm_up() -> bool:
    try:
        httpx.get("http://127.0.0.1:8080/health", timeout=3)
        return True
    except Exception:
        return False


requires_llm = pytest.mark.skipif(not _llm_up(), reason="llama-server non attivo")


@requires_llm
def test_synthetic_matching_is_grounded_and_gated(app_conn):
    profiles = ProfileRepository(app_conn, PiiRedactor())
    profiles.save(
        WorkProfile(
            pseudonym_id="P-cook",
            skills=[
                Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
            ],
            languages=[LanguageKnown(language="it", level=LanguageLevel.FLUENT)],
            aspiration=Aspiration(availability=Availability.FULL_TIME),
        )
    )
    profiles.save(
        WorkProfile(
            pseudonym_id="P-night",  # must be excluded by the night-shift gate
            skills=[
                Skill(name="cucina", kind=SkillKind.TECHNICAL, evidence=EvidenceGrade.DEMONSTRATED)
            ],
            aspiration=Aspiration(constraints=[WorkConstraint.NO_NIGHT_SHIFTS]),
        )
    )
    job = JobRequestRepository(app_conn).create(
        JobRequestCreate(
            title="Cuoco",
            sector="ristorazione",
            required_skills=["cucina", "sicurezza alimentare"],
            required_languages=[
                RequiredLanguage(language="it", min_level=LanguageLevel.INTERMEDIATE)
            ],
            required_availability=Availability.FULL_TIME,
            involves_night_shifts=True,
        ),
        created_by="op1",
    )
    app_conn.commit()

    results = MatchingService(app_conn, HttpxLlmClient(), PiiRedactor()).match(job.id, actor="op1")
    ids = [r.pseudonym_id for r in results]
    assert "P-night" not in ids  # deterministic hard-constraint gate held
    cook = next(r for r in results if r.pseudonym_id == "P-cook")
    # "cucina" satisfied and grounded in the profile; "sicurezza alimentare" a gap
    cooking = next(v for v in cook.requirements if "cucina" in v.requirement.lower())
    assert cooking.satisfied is True and cooking.evidence  # evidence cites the profile
    assert any("sicurezza" in g.requirement.lower() for g in cook.gaps)
