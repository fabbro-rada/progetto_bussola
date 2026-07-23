"""End-to-end interview against the real local LLM (Qwen2.5) + Postgres.

Skips unless a llama-server answers on /health (`requires_llm`); the DB
fixtures (shared `tests/conftest.py`) skip on their own if Postgres is down.
Synthetic personas only (§9). Asserts a full synthetic interview persists a
work-only profile — do NOT weaken the assertions to make a flaky model pass;
investigate the section/extraction prompts instead.
"""

from __future__ import annotations

import httpx
import pytest

from bussola.data.profiles import ProfileRepository
from bussola.guardrails.pii import PiiRedactor
from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview
from bussola.llm.client import HttpxLlmClient
from bussola.profile.models import WorkProfile


def _llm_up() -> bool:
    try:
        httpx.get("http://127.0.0.1:8080/health", timeout=3)
        return True
    except Exception:
        return False


requires_llm = pytest.mark.skipif(not _llm_up(), reason="llama-server non attivo")
pytestmark = requires_llm


def _drive(itw: Interview, answer: str) -> object:
    """Answer a section, then confirm; return the step after confirmation."""
    step = itw.submit(answer)
    assert step.kind in ("summary", "refusal", "clarification")
    return itw.submit("sì, è corretto")


def test_synthetic_interview_produces_work_only_profile(app_conn):
    redactor = PiiRedactor()
    repo = ProfileRepository(app_conn, redactor)
    client = HttpxLlmClient()
    itw = Interview(client, ScopeGuard(client), repo, language="it")

    itw.start()
    _drive(itw, "So cucinare e faccio manutenzione base. Parlo italiano e un po' di inglese.")
    _drive(itw, "Ho fatto il cuoco per due anni in una mensa.")
    _drive(
        itw, "Mi piacerebbe lavorare nella ristorazione. Vorrei un corso di sicurezza alimentare."
    )
    _drive(itw, "Disponibilità a tempo pieno.")
    final = _drive(itw, "Preferisco lavorare in squadra.")

    assert final.kind in ("completed", "clarification")

    # Exactly one profile was persisted; reload it and check it is realistic and
    # correctly ALIGNED per section (a section landing in the wrong slot, or an
    # empty extraction, must fail here — count>=1 alone would hide that).
    with app_conn.cursor() as cur:
        cur.execute("SELECT count(*), min(profile::text) FROM profiles.work_profile")
        count, profile_json = cur.fetchone()
    assert count == 1
    profile = WorkProfile.model_validate_json(profile_json)

    # Section 1 (skills): skills AND both languages captured.
    assert profile.skills, "no skills extracted"
    langs = {lang.language.lower() for lang in profile.languages}
    assert any("ital" in lang for lang in langs), f"Italian missing: {langs}"
    assert any("ingl" in lang or "engl" in lang for lang in langs), f"English missing: {langs}"
    # Section 2 (experiences): the cook experience.
    assert profile.experiences, "no experiences extracted"
    # Section 3 (aspirations): a field of interest AND a desired training.
    assert profile.aspiration is not None and profile.aspiration.fields_of_interest
    assert profile.desired_training, "no desired training extracted"
    # Section 4 (constraints): availability set to a real value (alignment: this
    # must NOT be an availability phrase sitting in fields_of_interest instead).
    assert profile.aspiration.availability is not None, "availability not aligned"
