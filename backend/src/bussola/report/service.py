"""Aggregate/anonymous report engine (§7.2/§7.3, Fase 2·B).

`compute_report` reads `profiles.work_profile`, `matching.job_request`, and
`matching.match_run` and produces ONLY marginal distributions over the
enumerated fields, plus a handful of global (non-identifying) totals. Every
distribution count, histogram bucket, top-gap count, and weekly-trend count
passes through `suppress` — the single k-anonymity choke point in the whole
system. Nothing here ever carries a pseudonym or a per-person value (§2/§5).

Two distributions are keyed by FREE TEXT rather than a fixed, public enum:
`languages` (keys built from the free-text `language` field) and
`matching.top_gaps` (keys = free-text `recommended_training`). For those, a
rare key is itself identifying — showing `{"tigrinya (fluent)": "<5"}` still
discloses that someone (1..4 people) speaks Tigrinya, singling them out by a
rare attribute even though the *count* is masked (§2/§5). So for these two
maps ONLY, a count below k causes the KEY to be dropped entirely (see
`_suppress_and_drop_rare_keys`), not merely masked to `"<5"`. Every other
distribution here (`skill_kinds`, `skill_evidence`, `availability`,
`constraints`, `completeness_histogram`, `trends.*`) is keyed by a fixed,
non-identifying vocabulary (an enum, a completeness bucket, or a week), so
`suppress`'s `"<5"` sentinel is safe there and is left unchanged.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, cast

import psycopg

from bussola.metrics.service import _profile_completeness
from bussola.profile.enums import Availability, EvidenceGrade, SkillKind, WorkConstraint
from bussola.report.models import Coverage, MatchingAgg, Report, Trends
from bussola.report.models import Count

# The 6 fixed completeness buckets (0/20/40/60/80/100%), independent of how
# many profile sections currently make up `_TOTAL_SECTIONS`.
_HISTOGRAM_BUCKETS = (0, 20, 40, 60, 80, 100)


def suppress(n: int, k: int = 5) -> Count:
    """The one and only k-anonymity choke point (§ anonymity).

    n<=0 -> 0 (nothing to hide); 0<n<k -> the sentinel "<k" (a small cell
    that could identify someone); n>=k -> the exact number.
    """
    if n <= 0:
        return 0
    if n < k:
        # The DTO fixes the sentinel type to Literal["<5"] (the caller-facing
        # contract always uses k=5); cast documents that k-parameterization
        # is an internal convenience, not a wider public sentinel type.
        return cast(Count, f"<{k}")
    return n


def _suppress_map(counts: dict[str, int], k: int) -> dict[str, Count]:
    return {key: suppress(value, k) for key, value in counts.items()}


def _suppress_and_drop_rare_keys(counts: dict[str, int], k: int) -> dict[str, Count]:
    """The k-anonymity choke point for FREE-TEXT-keyed distributions
    (`languages`, `matching.top_gaps`) — see the module docstring.

    Unlike `_suppress_map`, a count below k does not surface as the `"<5"`
    sentinel: the entry is dropped entirely, so the key itself (a rare
    language, a rare training gap) never reaches the caller. Every
    surviving value is a bare `int >= k` — the return type is `dict[str,
    Count]` only to match the DTO field type; the `"<5"` sentinel is a
    member of `Count` that this function never actually produces.
    """
    return {key: value for key, value in counts.items() if value >= k}


def _histogram_bucket(score: float) -> str:
    pct = round(score * 5) * 20
    pct = max(0, min(100, pct))
    return f"{pct}%"


def _week_key(ts: dt.datetime) -> str:
    """ISO date (Monday) of the week `ts` falls in — mirrors Postgres
    `date_trunc('week', ts)`, computed in Python once we already have the
    row's timestamp in hand."""
    monday = ts.date() - dt.timedelta(days=ts.weekday())
    return monday.isoformat()


