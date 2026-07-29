"""Aggregate/anonymous report DTOs (§7.2/§7.3, Fase 2·B).

Every ``dict[str, Count]`` field here is a MARGINAL distribution (never a
fine cross-tab) whose values have already passed through
``bussola.report.service.suppress`` before reaching this model — small
cells (1..k-1) arrive as the sentinel string ``"<5"``, never as a raw
number. The plain ``int``/``float`` fields (``total_profiles``,
``completed_profiles``, ``average_completeness``, ``total_job_requests``,
``runs``/``evaluated``/``compatible``/``compatible_rate``) are global,
non-identifying aggregates and are never suppressed.

Nothing here carries a pseudonym or per-person data (§2/§5): only counts.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

# A suppressed small cell (§ anonymity: k=5 small-cell suppression).
Count = int | Literal["<5"]


class Coverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_profiles: int
    completed_profiles: int
    average_completeness: float
    completeness_histogram: dict[str, Count]


class MatchingAgg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: int
    evaluated: int
    compatible: int
    compatible_rate: float
    top_gaps: dict[str, Count]


class Trends(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles_by_week: dict[str, Count]
    job_requests_by_week: dict[str, Count]


class Report(BaseModel):
    """The full aggregate/anonymous report (§7.2 «Metriche minime di
    qualità», extended). Only marginal distributions over enumerated
    fields; free text (skill names, sectors, roles, training topics) is
    never turned into a category here (no taxonomy, §6) — the only
    free-text aggregation is ``matching.top_gaps``, which is already
    aggregated frequency data (``matching.match_run.gaps``)."""

    model_config = ConfigDict(extra="forbid")

    coverage: Coverage
    languages: dict[str, Count]  # "<language> (<level>)" -> count
    skill_kinds: dict[str, Count]
    skill_evidence: dict[str, Count]
    availability: dict[str, Count]
    constraints: dict[str, Count]
    total_job_requests: int
    matching: MatchingAgg
    trends: Trends
