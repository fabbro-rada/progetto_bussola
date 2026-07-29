"""Aggregate/anonymous report engine (§7.2/§7.3, Fase 2·B).

Anonymity tests come first (§9): k=5 small-cell suppression is the whole
point of this module, so it is proven before anything else — including
that a person with a one-of-a-kind attribute (e.g. a rare language) can
never be singled out via a distribution count of 1..4.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import psycopg
import pytest
from psycopg.types.json import Jsonb
from pydantic import ValidationError

pytestmark = pytest.mark.usefixtures("db")

_UTC = dt.timezone.utc


def _insert_profile(
    conn: psycopg.Connection,
    pseudonym_id: str,
    body: dict[str, Any],
    *,
    created_at: dt.datetime | None = None,
) -> None:
    """Insert a minimal `profiles.work_profile` row directly (bypassing the
    repository) so tests can control `created_at` for weekly-trend fixtures
    and freely shape the JSONB for distribution fixtures."""
    payload: dict[str, Any] = {"pseudonym_id": pseudonym_id, **body}
    with conn.cursor() as cur:
        if created_at is not None:
            cur.execute(
                "INSERT INTO profiles.work_profile (pseudonym_id, profile, created_at) "
                "VALUES (%s, %s, %s)",
                (pseudonym_id, Jsonb(payload), created_at),
            )
        else:
            cur.execute(
                "INSERT INTO profiles.work_profile (pseudonym_id, profile) VALUES (%s, %s)",
                (pseudonym_id, Jsonb(payload)),
            )
    conn.commit()


def _seed_profiles(conn: psycopg.Connection, *, langs: list[str]) -> None:
    """Insert one minimal profile per language in `langs` (brief Step 1)."""
    for i, lang in enumerate(langs):
        _insert_profile(
            conn, f"P-lang-{i}", {"languages": [{"language": lang, "level": "fluent"}]}
        )


def _complete_body(
    *,
    language: str = "it",
    skill_kind: str = "technical",
    skill_evidence: str = "stated",
    availability: str | None = "full_time",
    constraints: list[str] | None = None,
) -> dict[str, Any]:
    """A profile body with all 5 sections populated (completeness == 1.0)."""
    return {
        "languages": [{"language": language, "level": "fluent"}],
        "skills": [{"name": "Cucina", "kind": skill_kind, "evidence": skill_evidence}],
        "experiences": [
            {"role": "Aiuto cuoco", "sector": "Ristorazione", "duration_months": 12}
        ],
        "aspiration": {
            "fields_of_interest": ["Ristorazione"],
            "availability": availability,
            "constraints": constraints or [],
        },
        "desired_training": [{"topic": "HACCP"}],
    }


def _insert_match_run(
    conn: psycopg.Connection,
    *,
    evaluated_count: int,
    compatible_count: int,
    gaps: dict[str, int],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO matching.match_run "
            "(job_request_id, evaluated_count, compatible_count, gaps) VALUES (%s, %s, %s, %s)",
            (1, evaluated_count, compatible_count, Jsonb(gaps)),
        )
    conn.commit()


def _insert_job_request(conn: psycopg.Connection, *, created_at: dt.datetime) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO matching.job_request (title, sector, created_by, created_at) "
            "VALUES (%s, %s, %s, %s)",
            ("Aiuto cuoco", "Ristorazione", "op1", created_at),
        )
    conn.commit()


# --- Step 1: anonymity tests, written FIRST ---------------------------------


def test_suppress_hides_small_cells() -> None:
    from bussola.report.service import suppress

    assert suppress(0) == 0
    assert suppress(-3) == 0
    assert suppress(1) == "<5" and suppress(4) == "<5"
    assert suppress(5) == 5 and suppress(42) == 42


def test_report_suppresses_rare_languages(app_conn: psycopg.Connection) -> None:
    _seed_profiles(app_conn, langs=["it"] * 5 + ["ti"])
    from bussola.report.service import compute_report

    rep = compute_report(app_conn, k=5)
    # `languages` is free-text-keyed: a count < k must not appear at all —
    # not even as the "<5" sentinel, because the KEY itself (a rare
    # language) is what would single someone out (§2/§5).
    assert all(isinstance(v, int) and v >= 5 for v in rep.languages.values())
    assert not any(kk.startswith("ti") for kk in rep.languages)  # Tigrinya key absent
    # a language with >= k speakers IS present, with its exact number
    it = next((v for kk, v in rep.languages.items() if kk.startswith("it")), None)
    assert it == 5
    # and no pseudonym / free text leaking anywhere in the dump
    dump = rep.model_dump_json()
    assert "pseudonym" not in dump
    assert "P-lang" not in dump


def test_unique_language_not_identifiable(app_conn: psycopg.Connection) -> None:
    """Adversarial: every profile has a DIFFERENT language (n=1 each). Not one
    of them may be identifiable via a raw count in the output — and since
    every language here is unique, the correct anonymity-preserving result
    is an EMPTY `languages` map: no rare key may be emitted at all."""
    _seed_profiles(app_conn, langs=["fr", "es", "ar", "en", "de"])
    from bussola.report.service import compute_report

    rep = compute_report(app_conn, k=5)
    assert rep.languages == {}  # every language is rare (n=1) -> all keys dropped
    for lang in ("fr", "es", "ar", "en", "de"):
        assert not any(kk.startswith(lang) for kk in rep.languages)


def test_zero_profiles_gives_empty_report(app_conn: psycopg.Connection) -> None:
    from bussola.report.service import compute_report

    rep = compute_report(app_conn, k=5)
    assert rep.coverage.total_profiles == 0
    assert rep.coverage.completed_profiles == 0
    assert rep.coverage.average_completeness == 0.0
    assert rep.total_job_requests == 0
    assert rep.matching.runs == 0
    assert rep.matching.evaluated == 0
    assert rep.matching.compatible == 0
    assert rep.matching.compatible_rate == 0.0


# --- Step 5: correctness tests on a known fixture ---------------------------


def test_coverage_counts_average_and_histogram(app_conn: psycopg.Connection) -> None:
    from bussola.report.service import compute_report

    for i in range(6):  # 6 complete profiles -> "100%" bucket, >= k -> exact
        _insert_profile(app_conn, f"P-complete-{i}", _complete_body())
    for i in range(2):  # 2 partial profiles (skills only) -> "20%" bucket, < k
        _insert_profile(app_conn, f"P-partial-{i}", {"skills": [{"name": "X", "kind": "soft", "evidence": "stated"}]})

    rep = compute_report(app_conn, k=5)
    assert rep.coverage.total_profiles == 8
    assert rep.coverage.completed_profiles == 6
    assert rep.coverage.average_completeness == pytest.approx((6 * 1.0 + 2 * 0.2) / 8)
    # global aggregates are never suppressed, even though 6 or 2 might be < k
    assert isinstance(rep.coverage.total_profiles, int)
    assert isinstance(rep.coverage.completed_profiles, int)
    # per-bucket counts ARE suppressed
    assert rep.coverage.completeness_histogram["100%"] == 6  # >= k -> exact
    assert rep.coverage.completeness_histogram["20%"] == "<5"  # < k -> suppressed
    assert rep.coverage.completeness_histogram["0%"] == 0


def test_enumerated_distributions_suppress_small_and_keep_large(
    app_conn: psycopg.Connection,
) -> None:
    from bussola.report.service import compute_report

    for i in range(6):
        _insert_profile(
            app_conn,
            f"P-tech-{i}",
            _complete_body(skill_kind="technical", availability="full_time"),
        )
    _insert_profile(
        app_conn, "P-soft-1", _complete_body(skill_kind="soft", availability="part_time")
    )

    rep = compute_report(app_conn, k=5)
    assert rep.skill_kinds["technical"] == 6  # >= k -> exact number
    assert rep.skill_kinds["soft"] == "<5"  # 1 profile -> suppressed
    assert rep.availability["full_time"] == 6
    assert rep.availability["part_time"] == "<5"


def test_matching_aggregate_rate_and_top_gaps(app_conn: psycopg.Connection) -> None:
    from bussola.report.service import compute_report

    _insert_match_run(
        app_conn, evaluated_count=10, compatible_count=6, gaps={"HACCP": 3, "muletto": 1}
    )
    _insert_match_run(app_conn, evaluated_count=5, compatible_count=1, gaps={"HACCP": 3})

    rep = compute_report(app_conn, k=5)
    # runs/evaluated/compatible/rate are global aggregates -> never suppressed
    assert rep.matching.runs == 2
    assert rep.matching.evaluated == 15
    assert rep.matching.compatible == 7
    assert rep.matching.compatible_rate == pytest.approx(7 / 15)
    # top_gaps is free-text-keyed (recommended_training): a count < k must
    # not appear at all — the KEY itself (a rare training gap) would single
    # someone out, so it is DROPPED, never shown as "<5" (§2/§5).
    assert rep.matching.top_gaps["HACCP"] == 6  # 3 + 3 >= k -> exact, present
    assert "muletto" not in rep.matching.top_gaps  # 1 -> key dropped entirely


def test_weekly_trends(app_conn: psycopg.Connection) -> None:
    from bussola.report.service import compute_report

    week_a = dt.datetime(2026, 7, 6, 12, 0, tzinfo=_UTC)  # Monday
    week_b = dt.datetime(2026, 7, 20, 12, 0, tzinfo=_UTC)  # a different Monday

    for i in range(6):
        _insert_profile(app_conn, f"P-wa-{i}", _complete_body(), created_at=week_a)
        _insert_job_request(app_conn, created_at=week_a)
    for i in range(2):
        _insert_profile(app_conn, f"P-wb-{i}", _complete_body(), created_at=week_b)
        _insert_job_request(app_conn, created_at=week_b)

    rep = compute_report(app_conn, k=5)
    assert rep.trends.profiles_by_week["2026-07-06"] == 6
    assert rep.trends.profiles_by_week["2026-07-20"] == "<5"
    assert rep.trends.job_requests_by_week["2026-07-06"] == 6
    assert rep.trends.job_requests_by_week["2026-07-20"] == "<5"


def test_report_forbids_extra_fields_and_has_no_free_text_leak(
    app_conn: psycopg.Connection,
) -> None:
    from bussola.report.models import Report
    from bussola.report.service import compute_report

    _insert_profile(app_conn, "P-1", _complete_body())
    rep = compute_report(app_conn, k=5)
    with pytest.raises(ValidationError):
        Report(**{**rep.model_dump(), "unexpected": "nope"})
    dump = rep.model_dump_json()
    assert "pseudonym" not in dump
    assert "Aiuto cuoco" not in dump  # free-text role never leaks into the report
    assert "Cucina" not in dump  # free-text skill name never leaks into the report