def compute_report(conn: psycopg.Connection, *, k: int = 5) -> Report:
    with conn.cursor() as cur:
        cur.execute("SELECT profile, created_at FROM profiles.work_profile")
        profile_rows: list[tuple[dict[str, Any], dt.datetime]] = cur.fetchall()

        cur.execute("SELECT created_at FROM matching.job_request")
        job_request_created_ats: list[dt.datetime] = [row[0] for row in cur.fetchall()]

        cur.execute(
            "SELECT count(*), COALESCE(sum(evaluated_count), 0), "
            "COALESCE(sum(compatible_count), 0) FROM matching.match_run"
        )
        match_run_row = cur.fetchone()
        runs, evaluated, compatible = match_run_row if match_run_row else (0, 0, 0)

        cur.execute("SELECT gaps FROM matching.match_run")
        gap_maps: list[dict[str, int]] = [row[0] for row in cur.fetchall()]

    profiles = [row[0] for row in profile_rows]
    total = len(profiles)
    total_job_requests = len(job_request_created_ats)
    scores = [_profile_completeness(p) for p in profiles]
    completed = sum(1 for s in scores if s >= 1.0)
    average = (sum(scores) / total) if total else 0.0

    histogram: dict[str, int] = {f"{pct}%": 0 for pct in _HISTOGRAM_BUCKETS}
    for score in scores:
        histogram[_histogram_bucket(score)] += 1

    languages: dict[str, int] = {}
    skill_kinds: dict[str, int] = {kind.value: 0 for kind in SkillKind}
    skill_evidence: dict[str, int] = {grade.value: 0 for grade in EvidenceGrade}
    availability: dict[str, int] = {a.value: 0 for a in Availability}
    constraints: dict[str, int] = {c.value: 0 for c in WorkConstraint}

    profiles_by_week: dict[str, int] = {}
    for (profile, created_at), score in zip(profile_rows, scores, strict=True):
        for lang in profile.get("languages") or []:
            key = f"{lang.get('language')} ({lang.get('level')})"
            languages[key] = languages.get(key, 0) + 1
        for skill in profile.get("skills") or []:
            kind = skill.get("kind")
            if kind in skill_kinds:
                skill_kinds[kind] += 1
            evidence = skill.get("evidence")
            if evidence in skill_evidence:
                skill_evidence[evidence] += 1
        aspiration = profile.get("aspiration")
        if isinstance(aspiration, dict):
            avail = aspiration.get("availability")
            if avail in availability:
                availability[avail] += 1
            for constraint in aspiration.get("constraints") or []:
                if constraint in constraints:
                    constraints[constraint] += 1
        if score >= 1.0:
            week = _week_key(created_at)
            profiles_by_week[week] = profiles_by_week.get(week, 0) + 1

    job_requests_by_week: dict[str, int] = {}
    for created_at in job_request_created_ats:
        week = _week_key(created_at)
        job_requests_by_week[week] = job_requests_by_week.get(week, 0) + 1

    top_gaps: dict[str, int] = {}
    for gaps in gap_maps:
        for gap_key, count in (gaps or {}).items():
            top_gaps[gap_key] = top_gaps.get(gap_key, 0) + int(count)

    evaluated = int(evaluated)
    compatible = int(compatible)
    compatible_rate = (compatible / evaluated) if evaluated else 0.0

    return Report(
        coverage=Coverage(
            total_profiles=total,
            completed_profiles=completed,
            average_completeness=average,
            completeness_histogram=_suppress_map(histogram, k),
        ),
        languages=_suppress_and_drop_rare_keys(languages, k),
        skill_kinds=_suppress_map(skill_kinds, k),
        skill_evidence=_suppress_map(skill_evidence, k),
        availability=_suppress_map(availability, k),
        constraints=_suppress_map(constraints, k),
        total_job_requests=total_job_requests,
        matching=MatchingAgg(
            runs=int(runs),
            evaluated=evaluated,
            compatible=compatible,
            compatible_rate=compatible_rate,
            top_gaps=_suppress_and_drop_rare_keys(top_gaps, k),
        ),
        trends=Trends(
            profiles_by_week=_suppress_map(profiles_by_week, k),
            job_requests_by_week=_suppress_map(job_requests_by_week, k),
        ),
    )
